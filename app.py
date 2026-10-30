import os
import sqlite3
from contextlib import contextmanager
from flask import Flask, jsonify, request, send_from_directory

def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.update(DATABASE=os.environ.get("INVENTORY_DB", os.path.join(app.instance_path, "inventory.db")),
                      MAX_CONTENT_LENGTH=64 * 1024)
    if test_config:
        app.config.update(test_config)
    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)

    @contextmanager
    def db():
        conn = sqlite3.connect(app.config["DATABASE"], timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            quantity INTEGER NOT NULL CHECK(quantity >= 0),
            price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_items_name ON items(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category)")

    def fail(message, status, details=None):
        payload = {"error": {"code": status, "message": message}}
        if details:
            payload["error"]["details"] = details
        return jsonify(payload), status

    def serialize(row):
        data = dict(row)
        data["price"] = round(data.pop("price_cents") / 100, 2)
        return data

    def validated(body, partial=False):
        if not isinstance(body, dict):
            return None, "Expected a JSON object"
        allowed = {"sku", "name", "category", "quantity", "price"}
        if set(body) - allowed:
            return None, "Unknown field(s): " + ", ".join(sorted(set(body) - allowed))
        if not partial and not {"sku", "name", "quantity", "price"}.issubset(body):
            return None, "Required fields: sku, name, quantity, price"
        if partial and not body:
            return None, "Supply at least one field"
        result = {}
        for key in ("sku", "name", "category"):
            if key in body:
                value = body[key]
                if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
                    return None, f"{key} must be nonempty text (maximum 120 characters)"
                result[key] = value.strip()
        if "quantity" in body:
            if type(body["quantity"]) is not int or body["quantity"] < 0:
                return None, "quantity must be a nonnegative integer"
            result["quantity"] = body["quantity"]
        if "price" in body:
            value = body["price"]
            if type(value) not in (int, float) or not 0 <= value <= 10000000:
                return None, "price must be a nonnegative number"
            cents = round(value * 100)
            if abs(value * 100 - cents) > 1e-6:
                return None, "price supports at most two decimal places"
            result["price_cents"] = cents
        if not partial and "category" not in result:
            result["category"] = "General"
        return result, None

    @app.get("/")
    def home():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "InventoryHub"})

    @app.get("/api/items")
    def list_items():
        try:
            page = int(request.args.get("page", 1))
            limit = int(request.args.get("limit", 10))
        except ValueError:
            return fail("page and limit must be integers", 400)
        if page < 1 or limit < 1 or limit > 100:
            return fail("page must be >= 1 and limit must be 1–100", 400)
        term = request.args.get("search", "").strip()
        if len(term) > 120:
            return fail("search must be at most 120 characters", 400)
        with db() as conn:
            # Escape wildcard characters so user search is literal.
            pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            clause = "WHERE name LIKE ? ESCAPE '\\' OR sku LIKE ? ESCAPE '\\'"
            params = (pattern, pattern)
            total = conn.execute(f"SELECT COUNT(*) FROM items {clause}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM items {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, (page - 1) * limit)
            ).fetchall()
        return jsonify({"data": [serialize(row) for row in rows],
                        "meta": {"page": page, "limit": limit, "total": total,
                                 "pages": (total + limit - 1) // limit}})

    @app.get("/api/items/<int:item_id>")
    def get_item(item_id):
        with db() as conn:
            row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return jsonify({"data": serialize(row)}) if row else fail("Item not found", 404)

    @app.post("/api/items")
    def add_item():
        if not request.is_json:
            return fail("Content-Type must be application/json", 415)
        data, error = validated(request.get_json(silent=True))
        if error:
            return fail(error, 400)
        try:
            with db() as conn:
                cursor = conn.execute(
                    "INSERT INTO items(sku,name,category,quantity,price_cents) VALUES (?,?,?,?,?)",
                    tuple(data[k] for k in ("sku", "name", "category", "quantity", "price_cents"))
                )
                row = conn.execute("SELECT * FROM items WHERE id=?", (cursor.lastrowid,)).fetchone()
        except sqlite3.IntegrityError:
            return fail("SKU already exists", 409)
        return jsonify({"data": serialize(row)}), 201

    @app.patch("/api/items/<int:item_id>")
    def edit_item(item_id):
        if not request.is_json:
            return fail("Content-Type must be application/json", 415)
        data, error = validated(request.get_json(silent=True), partial=True)
        if error:
            return fail(error, 400)
        try:
            with db() as conn:
                row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
                if row is None:
                    return fail("Item not found", 404)
                changes = ", ".join(f"{key}=?" for key in data)
                conn.execute(
                    f"UPDATE items SET {changes}, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                    (*data.values(), item_id)
                )
                result = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        except sqlite3.IntegrityError:
            return fail("SKU already exists", 409)
        return jsonify({"data": serialize(result)})

    @app.delete("/api/items/<int:item_id>")
    def delete_item(item_id):
        with db() as conn:
            cursor = conn.execute("DELETE FROM items WHERE id=?", (item_id,))
            if cursor.rowcount == 0:
                return fail("Item not found", 404)
        return "", 204

    @app.errorhandler(413)
    def too_large(_):
        return fail("Request body is too large", 413)

    return app

app = create_app()
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
