
import os
import re
import sqlite3
import uuid
from decimal import Decimal

import requests
from dotenv import load_dotenv
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template_string,
    request,
    url_for,
)

load_dotenv()

payments = Blueprint("payments", __name__)

APP_ID = os.getenv("CASHFREE_APP_ID", "")
SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "")
API_VERSION = os.getenv("CASHFREE_API_VERSION", "2025-01-01")

if os.getenv("CASHFREE_MODE", "sandbox") == "sandbox":
    BASE_URL = "https://sandbox.cashfree.com/pg"
else:
    BASE_URL = "https://api.cashfree.com/pg"


# DEMO CATALOG ONLY:
# Replace this with a lookup from your existing product database.
PRODUCTS = {
    "book001": {"name": "Engineering Textbook", "price": Decimal("250.00")},
    "calc001": {"name": "Scientific Calculator", "price": Decimal("500.00")},
}


def db_path():
    # Keeps the demo database beside this Python file.
    return os.path.join(os.path.dirname(__file__), "payments.db")


def init_payment_db():
    with sqlite3.connect(db_path()) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                order_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                amount_paise INTEGER NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'PENDING'
            )
        """)


init_payment_db()


def cashfree_headers():
    return {
        "x-client-id": APP_ID,
        "x-client-secret": SECRET_KEY,
        "x-api-version": API_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def get_local_order(order_id):
    with sqlite3.connect(db_path()) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM payment_orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        return dict(row) if row else None


def get_gateway_order(order_id):
    response = requests.get(
        f"{BASE_URL}/orders/{order_id}",
        headers=cashfree_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def refresh_order_status(order_id):
    local_order = get_local_order(order_id)
    if not local_order:
        return None

    gateway_order = get_gateway_order(order_id)
    gateway_status = gateway_order.get("order_status", "PENDING")

    # Only mark paid when Cashfree reports the order as PAID.
    if gateway_status == "PAID":
        with sqlite3.connect(db_path()) as db:
            db.execute(
                """UPDATE payment_orders
                   SET payment_status = 'PAID'
                   WHERE order_id = ?""",
                (order_id,),
            )
        return "PAID"

    # Do not turn a pending order into paid from a browser callback.
    return local_order["payment_status"]


@payments.post("/api/payments/create-order")
def create_order():
    if not APP_ID or not SECRET_KEY:
        return jsonify({"error": "Cashfree credentials are not configured"}), 500

    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    phone = str(data.get("customer_phone", "")).strip()

    product = PRODUCTS.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    # Basic format validation for an Indian mobile number.
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        return jsonify({"error": "Enter a valid 10-digit mobile number"}), 400

    order_id = "cc_" + uuid.uuid4().hex[:24]
    amount = product["price"]
    amount_paise = int(amount * 100)

    return_url = (
        url_for("payments.payment_return", _external=True)
        + "?order_id={order_id}"
    )

    payload = {
        "order_id": order_id,
        "order_amount": float(amount),
        "order_currency": "INR",
        "customer_details": {
            "customer_id": "cc_" + uuid.uuid4().hex[:12],
            "customer_phone": phone,
        },
        "order_meta": {
            "return_url": return_url,
        },
        "order_note": "Campus Cart demo purchase",
    }

    try:
        response = requests.post(
            f"{BASE_URL}/orders",
            headers=cashfree_headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        current_app.logger.exception("Cashfree create-order request failed")
        return jsonify({
            "error": "Could not create a Cashfree order. Check server logs."
        }), 502

    session_id = result.get("payment_session_id")
    if not session_id:
        current_app.logger.error("Cashfree response has no payment_session_id")
        return jsonify({"error": "Invalid response from Cashfree"}), 502

    with sqlite3.connect(db_path()) as db:
        db.execute(
            """INSERT INTO payment_orders
               (order_id, product_id, amount_paise, payment_status)
               VALUES (?, ?, ?, 'PENDING')""",
            (order_id, product_id, amount_paise),
        )

    return jsonify({
        "order_id": order_id,
        "payment_session_id": session_id,
        "product_name": product["name"],
        "amount": float(amount),
        "currency": "INR",
    })


@payments.get("/api/payments/status/<order_id>")
def payment_status(order_id):
    local_order = get_local_order(order_id)
    if not local_order:
        return jsonify({"error": "Order not found"}), 404

    try:
        status = refresh_order_status(order_id)
    except requests.RequestException:
        current_app.logger.exception("Cashfree status check failed")
        return jsonify({
            "order_id": order_id,
            "status": local_order["payment_status"],
            "message": "Unable to refresh status; please retry.",
        }), 502

    return jsonify({
        "order_id": order_id,
        "status": status or "PENDING",
    })


@payments.get("/payment/return")
def payment_return():
    order_id = request.args.get("order_id", "")

    # Never trust the return URL alone as proof of payment.
    local_order = get_local_order(order_id)
    if not local_order:
        return "Order not found", 404

    try:
        status = refresh_order_status(order_id) or "PENDING"
    except requests.RequestException:
        current_app.logger.exception("Cashfree return status check failed")
        status = "PENDING"

    return render_template_string("""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Campus Cart Payment Status</title>
        </head>
        <body>
          <h1>Campus Cart</h1>
          <h2>Payment status: {{ status }}</h2>
          <p>Order ID: {{ order_id }}</p>
          {% if status == "PAID" %}
            <p>Cashfree confirms this order as paid.</p>
          {% else %}
            <p>Payment is not confirmed yet. Refresh this page or check
               your order status later.</p>
          {% endif %}
          <a href="/">Return to Campus Cart</a>
        </body>
        </html>
    """, status=status, order_id=order_id)
