import base64
import hashlib
import hmac
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    request,
    send_from_directory,
    session,
)
from markupsafe import escape
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

# --------------------------------------------------------------------------
# Paths and configuration
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"

# DATA_DIR lets you keep the database and uploads on a persistent disk.
DATA_DIR = Path(os.environ.get("DATA_DIR") or BASE_DIR).resolve()
DATABASE = DATA_DIR / "database.db"
UPLOAD_FOLDER = DATA_DIR / "uploads"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
CATEGORIES = {"Textbooks", "Electronics", "Furniture", "Stationery", "Lab Equipment"}
CONDITIONS = {"New", "Like New", "Good", "Fair"}
MAX_PRICE = 1_000_000

# How long an item stays reserved while a buyer is paying.
RESERVATION_MINUTES = 30

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR / "static"),
    static_url_path="/static",
)

secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError(
        "Set the SECRET_KEY environment variable before starting the app."
    )

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

app.config.update(
    SECRET_KEY=secret_key,
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB upload limit
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=PUBLIC_BASE_URL.startswith("https://"),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

# Cashfree Payment Gateway configuration.
# Keep CASHFREE_MODE=sandbox while testing.
CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "")
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "")
CASHFREE_API_VERSION = os.environ.get("CASHFREE_API_VERSION", "2025-01-01")
CASHFREE_MODE = (
    "production"
    if os.environ.get("CASHFREE_MODE", "sandbox").strip().lower() == "production"
    else "sandbox"
)
CASHFREE_BASE_URL = (
    "https://api.cashfree.com/pg"
    if CASHFREE_MODE == "production"
    else "https://sandbox.cashfree.com/pg"
)


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

