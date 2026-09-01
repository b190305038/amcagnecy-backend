# Sales Monitoring — Production Deployment & Audit

_Full review of the Django backend and React frontend, changes applied for a
production server (MySQL), and a step-by-step deploy guide._

---

## 1. Audit summary

Both codebases are in good shape. The architecture is clean and the logic is
sound — the gaps were all in **configuration/hardening**, not application code.

**Backend (Django 5.2 + DRF + SimpleJWT)** — well structured: email-based custom
user, role/module permission matrix mirrored on both ends, 20+ REST viewsets,
pagination, filtering, OpenAPI schema. No logic bugs found. `manage.py check`
passes; no pending migrations.

**Frontend (React 19 + Vite + TS)** — fully API-backed store with optimistic
writes and token refresh. `tsc --noEmit` passes with zero errors.

### Issues found and fixed

| # | Area | Issue | Status |
|---|------|-------|--------|
| 1 | CORS | Allowed-origins default only listed port **5173**; Vite had hopped to **5174**, causing the `No 'Access-Control-Allow-Origin'` login error | **Fixed** — defaults now cover 5173–5175 + env override |
| 2 | Database | SQLite only | **Fixed** — MySQL via env (`DB_ENGINE=mysql`), SQLite kept for dev |
| 3 | Security | `DEBUG` on, no HTTPS redirect, no HSTS, cookies not `Secure` | **Fixed** — full security block applied when `DEBUG=False` |
| 4 | Secrets | Insecure default `SECRET_KEY`; no CSRF trusted origins | **Fixed** — env-driven; `.env.example` documents generation |
| 5 | Static | No production static serving | **Fixed** — WhiteNoise (admin/DRF assets) |
| 6 | Serving | No WSGI app server | **Fixed** — `gunicorn` added |

### Recommended before go-live (not code-breaking, your call)

- `accounts/serializers.py` defaults new users to password `demo123`, and
  `set_password` allows 4-char passwords. Fine for the demo; raise the minimum
  and drop the default before real users exist.
- `CompanySettingsViewSet.get_queryset()` writes a row on every access (harmless,
  but it makes drf-spectacular noisy). Optional cleanup only.
- SimpleJWT has no refresh-token blacklist, so logout is client-side only. Add
  `rest_framework_simplejwt.token_blacklist` if server-side revocation matters.

---

## 2. What changed in this pass

**`config/settings.py`**
- Env-driven `DATABASES` — MySQL (PyMySQL driver, `utf8mb4`, strict mode) or SQLite.
- WhiteNoise middleware + compressed-manifest static storage.
- CORS defaults widened to 5173–5175; `CSRF_TRUSTED_ORIGINS` added.
- Production security block (SSL redirect, HSTS, secure cookies, nosniff, frame deny) — active only when `DEBUG=False`.

**`requirements.txt`** — added `PyMySQL`, `whitenoise`, `gunicorn`.

**`.env.example`** (backend) — full production template (DB, hosts, CORS/CSRF, HTTPS, JWT).

**`.env.example`** (frontend) — documents the production `VITE_API_URL`.

No application logic was modified.

---

## 3. Deploy the backend (Ubuntu + nginx + gunicorn + MySQL)

### 3.1 MySQL
```bash
sudo apt install mysql-server
sudo mysql
```
```sql
CREATE DATABASE sales_monitoring CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sales_user'@'localhost' IDENTIFIED BY 'amcagency2026!@';
GRANT ALL PRIVILEGES ON sales_monitoring.* TO 'sales_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3.2 App
```bash
cd /var/www/sales-monitoring-backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then edit .env (see below)
python manage.py migrate
python manage.py createsuperuser        # or: python manage.py seed_data
python manage.py collectstatic --noinput
```

### 3.3 `.env` (production values)
```
SECRET_KEY=<paste output of: python -c "from django.core.management.utils import get_random_secret_key as k; print(k())">
DEBUG=False
ALLOWED_HOSTS=sales.ibitltd.com
DB_ENGINE=mysql
DB_NAME=sales_monitoring
DB_USER=sales_user
DB_PASSWORD=STRONG_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306
CORS_ALLOWED_ORIGINS=https://sales.ibitltd.com
CSRF_TRUSTED_ORIGINS=https://sales.ibitltd.com
SECURE_SSL_REDIRECT=True
```

### 3.4 Gunicorn (systemd `/etc/systemd/system/sales-api.service`)
```ini
[Unit]
Description=Sales Monitoring API
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/sales-monitoring-backend
EnvironmentFile=/var/www/sales-monitoring-backend/.env
ExecStart=/var/www/sales-monitoring-backend/venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now sales-api
```

### 3.5 nginx (TLS via certbot)
```nginx
server {
    server_name sales.ibitltd.com;

    location /api/    { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }
    location /admin/  { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }
    location /static/ { proxy_pass http://127.0.0.1:8000; }

    location / {                      # React build
        root /var/www/sales-monitoring/dist;
        try_files $uri /index.html;
    }
}
```
`X-Forwarded-Proto` matters: the settings trust it (`SECURE_PROXY_SSL_HEADER`) so
Django knows the request arrived over HTTPS.

---

## 4. Deploy the frontend

```bash
cd /var/www/sales-monitoring
printf 'VITE_API_URL=https://sales.ibitltd.com/api\n' > .env.production
npm install
npm run build          # outputs dist/
```
Serve `dist/` via the nginx `location /` block above.

> Note: the `@rollup/rollup-linux-x64-gnu` error only appears when a Windows
> `node_modules` is reused on Linux. A fresh `npm install` on the target OS fixes
> it — it is not a code problem (`tsc --noEmit` passes clean).

---

## 5. Moving existing SQLite data to MySQL (optional)

Fresh install? Skip this — just `migrate` + `seed_data`. To carry over current
records:
```bash
# with the OLD sqlite config active:
python manage.py dumpdata --natural-primary --natural-foreign \
  -e contenttypes -e auth.permission > data.json
# switch .env to DB_ENGINE=mysql, then:
python manage.py migrate
python manage.py loaddata data.json
```

---

## 6. Verification done in this pass
- `manage.py check` (dev, SQLite) → no issues.
- `manage.py check --deploy` (prod, MySQL, DEBUG=False) → no security warnings.
- `collectstatic` under WhiteNoise → 154 files, OK.
- `makemigrations --check` → no missing migrations.
- Frontend `tsc --noEmit` → 0 errors.
