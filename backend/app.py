import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


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


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(debug=True)