@contextmanager
def db():
    """Open a connection, commit on success, roll back on error, always close."""
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                item_condition TEXT NOT NULL,
                price REAL NOT NULL,
                image_path TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                seller_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (seller_id) REFERENCES users (id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                order_id TEXT PRIMARY KEY,
                item_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                amount_paise INTEGER NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'PENDING',
                payment_session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id),
                FOREIGN KEY (buyer_id) REFERENCES users (id),
                FOREIGN KEY (seller_id) REFERENCES users (id)
            )
        """)

        # Older databases were created without payment_session_id.
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(payment_orders)")
        }
        if "payment_session_id" not in columns:
            connection.execute(
                "ALTER TABLE payment_orders ADD COLUMN payment_session_id TEXT"
            )


init_db()


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def clean_text(source, key, max_length):
    """Return a stripped string from JSON/form data, or '' if missing/not text."""
    value = source.get(key, "")
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def parse_price(raw):
    """Return a valid price rounded to 2 decimals, or None."""
    try:
        price = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or price <= 0 or price > MAX_PRICE:
        return None
    return round(price, 2)


def remove_uploaded_image(image_path):
    if image_path and image_path.startswith("/uploads/"):
        (UPLOAD_FOLDER / Path(image_path).name).unlink(missing_ok=True)


def public_base_url():
    return PUBLIC_BASE_URL or request.url_root.rstrip("/")


# --------------------------------------------------------------------------
# Page routes
# --------------------------------------------------------------------------

def page(filename):
    return send_from_directory(TEMPLATES_DIR, filename)


@app.route("/")
def home():
    return page("index.html")


@app.route("/add-item")
def add_item_page():
    if session.get("user_id") is None:
        return redirect("/login")
    return page("add_item.html")


@app.route("/login")
def login_page():
    return page("login.html")


@app.route("/register")
def register_page():
    return page("register.html")


@app.route("/item/<int:item_id>")
def item_page(item_id):
    return page("item_details.html")


@app.route("/edit-item/<int:item_id>")
def edit_item_page(item_id):
    if session.get("user_id") is None:
        return redirect("/login")
    return page("edit_item.html")


@app.route("/my-listings")
def my_listings_page():
    if session.get("user_id") is None:
        return redirect("/login")
    return page("my_listings.html")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# --------------------------------------------------------------------------
# Auth API
# --------------------------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = clean_text(data, "name", 100)
    email = clean_text(data, "email", 200).lower()
    password = data.get("password", "")

    if not name or not email or not isinstance(password, str) or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if len(password) > 200:
        return jsonify({"error": "Password is too long"}), 400

    if not (email.endswith("@vitstudent.ac.in") or email.endswith("@vit.ac.in")):
        return jsonify({"error": "Use a VIT email address"}), 400

    try:
        with db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "This email is already registered"}), 409

    return jsonify({
        "message": "Student registered successfully",
        "user_id": user_id,
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = clean_text(data, "email", 200).lower()
    password = data.get("password", "")

    if not email or not isinstance(password, str) or not password:
        return jsonify({"error": "Email and password are required"}), 400

    with db() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    if user is None or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]

    return jsonify({
        "message": "Login successful",
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/me")
def me():
    """Tell the browser whether its login session is still valid."""
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "Not logged in"}), 401

    with db() as connection:
        user = connection.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    if user is None:
        session.clear()
        return jsonify({"error": "Not logged in"}), 401

    return jsonify({"user": dict(user)})


# --------------------------------------------------------------------------
# Items API
# --------------------------------------------------------------------------

@app.route("/api/items", methods=["POST"])
def create_item():
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to post an item"}), 401

    title = clean_text(request.form, "title", 120)
    description = clean_text(request.form, "description", 2000)
    category = clean_text(request.form, "category", 50)
    item_condition = clean_text(request.form, "item_condition", 50)
    image = request.files.get("image")

    price = parse_price(request.form.get("price"))
    if price is None:
        return jsonify({"error": "Enter a valid price greater than zero"}), 400

    if not all([title, description, category, item_condition]):
        return jsonify({"error": "All item details are required"}), 400
    if category not in CATEGORIES:
        return jsonify({"error": "Choose a valid category"}), 400
    if item_condition not in CONDITIONS:
        return jsonify({"error": "Choose a valid condition"}), 400

    image_path = None
    saved_file = None

    if image and image.filename:
        if not allowed_file(image.filename):
            return jsonify({
                "error": "Use PNG, JPG, JPEG, GIF, or WEBP images"
            }), 400

        filename = secure_filename(image.filename)
        unique_filename = f"{uuid4().hex}_{filename}"
        saved_file = UPLOAD_FOLDER / unique_filename
        image.save(saved_file)
        image_path = f"/uploads/{unique_filename}"

    try:
        with db() as connection:
            seller = connection.execute(
                "SELECT id FROM users WHERE id = ?", (seller_id,)
            ).fetchone()

            if seller is None:
                session.clear()
                if saved_file:
                    saved_file.unlink(missing_ok=True)
                return jsonify({"error": "Please log in again"}), 401

            cursor = connection.execute("""
                INSERT INTO items
                (title, description, category, item_condition, price, image_path, seller_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, description, category, item_condition, price,
                  image_path, seller_id))
            item_id = cursor.lastrowid
    except Exception:
        if saved_file:
            saved_file.unlink(missing_ok=True)
        raise

    return jsonify({"message": "Item posted successfully", "item_id": item_id}), 201


@app.route("/api/items")
def get_items():
    release_stale_reservations()

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    query = "SELECT * FROM items WHERE status = 'available'"
    values = []

    if search:
        query += " AND (title LIKE ? OR description LIKE ?)"
        values.extend([f"%{search}%", f"%{search}%"])

    if category:
        query += " AND category = ?"
        values.append(category)

    query += " ORDER BY created_at DESC, id DESC"

    with db() as connection:
        items = connection.execute(query, values).fetchall()

    return jsonify([dict(item) for item in items])


@app.route("/api/items/<int:item_id>")
def get_item_details(item_id):
    release_stale_reservations()

    with db() as connection:
        item = connection.execute("""
            SELECT items.*, users.name AS seller_name, users.email AS seller_email
            FROM items
            JOIN users ON items.seller_id = users.id
            WHERE items.id = ?
        """, (item_id,)).fetchone()

    if item is None:
        return jsonify({"error": "Item not found"}), 404

    result = dict(item)

    # Only logged-in students can see the seller's email address.
    if session.get("user_id") is None:
        result["seller_email"] = None

    return jsonify(result)


