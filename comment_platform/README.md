# Comment Platform API

FastAPI backend for the embeddable comment platform.

## Project Structure

```
comment_platform/
├── app/
│   ├── main.py                  # FastAPI app, middleware, lifespan
│   ├── api/
│   │   ├── deps.py              # Auth dependencies (get_current_user)
│   │   └── v1/
│   │       ├── router.py        # Registers all endpoint routers
│   │       └── endpoints/
│   │           ├── auth.py      # Register, login, refresh, logout, profile
│   │           ├── websites.py  # Website CRUD + API key rotation
│   │           ├── comments.py  # Public comment API (uses api_key)
│   │           ├── moderation.py# Approve/reject/delete comments
│   │           ├── billing.py   # Plans, subscription, invoices
│   │           └── analytics.py # Usage stats and summaries
│   ├── core/
│   │   ├── config.py            # Settings via pydantic-settings
│   │   └── security.py          # JWT, password hashing
│   ├── db/
│   │   └── session.py           # Async SQLAlchemy engine + get_db
│   ├── models/
│   │   ├── __init__.py
│   │   ├── auth_billing.py      # SuperUser, Session, AuditLog, Plan, Subscription, Invoice
│   │   └── core_moderation_analytics.py  # Website, Thread, Comment, Vote, Moderation, Analytics
│   └── schemas/
│       ├── auth.py              # Register/login/token Pydantic schemas
│       └── core.py              # Website/thread/comment Pydantic schemas
├── tests/
│   └── test_basic.py
├── requirements.txt
└── .env.example
```

## Setup

### 1. Clone and install dependencies

```bash
cd comment_platform
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your database credentials and secret key
```

### 3. Set up database

Make sure PostgreSQL is running and the database exists, then run the bootstrap SQL:

```bash
psql -U postgres -d comment_platform -f bootstrap_safe.sql
```

### 4. Run the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the API docs

- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc

---

## API Overview

### Authentication (JWT Bearer)

| Method | Endpoint                          | Description              |
|--------|-----------------------------------|--------------------------|
| POST   | `/api/v1/auth/register`           | Create account           |
| POST   | `/api/v1/auth/login`              | Get access + refresh tokens |
| POST   | `/api/v1/auth/refresh`            | Refresh access token     |
| POST   | `/api/v1/auth/logout`             | Invalidate session       |
| GET    | `/api/v1/auth/me`                 | Get current user         |
| PATCH  | `/api/v1/auth/me`                 | Update profile           |
| POST   | `/api/v1/auth/change-password`    | Change password          |
| GET    | `/api/v1/auth/verify-email/{token}` | Verify email           |

### Websites

| Method | Endpoint                               | Description           |
|--------|----------------------------------------|-----------------------|
| POST   | `/api/v1/websites`                     | Create website        |
| GET    | `/api/v1/websites`                     | List my websites      |
| GET    | `/api/v1/websites/{id}`                | Get website           |
| PATCH  | `/api/v1/websites/{id}`                | Update website        |
| DELETE | `/api/v1/websites/{id}`                | Soft-delete website   |
| POST   | `/api/v1/websites/{id}/rotate-keys`    | Rotate API keys       |

### Public Comment API (used by embeddable widget)

| Method | Endpoint                                              | Description              |
|--------|-------------------------------------------------------|--------------------------|
| GET    | `/api/v1/comments/{api_key}/threads/{identifier}`     | Get/create thread        |
| GET    | `/api/v1/comments/{api_key}/threads/{identifier}/comments` | List published comments |
| POST   | `/api/v1/comments/{api_key}/threads/{identifier}/comments` | Post a comment     |
| PATCH  | `/api/v1/comments/{api_key}/comments/{id}`            | Edit a comment           |
| POST   | `/api/v1/comments/{api_key}/comments/{id}/vote`       | Vote on a comment        |

### Moderation

| Method | Endpoint                                                   | Description          |
|--------|------------------------------------------------------------|----------------------|
| GET    | `/api/v1/moderation/{website_id}/pending`                  | List pending comments |
| POST   | `/api/v1/moderation/{website_id}/comments/{id}/action`     | Approve/reject/spam  |
| DELETE | `/api/v1/moderation/{website_id}/comments/{id}`            | Delete comment       |
| GET    | `/api/v1/moderation/{website_id}/reports`                  | List user reports    |

### Billing

| Method | Endpoint                     | Description           |
|--------|------------------------------|-----------------------|
| GET    | `/api/v1/billing/plans`      | List all active plans |
| GET    | `/api/v1/billing/plans/{slug}` | Get a plan          |
| GET    | `/api/v1/billing/subscription` | My subscription     |
| GET    | `/api/v1/billing/invoices`   | My invoices           |

### Analytics

| Method | Endpoint                                    | Description         |
|--------|---------------------------------------------|---------------------|
| GET    | `/api/v1/analytics/usage`                   | Daily API usage     |
| GET    | `/api/v1/analytics/websites/{id}/stats`     | Website stats       |
| GET    | `/api/v1/analytics/summary`                 | 30-day summary      |

---

## Running Tests

```bash
pytest tests/ -v
```
