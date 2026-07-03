# REST API

A dynamic REST API built with FastAPI and SQLite. Define your data schema in `schema.json` and the API automatically creates the database tables and full CRUD endpoints — no code changes required.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [Exposing with ngrok](#exposing-with-ngrok)
- [API Reference](#api-reference)
  - [Authentication](#authentication)
  - [System Endpoints](#system-endpoints)
  - [Dynamic CRUD Endpoints](#dynamic-crud-endpoints)
  - [Table Management](#table-management)
- [Schema Definition](#schema-definition)
- [Default Entities](#default-entities)
- [Browser UI](#browser-ui)

---

## Features

- **Schema-driven**: define tables in `schema.json` — routes and SQLite tables are created automatically on startup
- **Full CRUD**: GET (list + single), POST, PUT, PATCH, DELETE, and bulk upsert for every entity
- **Simple auth**: bearer token protects all write operations; reads are public
- **Dynamic table creation**: create new tables at runtime via `POST /tables`
- **Built-in browser UI**: served at `/ui/index.html`
- **Interactive docs**: Swagger UI at `/docs`, ReDoc at `/redoc`

---

## Prerequisites

- Python 3.10 or higher
- pip

---

## Installation

**1. Clone the repository**

```bash
git clone <repository-url>
cd rest-api
```

**2. (Recommended) Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Set up environment variables**

```bash
cp .env.example .env
```

Open `.env` and set a secure `API_TOKEN` before running the server:

```env
API_TOKEN=your-secret-token-here
DATABASE_URL=./data.db
PORT=3333
```

> **Important:** Never commit a real token. The `.env` file should be in your `.gitignore`.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `API_TOKEN` | *(required)* | Bearer token for all write operations |
| `DATABASE_URL` | `./data.db` | Path to the SQLite database file |
| `PORT` | `3333` | Port the server listens on |

---

## Running the Server

```bash
python -m app.main
```

Or using uvicorn directly (with auto-reload for development):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 3333 --reload
```

Once running, the server is accessible at:

| URL | Description |
|---|---|
| `http://localhost:3333/` | Redirects to browser UI |
| `http://localhost:3333/ui/index.html` | Browser UI |
| `http://localhost:3333/docs` | Swagger UI (interactive docs) |
| `http://localhost:3333/redoc` | ReDoc documentation |
| `http://localhost:3333/health` | Health check |

---

## Exposing with ngrok

ngrok creates a public HTTPS URL that tunnels traffic to your local server — useful for testing webhooks, sharing a local instance, or integrating with external services.

### Install ngrok from the Microsoft Store

1. Open the **Microsoft Store** on Windows
2. Search for **ngrok**
3. Click **Install**

Alternatively, install via `winget`:

```bash
winget install ngrok.ngrok
```

### Authenticate ngrok

Sign up at [https://ngrok.com](https://ngrok.com), then copy your auth token from the dashboard and run:

```bash
ngrok config add-authtoken <your-auth-token>
```

### Start a tunnel

Make sure the API server is already running on port `3333`, then:

```bash
ngrok http 3333
```

ngrok will display a forwarding URL such as:

```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:3333
```

Use that public URL as the base URL for all API requests. All endpoints, authentication, and the browser UI work identically over the ngrok tunnel.

---

## API Reference

### Authentication

Write operations require a bearer token in the `Authorization` header:

```
Authorization: Bearer <your-api-token>
```

| Operation | Auth required |
|---|---|
| GET (list, single) | No |
| POST, PUT, PATCH, DELETE | Yes |
| POST /tables | Yes |
| GET /health, /schema | No |

Responses:
- `401 Unauthorized` — token missing or incorrect
- `500 Internal Server Error` — `API_TOKEN` is not configured

---

### System Endpoints

#### Health check

```
GET /health
```

Response `200 OK`:
```json
{ "status": "ok" }
```

---

#### Get schema

Returns all entity definitions loaded from `schema.json`.

```
GET /schema
```

Response `200 OK`:
```json
[
  {
    "name": "customers",
    "fields": [
      { "name": "id",     "type": "text",    "required": true  },
      { "name": "name",   "type": "text",    "required": true  },
      { "name": "email",  "type": "text",    "required": false },
      { "name": "status", "type": "text",    "required": false }
    ]
  }
]
```

---

### Dynamic CRUD Endpoints

Every entity defined in `schema.json` gets the following endpoints automatically. Replace `{entity}` with the entity name (e.g. `customers`, `orders`).

Every record also includes an `updated_at` field (UTC ISO-8601 string) that is set automatically on every write.

---

#### List all records

```
GET /{entity}
```

Response `200 OK`:
```json
[
  { "id": "1", "name": "Acme Corp", "email": "info@acme.com", "status": "active", "updated_at": "2024-01-15T10:30:00" }
]
```

---

#### Get one record

```
GET /{entity}/{id}
```

Response `200 OK`:
```json
{ "id": "1", "name": "Acme Corp", "email": "info@acme.com", "status": "active", "updated_at": "2024-01-15T10:30:00" }
```

Response `404 Not Found` if the id does not exist.

---

#### Create a record

```
POST /{entity}
Authorization: Bearer <token>
Content-Type: application/json
```

Request body — include all required fields for the entity:
```json
{ "id": "1", "name": "Acme Corp", "email": "info@acme.com", "status": "active" }
```

Response `201 Created` — returns the created record.

Response `409 Conflict` if the id already exists.

---

#### Replace a record (full update)

```
PUT /{entity}/{id}
Authorization: Bearer <token>
Content-Type: application/json
```

Request body — provide all fields:
```json
{ "name": "Acme Corp Updated", "email": "new@acme.com", "status": "inactive" }
```

Response `200 OK` — returns the updated record.

Response `404 Not Found` if the id does not exist.

---

#### Update a record (partial update)

```
PATCH /{entity}/{id}
Authorization: Bearer <token>
Content-Type: application/json
```

Request body — provide only the fields to change:
```json
{ "status": "inactive" }
```

Response `200 OK` — returns the updated record.

Response `404 Not Found` if the id does not exist.

---

#### Delete a record

```
DELETE /{entity}/{id}
Authorization: Bearer <token>
```

Response `204 No Content` on success.

Response `404 Not Found` if the id does not exist.

---

#### Bulk upsert

Insert or update up to 5,000 records in a single request. Existing `id`s are updated; new `id`s are inserted.

```
POST /{entity}/bulk
Authorization: Bearer <token>
Content-Type: application/json
```

Request body:
```json
{
  "items": [
    { "id": "1", "name": "Acme Corp",  "email": "info@acme.com",  "status": "active"   },
    { "id": "2", "name": "Beta Ltd",   "email": "hello@beta.com", "status": "inactive" }
  ]
}
```

Response `200 OK`:
```json
{
  "inserted": 1,
  "updated":  1,
  "total":    2,
  "errors":   []
}
```

---

### Table Management

#### Create a new table

Adds a new entity to `schema.json` and creates the corresponding SQLite table. The new CRUD endpoints are available immediately without restarting the server.

```
POST /tables
Authorization: Bearer <token>
Content-Type: application/json
```

Request body:
```json
{
  "name": "products",
  "fields": [
    { "name": "id",       "type": "text",    "required": true  },
    { "name": "title",    "type": "text",    "required": true  },
    { "name": "price",    "type": "real",    "required": false },
    { "name": "quantity", "type": "integer", "required": false }
  ]
}
```

Supported field types: `text`, `real`, `integer`.

Response `200 OK` — returns the created entity definition.

---

## Schema Definition

The `schema.json` file is the source of truth for all entities. Edit it directly or use `POST /tables` to add new ones.

```json
[
  {
    "name": "entity_name",
    "fields": [
      { "name": "id",         "type": "text",    "required": true  },
      { "name": "field_name", "type": "text",    "required": false }
    ]
  }
]
```

- Every entity **must** include an `id` field — this is the primary key, always stored as `TEXT` in the database regardless of the type declared in the schema
- An `updated_at` column is added automatically to every table; do not define it in the schema
- Tables are created with `CREATE TABLE IF NOT EXISTS` on startup — existing tables are never altered

---

## Default Entities

The project ships with five entities pre-configured in `schema.json`:

### customers

| Field | Type | Required |
|---|---|---|
| id | text | Yes |
| name | text | Yes |
| email | text | No |
| status | text | No |

### orders

| Field | Type | Required |
|---|---|---|
| id | text | Yes |
| customer_id | text | Yes |
| amount | real | Yes |
| status | text | No |

### fact_billing

| Field | Type | Required |
|---|---|---|
| id | text | Yes |
| customerkey | integer | Yes |
| invoiceamount | integer | No |
| quantity | integer | No |
| billingdate | text | No |

### oscars

| Field | Type | Required |
|---|---|---|
| id | integer | Yes |
| film | text | No |
| year | text | No |
| award | text | No |
| nomination | integer | No |

### oscars1

| Field | Type | Required |
|---|---|---|
| id | integer | Yes |
| film | text | No |
| year | text | No |
| award | text | No |
| nomination | integer | No |

---

## Browser UI

A self-contained browser-based UI is served at `http://localhost:3333/ui/index.html` (the root `/` redirects there automatically). It lets you browse and interact with any entity without writing any API calls.