@app.route("/api/users/<int:seller_id>/items")
def get_my_items(seller_id):
    logged_in_user_id = session.get("user_id")

    if logged_in_user_id is None:
        return jsonify({"error": "Please log in to view your listings"}), 401

    if seller_id != logged_in_user_id:
        return jsonify({"error": "You can only view your own listings"}), 403

    release_stale_reservations()

    with db() as connection:
        items = connection.execute(
            "SELECT * FROM items WHERE seller_id = ? ORDER BY created_at DESC, id DESC",
            (logged_in_user_id,),
        ).fetchall()

    return jsonify([dict(item) for item in items])


@app.route("/api/items/<int:item_id>/sold", methods=["PATCH"])
def mark_item_sold(item_id):
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to update an item"}), 401

    with db() as connection:
        item = connection.execute(
            "SELECT id, status FROM items WHERE id = ? AND seller_id = ?",
            (item_id, seller_id),
        ).fetchone()

        if item is None:
            return jsonify({"error": "Item not found or you are not the seller"}), 404

        if item["status"] == "pending":
            return jsonify({
                "error": "A buyer is paying for this item right now. Try again shortly."
            }), 409

        connection.execute(
            "UPDATE items SET status = 'sold' WHERE id = ?", (item_id,)
        )

    return jsonify({"message": "Item marked as sold"})


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to edit an item"}), 401

    data = request.get_json(silent=True) or {}

    title = clean_text(data, "title", 120)
    description = clean_text(data, "description", 2000)
    category = clean_text(data, "category", 50)
    item_condition = clean_text(data, "item_condition", 50)

    price = parse_price(data.get("price"))
    if price is None:
        return jsonify({"error": "Enter a valid price greater than zero"}), 400

    if not all([title, description, category, item_condition]):
        return jsonify({"error": "All item details are required"}), 400
    if category not in CATEGORIES:
        return jsonify({"error": "Choose a valid category"}), 400
    if item_condition not in CONDITIONS:
        return jsonify({"error": "Choose a valid condition"}), 400

    with db() as connection:
        item = connection.execute(
            "SELECT id, status FROM items WHERE id = ? AND seller_id = ?",
            (item_id, seller_id),
        ).fetchone()

        if item is None:
            return jsonify({"error": "Item not found or you are not the seller"}), 404

        # The price must not change while a buyer is paying for it.
        if item["status"] == "pending":
            return jsonify({
                "error": "A buyer is paying for this item right now. Try again shortly."
            }), 409

        connection.execute("""
            UPDATE items
            SET title = ?, description = ?, category = ?,
                item_condition = ?, price = ?
            WHERE id = ?
        """, (title, description, category, item_condition, price, item_id))

    return jsonify({"message": "Item updated successfully"})


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to delete an item"}), 401

    with db() as connection:
        item = connection.execute(
            "SELECT id, status, image_path FROM items WHERE id = ? AND seller_id = ?",
            (item_id, seller_id),
        ).fetchone()

        if item is None:
            return jsonify({"error": "Item not found or you are not the seller"}), 404

        if item["status"] == "pending":
            return jsonify({
                "error": "A buyer is paying for this item right now. Try again shortly."
            }), 409

        paid = connection.execute(
            "SELECT 1 FROM payment_orders WHERE item_id = ? AND payment_status = 'PAID'",
            (item_id,),
        ).fetchone()
        if paid is not None:
            return jsonify({
                "error": "This item has a paid order and cannot be deleted."
            }), 409

        connection.execute("DELETE FROM payment_orders WHERE item_id = ?", (item_id,))
        connection.execute("DELETE FROM items WHERE id = ?", (item_id,))

    remove_uploaded_image(item["image_path"])

    return jsonify({"message": "Item deleted successfully"})


# --------------------------------------------------------------------------
# Cashfree payments
# --------------------------------------------------------------------------

def cashfree_configured():
    return bool(CASHFREE_APP_ID and CASHFREE_SECRET_KEY)


