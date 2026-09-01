# Sales Monitoring — Django Backend

REST API backing the `sales-monitoring` React frontend (A.M.C. Agency sales
monitoring system). Django 5 + Django REST Framework + JWT auth, SQLite storage.

It exposes every collection the frontend keeps in `localStorage` (see
`src/lib/store.ts`) as a real REST endpoint, with the same field names as
`src/lib/types.ts`.

## Quick start

```bash
cd sales-monitoring-backend

# 1. Create a virtualenv and install dependencies
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate    # macOS / Linux
pip install -r requirements.txt

# 2. Configure environment (optional — sensible defaults are built in)
copy .env.example .env        # Windows   (cp on macOS/Linux)

# 3. Create the database schema
python manage.py migrate

# 4. Load demo data (same data the frontend mocks)
python manage.py seed_data

# 5. Run the server
python manage.py runserver
```

API base: `http://127.0.0.1:8000/api/`
Interactive docs (Swagger): `http://127.0.0.1:8000/api/docs/`
Django admin: `http://127.0.0.1:8000/admin/` (log in as `admin@amc.com` / `demo123`)

## Authentication

JWT via `djangorestframework-simplejwt`. Log in, then send
`Authorization: Bearer <access>` on every request.

| Method | Endpoint            | Body                              | Returns                          |
|--------|---------------------|-----------------------------------|----------------------------------|
| POST   | `/api/auth/login/`  | `{ "email", "password" }`         | `{ access, refresh, user }`      |
| POST   | `/api/auth/refresh/`| `{ "refresh" }`                   | `{ access }`                     |
| GET    | `/api/auth/me/`     | —                                 | current user + permission map    |

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@amc.com","password":"demo123"}'
```

### Demo accounts (all password `demo123`)

| Email                | Role              |
|----------------------|-------------------|
| admin@amc.com        | Super Admin       |
| manager@amc.com      | Sales Manager     |
| area@amc.com         | Area Manager      |
| sr@amc.com           | Sales Officer     |
| warehouse@amc.com    | Warehouse Manager |
| accounts@amc.com     | Accountant        |

## Collections

Each is a full CRUD endpoint under `/api/` with pagination, search (`?search=`),
filtering (`?field=value`), and ordering (`?ordering=field`). Field names match
the frontend types exactly.

| Endpoint                | Frontend collection | Model         |
|-------------------------|---------------------|---------------|
| `/api/products/`        | products            | Product       |
| `/api/shops/`           | shops               | Shop          |
| `/api/sales/`           | sales               | SalesOrder    |
| `/api/offers/`          | offers              | Offer         |
| `/api/offer-accruals/`  | offerAccruals       | OfferAccrual  |
| `/api/salesmen/`        | salesmen            | Salesman      |
| `/api/attendance/`      | attendance          | Attendance    |
| `/api/ledger/`          | ledger              | LedgerEntry   |
| `/api/visits/`          | visits              | Visit         |
| `/api/payments/`        | payments            | Payment       |
| `/api/cashback-txns/`   | cashbackTxns        | CashbackTxn   |
| `/api/auth/users/`      | users               | User          |

### Pagination

Responses are paginated: `{ count, next, previous, results }`. Use
`?page=2&page_size=50`, or `?page_size=all` to fetch a whole collection at once
(the shape the localStorage frontend expects when hydrating a table).

## Role permissions

Writes/deletes are enforced by the same role matrix as the frontend
(`accounts/permissions.py`, mirroring `PERMS` in `src/lib/auth.tsx`). Reads are
open to any authenticated user. Example: an `Accountant` may only write the
`accounting` (ledger) module; a `Warehouse Manager` only `products`.

## Python version

Use Python 3.10 - 3.14. On **Python 3.14 you must be on Django 5.2 or newer**;
Django 5.0.x dies rendering any template with

    AttributeError: 'super' object has no attribute 'dicts'

which takes down the entire Django admin. `requirements.txt` pins `Django>=5.2`
for this reason. If the admin breaks again, check the installed version first:

```bash
python -m django --version
```

A stray system-wide Django (rather than the venv's) is the usual cause.

## Tests

```bash
python manage.py test
```

The suite in `core/tests.py` covers login for every role, read access, the
permission matrix, and - most importantly - the **multi-collection workflows**.
One invoice is six API calls; one payment is five. The tests replay exactly what
the React app sends and assert that a role which may start a workflow can finish
it, so a future permission tweak can't silently reintroduce half-written sales.

## Permissions

`accounts/permissions.py` holds two matrices:

- `PERMS` - what a role may deliberately edit. Mirrors `PERMS` in
  `src/lib/auth.tsx`; keep the two in sync.
- `DERIVED` - what a role's workflows necessarily touch. Selling implies posting
  to the ledger and decrementing stock, so sellers get *narrow* write access to
  those collections: `FIELD_LIMITS` caps which fields may change (a Sales
  Officer may move `Product.stock` but never `Product.price`), and stock and
  shop balances can never be deleted as a side effect.

## Wiring to the React frontend

Already wired. The frontend talks to this API through `src/lib/api.ts` (JWT
storage, refresh-on-401) and `src/lib/store.ts` (hydrates each collection from
`/api/<endpoint>/?page_size=all`, writes back optimistically). Point it at the
server with `VITE_API_URL` in `sales-monitoring/.env`.

## Notes

- Money fields are stored as `Decimal` and returned as JSON numbers (not strings).
- `Attendance` renames the reserved words `in`/`out` (kept internally as
  `check_in`/`check_out`) back to `in`/`out` in the JSON.
- Switch to PostgreSQL later by changing only the `DATABASES` block in
  `config/settings.py`.
