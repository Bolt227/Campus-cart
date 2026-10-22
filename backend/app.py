import os

import re


import sqlite3
from pathlib import Path
from uuid import uuid4


import requests
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, redirect, request, send_from_directory, session

from flask import Flask, jsonify, redirect, request, send_from_directory, session

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename



load_dotenv()


BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
DATABASE = BASE_DIR / "database.db"
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

UPLOAD_FOLDER.mkdir(exist_ok=True)

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

app.config["SECRET_KEY"] = secret_key
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Cashfree Payment Gateway configuration.
# Set CASHFREE_APP_ID and CASHFREE_SECRET_KEY in your environment.
# Keep CASHFREE_MODE=sandbox while testing.
CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "")
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "")
CASHFREE_API_VERSION = os.environ.get("CASHFREE_API_VERSION", "2025-01-01")
CASHFREE_MODE = os.environ.get("CASHFREE_MODE", "sandbox").lower()
CASHFREE_BASE_URL = (
    "https://sandbox.cashfree.com/pg"
    if CASHFREE_MODE == "sandbox"
    else "https://api.cashfree.com/pg"
)



def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db_connection()

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items (id),
            FOREIGN KEY (buyer_id) REFERENCES users (id),
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
    """)


    connection.commit()
    connection.close()


init_db()


@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR / "templates", "index.html")


@app.route("/add-item")
def add_item_page():
    if session.get("user_id") is None:
        return redirect("/login")

    return send_from_directory(FRONTEND_DIR / "templates", "add_item.html")


@app.route("/login")
def login_page():
    return send_from_directory(FRONTEND_DIR / "templates", "login.html")


@app.route("/register")
def register_page():
    return send_from_directory(FRONTEND_DIR / "templates", "register.html")


@app.route("/item/<int:item_id>")
def item_page(item_id):
    return send_from_directory(FRONTEND_DIR / "templates", "item_details.html")


@app.route("/edit-item/<int:item_id>")
def edit_item_page(item_id):
    if session.get("user_id") is None:
            return redirect("/login")
    return send_from_directory(FRONTEND_DIR / "templates", "edit_item.html")


@app.route("/my-listings")
def my_listings_page():
    if session.get("user_id") is None:
            return redirect("/login")
    return send_from_directory(FRONTEND_DIR / "templates", "my_listings.html")


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if not (email.endswith("@vitstudent.ac.in") or email.endswith("@vit.ac.in")):
        return jsonify({"error": "Use a VIT email address"}), 400

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        connection.commit()

        return jsonify({
            "message": "Student registered successfully",
            "user_id": cursor.lastrowid,
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "This email is already registered"}), 409

    finally:
        connection.close()


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    connection = get_db_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    connection.close()

    if user is None or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user["id"]

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
        },
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/items", methods=["POST"])
def create_item():
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to post an item"}), 401

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    item_condition = request.form.get("item_condition", "").strip()
    image = request.files.get("image")

    try:
        price = float(request.form.get("price"))
        if price <= 0:
            return jsonify({"error": "Price must be greater than zero"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a valid number"}), 400

    if not all([title, description, category, item_condition]):
        return jsonify({"error": "All item details are required"}), 400

    image_path = None

    if image and image.filename:
        if not allowed_file(image.filename):
            return jsonify({
                "error": "Use PNG, JPG, JPEG, GIF, or WEBP images"
            }), 400

        filename = secure_filename(image.filename)
        unique_filename = f"{uuid4().hex}_{filename}"
        image.save(app.config["UPLOAD_FOLDER"] / unique_filename)
        image_path = f"/uploads/{unique_filename}"

    connection = get_db_connection()

    seller = connection.execute(
        "SELECT id FROM users WHERE id = ?",
        (seller_id,),
    ).fetchone()

    if seller is None:
        connection.close()
        return jsonify({"error": "Seller not found"}), 404

    cursor = connection.execute("""
        INSERT INTO items
        (title, description, category, item_condition, price, image_path, seller_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        description,
        category,
        item_condition,
        price,
        image_path,
        seller_id,
    ))

    connection.commit()
    item_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "message": "Item posted successfully",
        "item_id": item_id,
    }), 201


@app.route("/api/items")
def get_items():
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

    query += " ORDER BY created_at DESC"

    connection = get_db_connection()
    items = connection.execute(query, values).fetchall()
    connection.close()

    return jsonify([dict(item) for item in items])


@app.route("/api/items/<int:item_id>")
def get_item_details(item_id):
    connection = get_db_connection()

    item = connection.execute("""
        SELECT
            items.*,
            users.name AS seller_name,
            users.email AS seller_email
        FROM items
        JOIN users ON items.seller_id = users.id
        WHERE items.id = ?
    """, (item_id,)).fetchone()

    connection.close()

    if item is None:
        return jsonify({"error": "Item not found"}), 404

    return jsonify(dict(item))


