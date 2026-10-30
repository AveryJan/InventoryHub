import os
import tempfile
import unittest
from app import create_app

class InventoryApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": os.path.join(self.tmp.name, "test.db")})
        self.client = self.app.test_client()
        self.sample = {"sku": "A-01", "name": "Mouse", "category": "Devices", "quantity": 5, "price": 19.99}

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, data=None):
        return self.client.post("/api/items", json=data or self.sample)

    def test_health_and_frontend(self):
        self.assertEqual(self.client.get("/api/health").json["status"], "ok")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_crud_json_contract(self):
        created = self.create()
        self.assertEqual(created.status_code, 201)
        obj = created.json["data"]
        self.assertEqual(obj["price"], 19.99)
        self.assertEqual(self.client.get(f'/api/items/{obj["id"]}').json["data"]["sku"], "A-01")
        changed = self.client.patch(f'/api/items/{obj["id"]}', json={"quantity": 3})
        self.assertEqual(changed.json["data"]["quantity"], 3)
        self.assertEqual(self.client.delete(f'/api/items/{obj["id"]}').status_code, 204)
        self.assertEqual(self.client.get(f'/api/items/{obj["id"]}').status_code, 404)

    def test_validation_and_duplicate(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.create({**self.sample, "quantity": -3}).status_code, 400)
        self.assertEqual(self.create({**self.sample, "price": 1.234}).status_code, 400)
        self.assertEqual(self.create({**self.sample, "quantity": True}).status_code, 400)
        self.assertEqual(self.client.post("/api/items", data="hello", content_type="text/plain").status_code, 415)
        self.assertEqual(self.client.patch("/api/items/1", json={}).status_code, 400)

    def test_search_and_pagination(self):
        self.create()
        self.create({**self.sample, "sku": "B-02", "name": "Keyboard"})
        result = self.client.get("/api/items?search=key&page=1&limit=1").json
        self.assertEqual(result["meta"]["total"], 1)
        self.assertEqual(result["data"][0]["sku"], "B-02")
        self.assertEqual(self.client.get("/api/items?limit=101").status_code, 400)
        self.assertEqual(self.client.get("/api/items?search=%25").json["meta"]["total"], 0)

if __name__ == "__main__":
    unittest.main()
