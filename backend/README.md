# Comment Platform - Django Backend

Beautiful admin dashboard and management interface for the Comment Platform.

## 🎨 Features

### Admin Interface
- **Beautiful UI** with django-admin-interface theme
- **Color-coded** status badges and severity indicators
- **Bulk actions** for moderation (approve, spam, trash)
- **Usage progress bars** for subscriptions
- **Quick filters** and search

### Dashboard Views
- **Homepage**: Overview of all websites with stats
- **Website Detail**: Deep dive into individual website performance
- **Moderation Queue**: Review and moderate pending comments
- **Analytics**: Charts, graphs, and top commenters
- **API Integration**: Test FastAPI connectivity

### Models (Unmanaged - Read from Existing DB)
- SuperUser (Users)
- Website
- Thread
- Comment
- Plan
- Subscription
- ModerationQueue

## 📦 Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 3. Collect static files
python manage.py collectstatic --noinput

# 4. Create Django superuser
python manage.py createsuperuser

# 5. Run server
python manage.py runserver 8001
```

## 🗄️ Database Setup

**Important**: Django uses UNMANAGED models. The database tables are created by FastAPI's `bootstrap.sql`.

1. Make sure PostgreSQL is running
2. Run FastAPI's bootstrap.sql first:
   ```bash
   psql -U postgres -d comment_platform -f bootstrap.sql
   ```
3. Django will read/write to these existing tables

## 🚀 Usage

### Access Points

**Admin Panel**: http://localhost:8001/admin
- Login with your superuser credentials
- Manage users, websites, comments, subscriptions

**Dashboard**: http://localhost:8001/dashboard
- User-friendly interface for website owners
- View stats, moderate comments, see analytics

### Creating Your First User

```bash
python manage.py createsuperuser
```

Then login to `/admin` and create a SuperUser record that matches your Django user email.

## 📋 Project Structure

```
backend/
├── config/              # Django settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── dashboard/       # Main dashboard app
│   │   ├── models.py    # Unmanaged models
│   │   ├── admin.py     # Beautiful admin interface
│   │   ├── views.py     # Dashboard views
│   │   └── urls.py      # URL patterns
│   ├── analytics/       # Analytics views
│   └── moderation/      # Moderation views
├── templates/           # HTML templates
│   ├── base.html
│   └── dashboard/
├── static/              # CSS, JS, images
└── manage.py
```

## 🎯 Key Features Explained

### 1. Admin Interface

Beautiful, color-coded admin with:
- **Status badges**: Green (active), Yellow (pending), Red (spam/suspended)
- **Progress bars**: Visual usage indicators for subscriptions
- **Quick actions**: Approve/spam/trash comments in bulk
- **Smart filters**: Filter by status, date, severity
- **Inline editing**: Edit related objects without leaving page

### 2. Dashboard Views

**Homepage** (`/dashboard/`)
- Overview of all websites
- Total comments/threads stats
- Subscription info with usage bar
- Quick access to each website

**Website Detail** (`/dashboard/website/<id>/`)
- Today's stats
- Recent comments with inline moderation
- API integration code snippet
- Quick links to moderation queue & analytics

**Moderation Queue** (`/dashboard/website/<id>/moderation/`)
- All pending comments
- One-click approve/reject
- Spam score indicators
- Bulk actions

**Analytics** (`/dashboard/website/<id>/analytics/`)
- 30-day comment trends
- Top commenters
- Top threads by engagement

### 3. FastAPI Integration

Django can call FastAPI endpoints:

```python
import httpx
from django.conf import settings

response = httpx.get(
    f"{settings.FASTAPI_URL}/api/v1/comments/{api_key}/threads/test/comments"
)
```

## 🔗 Integration with FastAPI

Both services share the same PostgreSQL database:

```
┌─────────┐     Read/Write     ┌──────────────┐
│ Django  │ ─────────────────→ │  PostgreSQL  │
│ :8001   │                    │    :5432     │
└─────────┘                    └──────────────┘
                                        ↑
                                        │ Read/Write
                                        │
                               ┌────────────┐
                               │  FastAPI   │
                               │   :8000    │
                               └────────────┘
```

**What Each Does**:
- **Django**: Admin panel, dashboard UI, moderation interface
- **FastAPI**: Public comment API, webhooks, spam detection

## 🎨 Customization

### Adding Custom Fields to Admin

Edit `apps/dashboard/admin.py`:

```python
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = [..., 'your_custom_field']
```

### Adding New Dashboard Pages

1. Create view in `apps/dashboard/views.py`
2. Add URL in `apps/dashboard/urls.py`
3. Create template in `templates/dashboard/`

### Styling

Templates use Tailwind CSS via CDN. Edit templates to customize:
- `templates/base.html` - Layout, navigation
- `templates/dashboard/*.html` - Page-specific styling

## 📊 Database Queries

Example: Get pending comments for a website

```python
from apps.dashboard.models import Comment, Website

website = Website.objects.get(domain='example.com')
pending = Comment.objects.filter(
    thread__website=website,
    status='pending'
).count()
```

## 🔒 Security

- CSRF protection enabled
- Session-based authentication
- Row-level security via Django ORM
- Passwords hashed with bcrypt
- CORS configured for FastAPI integration

## 🚢 Deployment

### Production Settings

```python
# config/settings.py
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com']
SECRET_KEY = os.getenv('SECRET_KEY')  # Use strong secret!
```

### Gunicorn

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8001 --workers 4
```

### Nginx

```nginx
location /admin/ {
    proxy_pass http://localhost:8001;
}

location /dashboard/ {
    proxy_pass http://localhost:8001;
}
```

## 📞 Support

For questions or issues:
1. Check Django logs: `logs/django.log`
2. Enable DEBUG mode for detailed errors
3. Verify database connection
4. Ensure FastAPI is running (for API calls)

## 🎉 What's Next?

- [ ] Add email notifications for new comments
- [ ] Export analytics to CSV
- [ ] Bulk comment management tools
- [ ] Advanced filtering and search
- [ ] Real-time dashboard updates with WebSockets
- [ ] Mobile-responsive admin theme
- [ ] Custom branding per website

---

**Built with**: Django 5.0 · PostgreSQL · Tailwind CSS · Font Awesome