@app.route("/api/users/<int:seller_id>/items")
def get_my_items(seller_id):
    logged_in_user_id = session.get("user_id")

    if logged_in_user_id is None:
        return jsonify({"error": "Please log in to view your listings"}), 401

    if seller_id != logged_in_user_id:
        return jsonify({"error": "You can only view your own listings"}), 403

    connection = get_db_connection()
    items = connection.execute(
        "SELECT * FROM items WHERE seller_id = ? ORDER BY created_at DESC",
        (logged_in_user_id,),
    ).fetchall()
    connection.close()

    return jsonify([dict(item) for item in items])


@app.route("/api/items/<int:item_id>/sold", methods=["PATCH"])
def mark_item_sold(item_id):
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to update an item"}), 401

    connection = get_db_connection()

    item = connection.execute(
        "SELECT id FROM items WHERE id = ? AND seller_id = ?",
        (item_id, seller_id),
    ).fetchone()

    if item is None:
        connection.close()
        return jsonify({"error": "Item not found or you are not the seller"}), 404

    connection.execute(
        "UPDATE items SET status = 'sold' WHERE id = ?",
        (item_id,),
    )

    connection.commit()
    connection.close()

    return jsonify({"message": "Item marked as sold"})


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to edit an item"}), 401

    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "").strip()
    item_condition = data.get("item_condition", "").strip()

    try:
        price = float(data.get("price"))
        if price <= 0:
            return jsonify({"error": "Price must be greater than zero"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a valid number"}), 400

    if not all([title, description, category, item_condition]):
        return jsonify({"error": "All item details are required"}), 400

    connection = get_db_connection()

    item = connection.execute(
        "SELECT id FROM items WHERE id = ? AND seller_id = ?",
        (item_id, seller_id),
    ).fetchone()

    if item is None:
        connection.close()
        return jsonify({"error": "Item not found or you are not the seller"}), 404

    connection.execute("""
        UPDATE items
        SET title = ?, description = ?, category = ?,
            item_condition = ?, price = ?
        WHERE id = ?
    """, (
        title,
        description,
        category,
        item_condition,
        price,
        item_id,
    ))

    connection.commit()
    connection.close()

    return jsonify({"message": "Item updated successfully"})


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    seller_id = session.get("user_id")
    if seller_id is None:
        return jsonify({"error": "Please log in to delete an item"}), 401

    connection = get_db_connection()

    item = connection.execute(
        "SELECT id FROM items WHERE id = ? AND seller_id = ?",
        (item_id, seller_id),
    ).fetchone()

    if item is None:
        connection.close()
        return jsonify({"error": "Item not found or you are not the seller"}), 404

    connection.execute(
        "DELETE FROM items WHERE id = ?",
        (item_id,),
    )

    connection.commit()
    connection.close()

    return jsonify({"message": "Item deleted successfully"})


<<<<<<< HEAD

def cashfree_headers():
    """Build headers for Cashfree's server-side API requests."""
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


def refresh_payment_status(order_id, buyer_id=None):
    """Refresh a local order from Cashfree and update the listing if paid."""
    connection = get_db_connection()
    try:
        query = "SELECT * FROM payment_orders WHERE order_id = ?"
        params = [order_id]
        if buyer_id is not None:
            query += " AND buyer_id = ?"
            params.append(buyer_id)

        local_order = connection.execute(query, params).fetchone()
        if local_order is None:
            return None

        gateway_order = get_payment_order(order_id)
        gateway_status = gateway_order.get("order_status", "PENDING")

        # Mark paid only when Cashfree's server API reports PAID and the
        # amount/currency match the local order record.
        if gateway_status == "PAID":
            gateway_amount = gateway_order.get("order_amount")
            try:
                amount_matches = round(float(gateway_amount) * 100) == local_order["amount_paise"]
            except (TypeError, ValueError):
                amount_matches = False

            if not amount_matches or gateway_order.get("order_currency") != "INR":
                current_app.logger.error(
                    "Cashfree order amount/currency mismatch for %s", order_id
                )
                return local_order["payment_status"]

            # Update the payment record. Only mark the item sold if it is
            # still available. For production, reserve listings when orders
            # are created to prevent concurrent purchases.
            connection.execute(
                """UPDATE payment_orders
                   SET payment_status = 'PAID'
                   WHERE order_id = ?""",
                (order_id,),
            )
            connection.execute(
                """UPDATE items SET status = 'sold'
                   WHERE id = ? AND status = 'available'""",
                (local_order["item_id"],),
            )
            connection.commit()
            return "PAID"

        if gateway_status in ("EXPIRED", "TERMINATED"):
            connection.execute(
                """UPDATE payment_orders
                   SET payment_status = ?
                   WHERE order_id = ? AND payment_status != 'PAID'""",
                (gateway_status, order_id),
            )
            connection.commit()
            return gateway_status

        return local_order["payment_status"]
    finally:
        connection.close()


@app.route("/api/payments/create-order", methods=["POST"])
def create_cashfree_order():
    """Create a Cashfree checkout order for an existing Campus Cart item."""
    buyer_id = session.get("user_id")
    if buyer_id is None:
        return jsonify({"error": "Please log in before making a purchase"}), 401

    if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY:
        return jsonify({
            "error": "Cashfree is not configured. Set CASHFREE_APP_ID and CASHFREE_SECRET_KEY."
        }), 503

    data = request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("item_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid item_id is required"}), 400

    phone = str(data.get("customer_phone", "")).strip()
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        return jsonify({"error": "Enter a valid 10-digit Indian mobile number"}), 400

    connection = get_db_connection()
    try:
        buyer = connection.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (buyer_id,),
        ).fetchone()

        item = connection.execute(
            """SELECT id, title, price, status, seller_id
               FROM items WHERE id = ?""",
            (item_id,),
        ).fetchone()

        if buyer is None:
            session.clear()
            return jsonify({"error": "Your account was not found. Please log in again."}), 401

        if item is None:
            return jsonify({"error": "Item not found"}), 404

        if item["status"] != "available":
            return jsonify({"error": "This item is no longer available"}), 409

        if item["seller_id"] == buyer_id:
            return jsonify({"error": "You cannot buy your own listing"}), 400

        try:
            amount_paise = round(float(item["price"]) * 100)
        except (TypeError, ValueError):
            return jsonify({"error": "This item's price is invalid"}), 400

        if amount_paise <= 0:
            return jsonify({"error": "This item's price must be greater than zero"}), 400

        order_id = "cc_" + uuid4().hex[:24]
        amount_rupees = amount_paise / 100

        # Cashfree requires a return URL with the {order_id} placeholder.
        return_url = request.url_root.rstrip("/") + "/payment/return?order_id={order_id}"

        payload = {
            "order_id": order_id,
            "order_amount": amount_rupees,
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"cc_user_{buyer_id}",
                "customer_phone": phone,
                "customer_email": buyer["email"],
                "customer_name": buyer["name"][:100],
            },
            "order_meta": {
                "return_url": return_url,
            },
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
            return jsonify({
                "error": "Cashfree could not create the order. Check credentials and server logs."
            }), 502

        payment_session_id = gateway_order.get("payment_session_id")
        if not payment_session_id:
            current_app.logger.error("Cashfree response did not include payment_session_id")
            return jsonify({"error": "Cashfree returned an invalid order response"}), 502

        connection.execute(
            """INSERT INTO payment_orders
               (order_id, item_id, buyer_id, seller_id, amount_paise, payment_status)
               VALUES (?, ?, ?, ?, ?, 'PENDING')""",
            (order_id, item_id, buyer_id, item["seller_id"], amount_paise),
        )
        connection.commit()

        return jsonify({
            "order_id": order_id,
            "payment_session_id": payment_session_id,
            "item_id": item_id,
            "item_title": item["title"],
            "amount": amount_rupees,
            "currency": "INR",
        }), 201
    finally:
        connection.close()


