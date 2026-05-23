# Kommies 💬  
### A Scalable, Embeddable Comment Platform for Modern Websites

Kommies is a powerful and scalable comment platform that allows websites to seamlessly integrate real-time discussion threads through an embeddable widget. It combines a high-performance API backend with a robust admin dashboard for moderation, analytics, subscriptions, and platform management.

Built with a dual-backend architecture using **FastAPI** and **Django**, Kommies is designed for performance, maintainability, and developer experience.

---

## ✨ Features

- 🔌 **Embeddable Comment Widget**
  - Easily integrate comments into any website
  - API key based authentication
  - Rotatable keys for improved security

- 🛡️ **Advanced Moderation**
  - Dedicated moderation queue
  - Approve / reject / mark spam
  - Bulk moderation actions
  - Color-coded moderation dashboard

- 📊 **Analytics Dashboard**
  - 30-day comment trends
  - Daily API usage insights
  - Top-performing discussion threads
  - Engagement metrics

- 💳 **Billing & Subscriptions**
  - Subscription plan management
  - Invoice support
  - Scalable SaaS-ready architecture

- 🔐 **Authentication & Security**
  - JWT authentication
  - Refresh tokens
  - Rate limiting
  - bcrypt password hashing
  - Secure API key handling

- ⚡ **High Performance**
  - Async SQLAlchemy support
  - FastAPI-powered REST API
  - PostgreSQL optimized architecture

---

# 🏗️ Architecture Overview

Kommies uses a **shared database dual-service architecture**.

```text
                ┌────────────────────┐
                │   Client Website   │
                │  (Embedded Widget) │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │   FastAPI Backend  │
                │      /api          │
                │     Port 8000      │
                └─────────┬──────────┘
                          │
          ┌───────────────┴────────────────┐
          ▼                                ▼
 ┌─────────────────┐              ┌─────────────────┐
 │ PostgreSQL 14   │◄────────────►│ Django Admin    │
 │ Shared Database │              │    /backend     │
 └─────────────────┘              │    Port 8001    │
                                  └─────────────────┘
```

---

# 🛠️ Tech Stack

| Category | Technology |
|---|---|
| Language | Python >= 3.13 |
| Backend API | FastAPI + Uvicorn |
| Admin Dashboard | Django |
| Database | PostgreSQL 14 |
| ORM | SQLAlchemy Async |
| Package Manager | Poetry |
| Authentication | JWT + bcrypt |

---

# 📂 Project Structure

```bash
kommies/
│
├── api/                 # FastAPI backend
├── backend/             # Django admin dashboard
├── widget/              # Embeddable comment widget
├── shared/              # Shared models & utilities
├── migrations/          # Database migrations
├── docker/              # Docker configurations
├── scripts/             # Utility scripts
└── tests/               # Test suite
```

---

# 🚀 Getting Started

## Option 1 — Docker (Recommended)

The quickest way to start the entire stack.

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/kommies.git
cd kommies
```

### 2. Start Services

```bash
docker-compose up -d
```

### 3. Access Services

| Service | URL |
|---|---|
| FastAPI API | http://localhost:8000 |
| Django Admin | http://localhost:8001 |
| API Docs | http://localhost:8000/docs |

---

# ⚙️ Local Development Setup

## 1. Install Poetry

```bash
pip install poetry
```

## 2. Install Dependencies

```bash
poetry install
```

## 3. Configure Environment Variables

Create a `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/kommies
SECRET_KEY=your-secret-key
JWT_SECRET=your-jwt-secret
```

## 4. Run FastAPI Backend

```bash
poetry run uvicorn api.main:app --reload --port 8000
```

## 5. Run Django Admin

```bash
poetry run python backend/manage.py runserver 8001
```

---

# 🔑 API Authentication

Kommies uses JWT-based authentication.

### Obtain Access Token

```http
POST /api/auth/login
```

### Example Response

```json
{
  "access_token": "your-token",
  "refresh_token": "your-refresh-token"
}
```

---

# 📊 Analytics Features

- Daily API request tracking
- Comment activity visualization
- Top engaged discussion threads
- Moderation statistics
- Subscription insights

---

# 🔌 Embedding the Widget

Add the widget script to your website:

```html
<script
  src="https://cdn.kommies.dev/widget.js"
  data-api-key="YOUR_API_KEY">
</script>
```

---

# 🧪 Running Tests

```bash
poetry run pytest
```

---

# 🐳 Docker Services

| Container | Purpose |
|---|---|
| api | FastAPI application |
| backend | Django admin |
| postgres | PostgreSQL database |
| nginx | Reverse proxy (optional) |

---

# 📈 Future Roadmap

- Real-time comments with WebSockets
- AI-powered spam detection
- Multi-tenant organizations
- Comment reactions & replies
- Email notifications
- OAuth providers
- Theme customization support

---

# 👥 Authors

- Shashwat Acharya
- Vidit Pokhral

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

# 📄 License

This project is licensed under the MIT License.

---

# ⭐ Support the Project

If you like Kommies, consider giving the repository a star ⭐ to support development and help others discover the project.
