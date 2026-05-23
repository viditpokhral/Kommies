# Kommies

Kommies is a scalable, embeddable comment platform. It allows websites to seamlessly embed a comment widget while providing a robust backend for comprehensive moderation, analytics, and billing features. 

The system utilizes a dual-backend architecture, featuring a high-throughput FastAPI service for RESTful API operations and a beautiful Django admin dashboard for platform management.

## 🛠️ Tech Stack
* **Language**: Python >= 3.13
* **Backend API**: FastAPI (>=0.128.5) paired with Uvicorn (>=0.40.0)
* **Admin Dashboard**: Django (>=6.0.2)
* **Database**: PostgreSQL 14
* **ORM**: SQLAlchemy (>=2.0.46) configured with async support
* **Package Management**: Poetry

## ✨ Key Features
* **Embeddable Widget Integration**: Websites can seamlessly integrate comment threads using rotatable API keys.
* **Advanced Moderation**: A dedicated moderation queue allows administrators to quickly approve, reject, or flag comments as spam, including bulk actions.
* **Analytics**: Provides deep insights such as 30-day comment trends, top thread engagement, and daily API usage.
* **Billing & Subscriptions**: Includes out-of-the-box support for subscription plans and invoicing management.
* **Security & Authentication**: Protects user data with JWT-based authentication, refresh tokens, rate limiting, and bcrypt password hashing.

## 🏗️ Architecture Overview
The platform operates on a shared-database model leveraging two distinct services:
1. **FastAPI Backend (`/api`)**: Serves on Port 8000 and is responsible for authentication endpoints, core comment management logic, public API requests for widgets, and billing.
2. **Django Admin (`/backend`)**: Serves on Port 8001 and reads from the shared unmanaged database to provide a color-coded admin dashboard, moderation queue interface, and analytics charts.
3. **PostgreSQL Database**: A centralized store for core platform models, authentication details, and moderation data.

## 🚀 Getting Started

### Option 1: Docker (Recommended)
The quickest way to spin up the entire application stack is via Docker Compose. 
1. Build and start the services in detached mode:
   ```bash
   docker-compose up -d
