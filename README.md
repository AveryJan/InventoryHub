# InventoryHub

A complete, lightweight inventory-management web app built with **Flask**, **SQLite**, and **vanilla JavaScript**. It demonstrates front-end/back-end integration, consistent JSON contracts, graceful error handling, and performance-aware patterns.

## Features
- Create, view, update, and delete inventory products.
- Search by product name or SKU, with server-side pagination.
- Validated JSON payloads and predictable HTTP status codes.
- Responsive UI with loading/error feedback and safe DOM rendering.
- SQLite transactions, database indexes, integer-cent prices, and parameterized SQL.
- Client search debouncing (250 ms) and cancellation of outdated GET requests.
- Automated API tests using Python's standard-library `unittest`.

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

The SQLite database is created automatically in `instance/inventory.db`.
Optional: set `INVENTORY_DB` to change its path.

## Tests

```bash
python -m unittest discover -s tests -v
```

## JSON API

All successful item reads return an object with a `data` key.

| Method | Endpoint | Purpose | Success |
|---|---|---|---|
| GET | `/api/health` | Health check | 200 |
| GET | `/api/items?search=&page=1&limit=10` | Search and list items | 200 |
| GET | `/api/items/{id}` | Retrieve an item | 200 |
| POST | `/api/items` | Create an item | 201 |
| PATCH | `/api/items/{id}` | Update supplied fields | 200 |
| DELETE | `/api/items/{id}` | Delete an item | 204 |

Create request:
```json
{"sku":"SKU-1001","name":"Wireless Mouse","category":"Accessories","quantity":12,"price":24.99}
```

Create response (`201`):
```json
{"data":{"id":1,"sku":"SKU-1001","name":"Wireless Mouse","category":"Accessories","quantity":12,"price":24.99,"updated_at":"2026-10-30T00:00:00.000Z"}}
```

List response:
```json
{"data":[],"meta":{"page":1,"limit":10,"total":0,"pages":0}}
```

Error response:
```json
{"error":{"code":409,"message":"SKU already exists"}}
```

## Architecture

`Browser → fetch() → Flask JSON endpoints → SQLite`

The browser calls relative `/api/...` paths, so same-origin development avoids unnecessary cross-origin configuration. Flask validates incoming JSON, runs parameterized SQL, and returns standardized envelopes. The front end renders results without injecting untrusted HTML.

## Debugging and optimizations

1. **Integration:** Centralized `api()` wrapper sets JSON headers and handles response parsing and non-2xx codes. 
2. **Bug prevention:** Explicit checks for missing records, duplicate SKUs, invalid quantities, bad prices, malformed request bodies, and HTTP 204 without JSON.
3. **Contracts:** Data is returned inside `data`; list pagination inside `meta`; errors inside `error`.
4. **Performance:** Indexed lookup fields, query-level LIMIT/OFFSET pagination, 250 ms debounced search, and `AbortController` to discard stale requests.
5. **Verification:** `unittest` API coverage for CRUD, validation, duplicate handling, search, and paging.

For very large inventories, keyset pagination and a dedicated database server would be sensible next steps. This is a local-demo application, not a production-authenticated multi-user system.

## Copilot reflection — adapt to your actual process

The course asks you to reflect on **your use of Microsoft Copilot**. This starter project was generated with AI assistance in ChatGPT, **not verified as developed with Microsoft Copilot**. Do not claim Microsoft Copilot usage unless you personally used it.

A truthful sample reflection to adapt *after* working through the activities using Copilot:

> I used Microsoft Copilot to explore the responsibilities of the front-end `fetch` layer and the Flask API, then reviewed and refined the generated integration code to align endpoints and response shapes. I used Copilot suggestions to reason about common integration bugs, including missing content types, invalid payloads, duplicate SKUs, and delete responses with no body. I defined consistent JSON `data`, `meta`, and `error` wrappers and verified how they were handled in the UI and API tests. For performance, I evaluated Copilot suggestions such as paginated SQL queries, indexes, debounced searching, and canceling stale requests. I kept responsibility for validating, testing, and accepting every suggested change.

You should revise this to describe only steps you actually performed with Copilot and add concrete screenshots/prompts or commit references where available.

## Suggested GitHub submission

Repository name: `InventoryHub`

In GitHub select **New repository → Public → Create repository**, then upload the contents of this folder (not just the ZIP), commit, and copy the resulting URL. Confirm README, source files, and tests are visible.

## Scope and security

This demo has no authentication, authorization, audit logging, CSRF protection, or production deployment configuration. Do not deploy it publicly with write access or real business data without adding these protections.
