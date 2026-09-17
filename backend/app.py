import sqlite3
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR / "static"),
    static_url_path="/static"
)

DATABASE = BASE_DIR / "database.db"


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
    return send_from_directory(
        FRONTEND_DIR / "templates",
        "index.html"
    )
@app.route("/add-item")
def add_item_page():
    return send_from_directory(
        FRONTEND_DIR / "templates",
        "add_item.html"
    )
@app.route("/login")
def login_page():
    return send_from_directory(
        FRONTEND_DIR / "templates",
        "login.html"
    )
@app.route("/register")
def register_page():
    return send_from_directory(
        FRONTEND_DIR / "templates",
        "register.html"
    )
@app.route("/item/<int:item_id>")
def item_page(item_id):
    return send_from_directory(
        FRONTEND_DIR / "templates",
        "item_details.html"
    )
@app.route("/my-listings")
def my_listings_page():
    return send_from_directory(
        FRONTEND_DIR / "templates",
        "my_listings.html"
    )
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if not (email.endswith("@vitstudent.ac.in") or email.endswith("@vit.ac.in")):
        return jsonify({"error": "Use a VIT email address"}), 400

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password))
        )
        connection.commit()

        return jsonify({
            "message": "Student registered successfully",
            "user_id": cursor.lastrowid
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "This email is already registered"}), 409

    finally:
        connection.close()

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    connection = get_db_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()
    connection.close()

    if user is None or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    })
@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json()

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "").strip()
    item_condition = data.get("item_condition", "").strip()
    seller_id = data.get("seller_id")

    try:
        price = float(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a valid number"}), 400

    if not all([title, description, category, item_condition, seller_id]):
        return jsonify({"error": "All item details are required"}), 400

    connection = get_db_connection()

    seller = connection.execute(
        "SELECT id FROM users WHERE id = ?",
        (seller_id,)
    ).fetchone()

    if seller is None:
        connection.close()
        return jsonify({"error": "Seller not found"}), 404

    cursor = connection.execute("""
        INSERT INTO items
        (title, description, category, item_condition, price, seller_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, description, category, item_condition, price, seller_id))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Item posted successfully",
        "item_id": cursor.lastrowid
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
    connection = get_db_connection()

    items = connection.execute(
        "SELECT * FROM items WHERE seller_id = ? ORDER BY created_at DESC",
        (seller_id,)
    ).fetchall()

    connection.close()
    return jsonify([dict(item) for item in items])


@app.route("/api/items/<int:item_id>/sold", methods=["PATCH"])
def mark_item_sold(item_id):
    data = request.get_json()
    seller_id = data.get("seller_id")

    if not seller_id:
        return jsonify({"error": "Seller ID is required"}), 400

    connection = get_db_connection()

    item = connection.execute(
        "SELECT * FROM items WHERE id = ? AND seller_id = ?",
        (item_id, seller_id)
    ).fetchone()

    if item is None:
        connection.close()
        return jsonify({"error": "Item not found or you are not the seller"}), 404

    connection.execute(
        "UPDATE items SET status = 'sold' WHERE id = ?",
        (item_id,)
    )

    connection.commit()
    connection.close()

    return jsonify({"message": "Item marked as sold"})
@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    data = request.get_json()

    seller_id = data.get("seller_id")
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "").strip()
    item_condition = data.get("item_condition", "").strip()

    try:
        price = float(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a valid number"}), 400

    if not all([seller_id, title, description, category, item_condition]):
        return jsonify({"error": "All item details are required"}), 400

    connection = get_db_connection()

    item = connection.execute(
        "SELECT id FROM items WHERE id = ? AND seller_id = ?",
        (item_id, seller_id)
    ).fetchone()

    if item is None:
        connection.close()
        return jsonify({"error": "Item not found or you are not the seller"}), 404

    connection.execute("""
        UPDATE items
        SET title = ?, description = ?, category = ?,
            item_condition = ?, price = ?
        WHERE id = ?
    """, (title, description, category, item_condition, price, item_id))

    connection.commit()
    connection.close()

    return jsonify({"message": "Item updated successfully"})
@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    data = request.get_json()
    seller_id = data.get("seller_id")

    if not seller_id:
        return jsonify({"error": "Seller ID is required"}), 400

    connection = get_db_connection()

    item = connection.execute(
        "SELECT id FROM items WHERE id = ? AND seller_id = ?",
        (item_id, seller_id)
    ).fetchone()

    if item is None:
        connection.close()
        return jsonify({"error": "Item not found or you are not the seller"}), 404

    connection.execute(
        "DELETE FROM items WHERE id = ?",
        (item_id,)
    )

    connection.commit()
    connection.close()

    return jsonify({"message": "Item deleted successfully"})
if __name__ == "__main__":
    app.run(debug=True)