def cashfree_headers():
    """Headers for Cashfree's server-side API requests."""
    return {
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY,
        "x-api-version": CASHFREE_API_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def get_payment_order(order_id):
    """Fetch an order directly from Cashfree; never trust browser status."""
    response = requests.get(
        f"{CASHFREE_BASE_URL}/orders/{order_id}",
        headers=cashfree_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def release_item(connection, item_id):
    """Make a reserved item available again if no payment is still pending."""
    connection.execute(
        """UPDATE items SET status = 'available'
           WHERE id = ? AND status = 'pending'
             AND NOT EXISTS (
                 SELECT 1 FROM payment_orders
                 WHERE item_id = ? AND payment_status = 'PENDING'
             )""",
        (item_id, item_id),
    )


def refresh_payment_status(order_id, buyer_id=None):
    """Refresh a local order from Cashfree and update the item to match."""
    query = "SELECT * FROM payment_orders WHERE order_id = ?"
    params = [order_id]
    if buyer_id is not None:
        query += " AND buyer_id = ?"
        params.append(buyer_id)

    with db() as connection:
        local_order = connection.execute(query, params).fetchone()

    if local_order is None:
        return None

    if local_order["payment_status"] == "PAID":
        return "PAID"

    gateway_order = get_payment_order(order_id)
    gateway_status = gateway_order.get("order_status", "PENDING")

    with db() as connection:
        if gateway_status == "PAID":
            # Only trust PAID if amount and currency match what we created.
            try:
                amount_matches = (
                    round(float(gateway_order.get("order_amount")) * 100)
                    == local_order["amount_paise"]
                )
            except (TypeError, ValueError):
                amount_matches = False

            if not amount_matches or gateway_order.get("order_currency") != "INR":
                current_app.logger.error(
                    "Cashfree order amount/currency mismatch for %s", order_id
                )
                return local_order["payment_status"]

            connection.execute(
                "UPDATE payment_orders SET payment_status = 'PAID' WHERE order_id = ?",
                (order_id,),
            )
            connection.execute(
                """UPDATE items SET status = 'sold'
                   WHERE id = ? AND status IN ('available', 'pending')""",
                (local_order["item_id"],),
            )
            return "PAID"

        if gateway_status in ("EXPIRED", "TERMINATED"):
            connection.execute(
                """UPDATE payment_orders SET payment_status = ?
                   WHERE order_id = ? AND payment_status != 'PAID'""",
                (gateway_status, order_id),
            )
            release_item(connection, local_order["item_id"])
            return gateway_status

    return local_order["payment_status"]


def release_stale_reservations():
    """Free items whose payment order has run past its reservation time."""
    if not cashfree_configured():
        return

    cutoff = f"-{RESERVATION_MINUTES + 5} minutes"
    with db() as connection:
        stale = connection.execute(
            """SELECT order_id FROM payment_orders
               WHERE payment_status = 'PENDING'
                 AND created_at < datetime('now', ?)""",
            (cutoff,),
        ).fetchall()

    for row in stale:
        try:
            refresh_payment_status(row["order_id"])
        except requests.RequestException:
            current_app.logger.exception("Could not refresh stale order")


@app.route("/api/payments/create-order", methods=["POST"])
def create_cashfree_order():
    """Reserve an item and create a Cashfree checkout order for it."""
    buyer_id = session.get("user_id")
    if buyer_id is None:
        return jsonify({"error": "Please log in before making a purchase"}), 401

    if not cashfree_configured():
        return jsonify({
            "error": "Payments are not configured yet. Please try again later."
        }), 503

    data = request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("item_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid item_id is required"}), 400

    phone = str(data.get("customer_phone", "")).strip()
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        return jsonify({"error": "Enter a valid 10-digit Indian mobile number"}), 400

    release_stale_reservations()

    with db() as connection:
        buyer = connection.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (buyer_id,)
        ).fetchone()
        item = connection.execute(
            "SELECT id, title, price, status, seller_id FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()

        if buyer is None:
            session.clear()
            return jsonify({"error": "Your account was not found. Please log in again."}), 401
        if item is None:
            return jsonify({"error": "Item not found"}), 404
        if item["seller_id"] == buyer_id:
            return jsonify({"error": "You cannot buy your own listing"}), 400

        # If this buyer already has an open order for the item, reuse it so a
        # failed or abandoned payment can be retried without waiting.
        existing = connection.execute(
            """SELECT order_id, payment_session_id, amount_paise
               FROM payment_orders
               WHERE item_id = ? AND buyer_id = ?
                 AND payment_status = 'PENDING'
                 AND payment_session_id IS NOT NULL
                 AND created_at >= datetime('now', ?)
               ORDER BY created_at DESC LIMIT 1""",
            (item_id, buyer_id, f"-{RESERVATION_MINUTES} minutes"),
        ).fetchone()

        if existing is not None and item["status"] == "pending":
            return jsonify({
                "order_id": existing["order_id"],
                "payment_session_id": existing["payment_session_id"],
                "item_id": item_id,
                "item_title": item["title"],
                "amount": existing["amount_paise"] / 100,
                "currency": "INR",
                "mode": CASHFREE_MODE,
            }), 200

        if item["status"] != "available":
            return jsonify({"error": "This item is no longer available"}), 409

        # Reserve the item. This UPDATE only succeeds for one buyer.
        reserved = connection.execute(
            "UPDATE items SET status = 'pending' WHERE id = ? AND status = 'available'",
            (item_id,),
        )
        if reserved.rowcount == 0:
            return jsonify({"error": "This item is no longer available"}), 409

    # Reserved. From here, release the item again if anything fails.
    def release():
        with db() as connection:
            release_item(connection, item_id)

    try:
        # Read the price after reserving; sellers cannot edit a pending item.
        with db() as connection:
            price = connection.execute(
                "SELECT price FROM items WHERE id = ?", (item_id,)
            ).fetchone()["price"]

        amount_paise = round(float(price) * 100)
        if amount_paise <= 0:
            release()
            return jsonify({"error": "This item's price is invalid"}), 400

        amount_rupees = amount_paise / 100
        order_id = "cc_" + uuid4().hex[:24]
        base_url = public_base_url()

        expiry = (
            datetime.now(timezone.utc) + timedelta(minutes=RESERVATION_MINUTES)
        ).replace(microsecond=0).isoformat()

        order_meta = {
            "return_url": base_url + "/payment/return?order_id={order_id}",
        }
        if base_url.startswith("https://"):
            order_meta["notify_url"] = base_url + "/api/payments/webhook"

        payload = {
            "order_id": order_id,
            "order_amount": amount_rupees,
            "order_currency": "INR",
            "order_expiry_time": expiry,
            "customer_details": {
                "customer_id": f"cc_user_{buyer_id}",
                "customer_phone": phone,
                "customer_email": buyer["email"],
                "customer_name": buyer["name"][:100],
            },
            "order_meta": order_meta,
            "order_note": f"Campus Cart item {item_id}",
        }

        try:
            response = requests.post(
                f"{CASHFREE_BASE_URL}/orders",
                headers=cashfree_headers(),
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            gateway_order = response.json()
        except requests.RequestException:
            current_app.logger.exception("Cashfree order creation failed")
            release()
            return jsonify({
                "error": "Could not start the payment. Please try again."
            }), 502

        payment_session_id = gateway_order.get("payment_session_id")
        if not payment_session_id:
            current_app.logger.error("Cashfree response had no payment_session_id")
            release()
            return jsonify({"error": "Payment provider returned an invalid response"}), 502

        with db() as connection:
            connection.execute(
                """INSERT INTO payment_orders
                   (order_id, item_id, buyer_id, seller_id, amount_paise,
                    payment_status, payment_session_id)
                   VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
                (order_id, item_id, buyer_id, item["seller_id"],
                 amount_paise, payment_session_id),
            )

        return jsonify({
            "order_id": order_id,
            "payment_session_id": payment_session_id,
            "item_id": item_id,
            "item_title": item["title"],
            "amount": amount_rupees,
            "currency": "INR",
            "mode": CASHFREE_MODE,
        }), 201

    except Exception:
        current_app.logger.exception("Unexpected error creating order")
        release()
        return jsonify({"error": "Could not start the payment. Please try again."}), 500


@app.route("/api/payments/status/<order_id>", methods=["GET"])
def cashfree_payment_status(order_id):
    buyer_id = session.get("user_id")
    if buyer_id is None:
        return jsonify({"error": "Please log in to check this order"}), 401

    with db() as connection:
        order = connection.execute(
            """SELECT order_id, payment_status FROM payment_orders
               WHERE order_id = ? AND buyer_id = ?""",
            (order_id, buyer_id),
        ).fetchone()

    if order is None:
        return jsonify({"error": "Order not found"}), 404

    if not cashfree_configured():
        return jsonify({"error": "Cashfree is not configured"}), 503

    try:
        status = refresh_payment_status(order_id, buyer_id=buyer_id)
    except requests.RequestException:
        current_app.logger.exception("Cashfree payment status check failed")
        return jsonify({
            "order_id": order_id,
            "status": order["payment_status"],
            "message": "Unable to refresh status; please try again.",
        }), 502

    return jsonify({"order_id": order_id, "status": status or "PENDING"})


@app.route("/api/payments/webhook", methods=["POST"])
def cashfree_webhook():
    """Cashfree calls this when a payment changes. Verify, then re-check."""
    if not CASHFREE_SECRET_KEY:
        return jsonify({"error": "Not configured"}), 503

    raw_body = request.get_data()
    timestamp = request.headers.get("x-webhook-timestamp", "")
    signature = request.headers.get("x-webhook-signature", "")

    expected = base64.b64encode(
        hmac.new(
            CASHFREE_SECRET_KEY.encode(),
            timestamp.encode() + raw_body,
            hashlib.sha256,
        ).digest()
    ).decode()

    if not signature or not hmac.compare_digest(expected, signature):
        return jsonify({"error": "Invalid signature"}), 401

    payload = request.get_json(silent=True) or {}
    order = (payload.get("data") or {}).get("order") or {}
    order_id = order.get("order_id")

    if order_id:
        try:
            # Ask Cashfree directly instead of trusting the webhook body.
            refresh_payment_status(order_id)
        except requests.RequestException:
            current_app.logger.exception("Webhook status refresh failed")
            return jsonify({"error": "Try again"}), 502

    return jsonify({"ok": True})


@app.route("/payment/return", methods=["GET"])
def cashfree_payment_return():
    """Cashfree redirects here; verify status server-to-server before showing it."""
    order_id = request.args.get("order_id", "").strip()
    if not order_id:
        return "Missing order ID", 400

    buyer_id = session.get("user_id")
    if buyer_id is None:
        return redirect("/login")

    with db() as connection:
        order = connection.execute(
            "SELECT order_id FROM payment_orders WHERE order_id = ? AND buyer_id = ?",
            (order_id, buyer_id),
        ).fetchone()

    if order is None:
        return "Order not found", 404

    status = "PENDING"
    if cashfree_configured():
        try:
            status = refresh_payment_status(order_id, buyer_id=buyer_id) or "PENDING"
        except requests.RequestException:
            current_app.logger.exception("Could not refresh Cashfree status on return")

    if status == "PAID":
        message = "Payment confirmed. Thank you for using Campus Cart. Contact the seller to arrange pickup."
    elif status in ("EXPIRED", "TERMINATED"):
        message = "This payment expired or was cancelled. The item is available again."
    else:
        message = "Payment is not confirmed yet. Refresh this page in a moment."

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Campus Cart payment status</title></head>"
        "<body style='font-family:sans-serif;max-width:480px;margin:60px auto;padding:0 16px'>"
        "<h1>Campus Cart</h1>"
        f"<h2>Payment status: {escape(status)}</h2>"
        f"<p>{escape(message)}</p>"
        f"<p>Order ID: {escape(order_id)}</p>"
        "<a href='/'>Return to Campus Cart</a></body></html>"
    )


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"error": "The image is too large (5 MB maximum)"}), 413


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
