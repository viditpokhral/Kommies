# Kommies - System Architecture

**Version:** 1.0.0  
**Last Updated:** February 16, 2026

## Table of Contents

1. [High-Level Overview](#high-level-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Components](#components)
5. [Data Flow](#data-flow)
6. [Database Schema](#database-schema)
7. [API Architecture](#api-architecture)
8. [Authentication & Security](#authentication--security)
9. [Deployment](#deployment)

---

## High-Level Overview

**Kommies** is an embeddable comment platform consisting of:
- **FastAPI Backend** (`/api`) - RESTful API for comment management, authentication, and billing
- **Django Admin** (`/backend`) - Management dashboard and admin interface
- **Shared Database** - PostgreSQL database managed by Django models but used by both systems

The system allows websites to embed a comment widget and provides comprehensive moderation, analytics, and billing features.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Websites (Frontend Clients)                   │
└────────────────┬────────────────────────────────────────┬────────┘
                 │                                        │
         (embed comment widget)                (admin dashboard)
                 │                                        │
    ┌────────────▼─────────────┐        ┌────────────────▼────────┐
    │   FastAPI Backend        │        │   Django Admin Backend  │
    │   (Port 8000)            │        │   (Port 8001)           │
    │ - Auth endpoints         │        │ - Dashboard UI          │
    │ - Comment management     │        │ - Moderation interface  │
    │ - Billing/Plans          │        │ - Analytics views       │
    │ - Public API             │        │ - Settings management   │
    └────────────┬─────────────┘        └────────────┬────────────┘
                 │                                   │
                 └───────────────────┬────────────────┘
                                     │
                          (Shared PostgreSQL DB)
                                     │
                    ┌────────────────▼────────────────┐
                    │   PostgreSQL Database            │
                    │ - Auth & Billing models          │
                    │ - Core platform models           │
                    │ - Moderation & Analytics data    │
                    └─────────────────────────────────┘
```

---

## Technology Stack

### Backend
- **Framework**: FastAPI (async Python web framework)
- **ORM**: SQLAlchemy (with async support)
- **Database**: PostgreSQL 12+
- **Auth**: JWT-based authentication with refresh tokens
- **Admin Dashboard**: Django + django-admin-interface

### Development
- **Package Manager**: Poetry (dependency management via `pyproject.toml`)
- **Python Version**: >= 3.13
- **Server**: Uvicorn (ASGI server)
- **Containerization**: Docker & Docker Compose

### Key Dependencies
```
FastAPI >= 0.128.5
SQLAlchemy >= 2.0.46
Uvicorn >= 0.40.0
Starlette >= 0.52.1
Django >= 6.0.2
Psycopg >= 3.3.2
```

---

## Project Structure

```
kommies/
│
├── api/                          # FastAPI Application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app instance, middleware, lifespan
│   │   ├── api/
│   │   │   ├── deps.py          # Dependency injection (get_current_user, etc.)
│   │   │   └── v1/
│   │   │       ├── router.py    # V1 router aggregator
│   │   │       └── endpoints/
│   │   │           ├── auth.py              # Register, login, refresh, logout, profile
│   │   │           ├── websites.py         # Website CRUD, API key rotation
│   │   │           ├── comments.py         # Public comment submission (api_key auth)
│   │   │           ├── moderation.py       # Approve/reject/delete comments
│   │   │           ├── billing.py          # Plans, subscriptions, invoices
│   │   │           └── analytics.py        # Usage stats and summaries
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings (env vars)
│   │   │   └── security.py      # JWT encoding/decoding, password hashing
│   │   ├── db/
│   │   │   └── session.py       # Async SQLAlchemy engine, session factory
│   │   ├── middleware/
│   │   │   └── __init__.py      # Custom middleware (if any)
│   │   ├── models/
│   │   │   ├── auth_billing.py  # SuperUser, Session, Plan, Subscription, Invoice, AuditLog
│   │   │   └── core_moderation_analytics.py  # Website, Thread, Comment, Vote, Moderation, Analytics
│   │   └── schemas/
│   │       ├── auth.py          # Pydantic schemas (RegisterRequest, TokenResponse, etc.)
│   │       └── core.py          # Pydantic schemas (WebsiteResponse, CommentCreate, etc.)
│   ├── services/
│   │   ├── email.py             # Email notifications (SMTP)
│   │   ├── spam.py              # Spam detection & filtering
│   │   └── webhooks.py          # Webhook dispatch
│   ├── tests/
│   │   └── test_basic.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── backend/                      # Django Admin Dashboard
│   ├── apps/                    # Django apps
│   ├── config/                  # Django settings
│   ├── templates/               # Django HTML templates
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── docker-compose.yml           # Docker Compose configuration
├── pyproject.toml              # Poetry project metadata
├── poetry.lock                 # Locked dependencies
├── ARCHITECTURE.md             # This file
└── README.md                   # Project overview
```

---

## Components

### 1. **FastAPI Backend** (`/api/app`)

#### Main Application (`main.py`)
- Initializes FastAPI instance with Uvicorn
- Configures CORS middleware
- Adds request timing middleware
- Sets up global exception handler
- Lifespan hooks for startup/shutdown

#### API Routes

**Authentication** (`auth.py`)
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login (returns JWT tokens)
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout (revoke tokens)
- `GET /api/v1/auth/profile` - Get current user profile

**Websites** (`websites.py`)
- `POST /api/v1/websites` - Create new website
- `GET /api/v1/websites` - List user's websites
- `GET /api/v1/websites/{site_id}` - Get website details
- `PUT /api/v1/websites/{site_id}` - Update website
- `DELETE /api/v1/websites/{site_id}` - Delete website
- `POST /api/v1/websites/{site_id}/rotate-key` - Rotate API key

**Comments** (`comments.py`)
- `POST /api/v1/comments` - Submit new comment (public, requires api_key)
- `GET /api/v1/comments` - List comments (requires api_key)
- `GET /api/v1/comments/{id}` - Get single comment

**Moderation** (`moderation.py`)
- `POST /api/v1/moderation/approve/{id}` - Approve comment
- `POST /api/v1/moderation/reject/{id}` - Reject comment
- `DELETE /api/v1/moderation/delete/{id}` - Delete comment
- `GET /api/v1/moderation/queue` - Get moderation queue

**Billing** (`billing.py`)
- `GET /api/v1/billing/plans` - List available plans
- `POST /api/v1/billing/subscribe` - Subscribe to plan
- `GET /api/v1/billing/invoices` - Get user invoices
- `GET /api/v1/billing/usage` - Get current usage stats

**Analytics** (`analytics.py`)
- `GET /api/v1/analytics/summary` - Overall analytics summary
- `GET /api/v1/analytics/comments` - Comment statistics
- `GET /api/v1/analytics/top-commenters` - Top user rankings

#### Core Components

**Security** (`core/security.py`)
- JWT token generation and validation
- Password hashing with bcrypt
- Token expiration management

**Config** (`core/config.py`)
- Environment variable management via Pydantic Settings
- Database URL configuration
- CORS allowed origins
- Email/SMTP settings
- Rate limiting configuration

**Database Session** (`db/session.py`)
- Async SQLAlchemy engine creation
- Session factory for dependency injection
- Connection pooling

**Dependencies** (`api/deps.py`)
- `get_current_user()` - Dependency for JWT authentication
- `get_db()` - Dependency for database session
- `get_api_key()` - Dependency for API key validation

#### Models & Schemas

**Models** (`models/`)
- Auth & Billing: SuperUser, Session, Plan, Subscription, Invoice, AuditLog
- Core: Website, Thread, Comment, Vote, ModerationQueue, Analytics

**Schemas** (`schemas/`)
- Pydantic validation schemas for request/response serialization

### 2. **Django Admin Backend** (`/backend`)

#### Features
- Django admin interface with custom theme (django-admin-interface)
- Read-only models synced from FastAPI database
- Dashboard with:
  - Website overview
  - Moderation queue
  - Analytics charts
  - Subscription management
  - API connectivity testing

#### Models (Unmanaged)
- Read existing database models created by FastAPI
- SuperUser, Website, Thread, Comment, Plan, Subscription

#### Views
- Homepage dashboard
- Website detail pages
- Moderation interface
- Analytics charts
- Settings panel

### 3. **Database Layer** (PostgreSQL)

Models are defined in SQLAlchemy and used by both FastAPI and Django (read-only in Django).

#### Key Tables
- `superuser` - Platform users
- `website` - Client websites
- `thread` - Comment threads per webpage
- `comment` - Individual comments
- `plan` - Subscription plans
- `subscription` - Active subscriptions
- `invoice` - Billing records
- `moderation_queue` - Pending moderation
- `analytics` - Usage statistics
- `audit_log` - System audit trail

---

## Data Flow

### Comment Submission Flow
```
1. Website embeds comment widget with API key
2. User submits comment via widget
3. POST /api/v1/comments (with api_key)
   ├─ Validate API key
   ├─ Check spam filter
   ├─ Create comment record
   ├─ Add to moderation queue (if enabled)
   └─ Return comment ID
4. Webhook notification sent (optional)
5. Website receives confirmation
```

### Authentication Flow
```
1. User registers: POST /api/v1/auth/register
2. User login: POST /api/v1/auth/login returns {access_token, refresh_token}
3. Access token used in Authorization header: "Bearer {token}"
4. Token validated by get_current_user dependency
5. Refresh token used to get new access token when expired
```

### Moderation Flow
```
1. Comment submitted → queued in moderation_queue
2. Admin reviews via Django dashboard or API
3. Admin action: approve_comment → moves to published
   or reject_comment → marks as spam
   or delete_comment → removes from system
4. Analytics updated
```

---

## Database Schema

### Authentication & Billing
```sql
-- Users
CREATE TABLE superuser (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Plans
CREATE TABLE plan (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    price DECIMAL,
    comments_per_month INT
);

-- Subscriptions
CREATE TABLE subscription (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES superuser(id),
    plan_id INT REFERENCES plan(id),
    active_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Invoices
CREATE TABLE invoice (
    id SERIAL PRIMARY KEY,
    subscription_id INT REFERENCES subscription(id),
    amount DECIMAL,
    issued_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP
);
```

### Core Platform
```sql
-- Websites
CREATE TABLE website (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES superuser(id),
    domain VARCHAR NOT NULL,
    api_key VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Threads (Comment sections)
CREATE TABLE thread (
    id SERIAL PRIMARY KEY,
    website_id INT REFERENCES website(id),
    page_url VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Comments
CREATE TABLE comment (
    id SERIAL PRIMARY KEY,
    thread_id INT REFERENCES thread(id),
    author_name VARCHAR,
    author_email VARCHAR,
    content TEXT,
    is_approved BOOLEAN DEFAULT FALSE,
    is_spam BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Moderation Queue
CREATE TABLE moderation_queue (
    id SERIAL PRIMARY KEY,
    comment_id INT REFERENCES comment(id),
    status VARCHAR DEFAULT 'pending',
    flagged_reason VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analytics
CREATE TABLE analytics (
    id SERIAL PRIMARY KEY,
    website_id INT REFERENCES website(id),
    comments_submitted INT DEFAULT 0,
    comments_approved INT DEFAULT 0,
    spam_detected INT DEFAULT 0,
    month_year VARCHAR,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## API Architecture

### Request/Response Cycle

```
Client Request
    ↓
CORS Middleware (allow origins check)
    ↓
Request Timing Middleware (start timer)
    ↓
Route Handler
    ├─ Dependency Injection (auth, db, etc.)
    ├─ Request Validation (Pydantic schema)
    ├─ Business Logic
    ├─ Database Operations
    └─ Response Serialization
    ↓
Request Timing Middleware (add X-Process-Time header)
    ↓
Response to Client
```

### Endpoint Organization

**V1 API Base**: `/api/v1`

Endpoints organized by domain:
- `/auth/*` - Authentication
- `/websites/*` - Website management
- `/comments/*` - Comment operations
- `/moderation/*` - Moderation actions
- `/billing/*` - Billing & subscription
- `/analytics/*` - Analytics & reporting

### Response Format

All endpoints return JSON:
```json
{
  "status": "success|error",
  "data": {},
  "message": "optional message",
  "errors": []
}
```

---

## Authentication & Security

### JWT Implementation
- **Algorithm**: HS256
- **Access Token Expiry**: 30 minutes
- **Refresh Token Expiry**: 7 days
- **Signing Key**: `SECRET_KEY` from environment

### Password Security
- **Hashing**: bcrypt with salt
- **Verification**: Constant-time comparison

### API Key Authentication
- Websites use API keys for comment submission
- Keys are rotatable
- Keys are associated with website records

### CORS Configuration
- Configurable allowed origins via environment
- Credentials allowed
- All HTTP methods allowed
- All headers allowed

### Rate Limiting
- Default: 60 requests/minute (unauthenticated)
- Authenticated: 120 requests/minute
- Per-endpoint rate limiting possible

---

## Deployment

### Docker Setup
```bash
# Build and run with docker-compose
docker-compose up -d

# Services:
# - PostgreSQL: localhost:5432
# - FastAPI: localhost:8000
# - Django Admin: localhost:8001
```

### Environment Variables
Required variables in `.env`:
```
DATABASE_URL=postgresql://user:password@db:5432/kommies
SECRET_KEY=your-secret-key
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Running Locally
```bash
# FastAPI
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Django
cd backend
pip install -r requirements.txt
python manage.py runserver 8001
```

### Production Considerations
- Use environment-specific settings
- Enable HTTPS/SSL
- Configure proper CORS origins
- Use strong SECRET_KEY
- Enable database backups
- Set up proper logging
- Configure email credentials for notifications

---

## Development Workflow

### Adding a New Endpoint
1. Create route handler in appropriate `endpoints/*.py`
2. Define Pydantic schema in `schemas/`
3. Define SQLAlchemy model if needed in `models/`
4. Add router to `api/v1/router.py`
5. Add tests to `tests/`

### Database Changes
1. Update SQLAlchemy models
2. Generate/apply Alembic migrations (if using)
3. Update corresponding Django models
4. Test with both FastAPI and Django

### Configuration Changes
1. Update `core/config.py` Settings class
2. Add to `.env.example`
3. Document in deployment section

---

## Monitoring & Logging

### Request Tracking
- Request processing time added to response headers (`X-Process-Time`)
- Timing in milliseconds

### Error Handling
- Global exception handler catches all unhandled exceptions
- Returns 500 status with generic error message
- Logs stack traces (in development)

### Audit Logging
- `audit_log` table tracks important actions
- Created, modified, deleted records logged
- User and timestamp recorded

---

## Future Enhancements

1. **GraphQL API** - Alternative to REST API
2. **Real-time Notifications** - WebSocket support
3. **Advanced Analytics** - ML-based spam detection
4. **Multi-tenant Support** - Improved isolation
5. **API Rate Limiting** - Per-endpoint configuration
6. **Database Migrations** - Alembic integration
7. **Testing** - Comprehensive test suite
8. **CI/CD Pipeline** - Automated deployments

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async Guide](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Django Admin Interface](https://docs.djangoproject.com/en/stable/ref/contrib/admin/)