@app.route("/api/payments/status/<order_id>", methods=["GET"])
def cashfree_payment_status(order_id):
    buyer_id = session.get("user_id")
    if buyer_id is None:
        return jsonify({"error": "Please log in to check this order"}), 401

    connection = get_db_connection()
    try:
        order = connection.execute(
            """SELECT order_id, payment_status FROM payment_orders
               WHERE order_id = ? AND buyer_id = ?""",
            (order_id, buyer_id),
        ).fetchone()
    finally:
        connection.close()

    if order is None:
        return jsonify({"error": "Order not found"}), 404

    if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY:
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


@app.route("/payment/return", methods=["GET"])
def cashfree_payment_return():
    """Cashfree redirects here; verify status server-to-server before showing it."""
    order_id = request.args.get("order_id", "").strip()
    if not order_id:
        return "Missing order ID", 400

    buyer_id = session.get("user_id")
    if buyer_id is None:
        return redirect("/login")

    connection = get_db_connection()
    try:
        order = connection.execute(
            """SELECT order_id FROM payment_orders
               WHERE order_id = ? AND buyer_id = ?""",
            (order_id, buyer_id),
        ).fetchone()
    finally:
        connection.close()

    if order is None:
        return "Order not found", 404

    status = "PENDING"
    if CASHFREE_APP_ID and CASHFREE_SECRET_KEY:
        try:
            status = refresh_payment_status(order_id, buyer_id=buyer_id) or "PENDING"
        except requests.RequestException:
            current_app.logger.exception("Could not refresh Cashfree status on return")

    if status == "PAID":
        message = "Payment confirmed. Thank you for using Campus Cart."
    elif status in ("EXPIRED", "TERMINATED"):
        message = "This payment order expired or was terminated."
    else:
        message = "Payment is not confirmed yet. Check your order status again shortly."

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Campus Cart payment status</title></head><body>"
        "<h1>Campus Cart</h1><h2>Payment status: "
        + status
        + "</h2><p>"
        + message
        + "</p><p>Order ID: "
        + order_id
        + "</p><a href='/'>Return to Campus Cart</a></body></html>"
    )



@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(debug=True)
