"""
EKO-PRODUCTION CRM: PRODUCTION DEPLOYMENT CHECKLIST
Version: 1.0
Date: 2026-08-28
"""

## PRE-DEPLOYMENT CHECKLIST

### 1. Code Quality & Security
- [ ] Run linter: `flake8 app.py`
- [ ] Run security check: `bandit -r .`
- [ ] Ensure no hardcoded credentials in app.py
- [ ] Verify `.env` is in `.gitignore`
- [ ] Enable HTTPS/SSL certificate (Let's Encrypt recommended)
- [ ] Set `FLASK_ENV=production` in `.env`
- [ ] Generate strong SECRET_KEY (min 32 chars, random)

### 2. Database & Migrations
- [ ] Backup existing SQLite DB: `cp instance/eko_production.db instance/eko_production.db.backup-2026-08-28`
- [ ] Apply new models (S1-S8): Add classes from MODELS_S1_TO_S8.py to app.py
- [ ] Run migration: `python init_db.py` (creates new tables)
- [ ] Verify tables exist: `sqlite3 instance/eko_production.db .tables`
- [ ] Test rollback procedure on staging first

### 3. Dependencies
- [ ] Audit requirements: `pip freeze > requirements_2026.txt`
- [ ] Add new deps: `flask-wtf` (CSRF), `python-dotenv` (env vars), `flask-cors` (API)
- [ ] Pin versions: Update requirements.txt with exact versions
- [ ] Test install on staging: `pip install -r requirements.txt`

### 4. Environment Configuration
- [ ] Copy `.env.example` to `.env`
- [ ] Fill in production values:
  - SECRET_KEY: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
  - TELEGRAM_BOT_TOKEN: From BotFather
  - TELEGRAM_CHAT_IDs: Your group/channel IDs
  - DATABASE_URI: Point to production DB
  - MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD: SMTP config
- [ ] Set SESSION_COOKIE_SECURE=True, HTTPONLY=True, SAMESITE=Lax (only for HTTPS)
- [ ] Verify `.env` permissions: `chmod 600 .env`

### 5. CORS & External APIs
- [ ] Configure Flask-CORS for mobile app requests
- [ ] Whitelist allowed origins in CORS config
- [ ] Telegram Bot token tested: `curl https://api.telegram.org/botTOKEN/getMe`
- [ ] Email SMTP tested: `telnet mail.server.com 587`

### 6. Testing (Staging)
- [ ] Unit tests: `python -m pytest tests/ -v`
- [ ] Integration test: Login → Create order → Auto-generate tasks → Check materials → Send email
- [ ] Role-based access: Test login as admin, manager, user roles
- [ ] Form validation: Submit invalid data, verify error messages
- [ ] Download KП: Verify 404 is fixed
- [ ] CSRF protection: Submit form without token, verify rejection

### 7. Monitoring & Logging
- [ ] Configure error tracking (Sentry recommended)
- [ ] Enable application logging: `logging.basicConfig(level=logging.INFO)`
- [ ] Set up log rotation: `RotatingFileHandler`
- [ ] Monitor DB connection pool: `SQLALCHEMY_POOL_SIZE=10`
- [ ] Set up uptime monitoring (Uptime Robot, etc.)

### 8. Performance & Load
- [ ] Run load test: `pip install locust`, then `locust -f locustfile.py`
- [ ] Expected: Handle 10+ concurrent users without degradation
- [ ] Database indexing: Verify indices on `status`, `created_at`, `user_id`
- [ ] Cache static assets: Configure web server (Nginx/Apache)
- [ ] Enable gzip compression

### 9. Backup & Disaster Recovery
- [ ] Daily DB backup: `0 2 * * * /home/crm/backup.sh` (cron job)
- [ ] Backup script location: `/home/crm/backup.sh`
- [ ] Off-site backup: Upload to S3 or cloud storage
- [ ] Test restore: `sqlite3 instance/eko_production.db < backup.sql`
- [ ] Document runbook: `/home/crm/RUNBOOK.md`

### 10. Deployment Infrastructure
- [ ] Web server: Gunicorn (production) or uWSGI
- [ ] Config: `gunicorn -w 4 -b 0.0.0.0:8000 app:app`
- [ ] Reverse proxy: Nginx or Apache for HTTPS, SSL, routing
- [ ] Process manager: Systemd service or Supervisor
- [ ] Service restart: `systemctl restart eko-crm` (Systemd)

### 11. Documentation
- [ ] User manual: Create/update guides for each role
- [ ] API docs: Generate Swagger/OpenAPI from code
- [ ] Runbook: Emergency procedures, common issues, rollback steps
- [ ] Architecture diagram: Update with S1-S8 models
- [ ] Database schema: Export ERD from SQLAlchemy models

### 12. Go-Live
- [ ] Announce maintenance window: Email all users (e.g. 22:00 - 23:00 UTC)
- [ ] Switch DNS to staging, test full flow
- [ ] Point production DNS to new app server
- [ ] Warm caches: Simulate user traffic
- [ ] Monitor logs for errors: First 30 minutes
- [ ] Have rollback plan ready: Keep old DB backup mounted

### 13. Post-Deployment (First Week)
- [ ] Daily check-ins: Review audit logs, error tracking
- [ ] Gather user feedback: Send brief survey
- [ ] Performance metrics: Query latency, error rates, uptime
- [ ] Fix any critical issues immediately
- [ ] Document lessons learned

---

## DEPLOYMENT COMMANDS

```bash
# Staging (first)
git checkout develop
git pull origin feature/sprint-s1-s8
pip install -r requirements.txt
cp .env.example .env
# Edit .env
python init_db.py  # Creates tables
export FLASK_ENV=development
python app.py  # Test locally at http://localhost:5000

# Run tests
pytest tests/ -v

# Production (after staging passes)
git checkout main
git pull origin main
pip install -r requirements.txt --upgrade
# Stop running app
systemctl stop eko-crm
# Backup DB
cp instance/eko_production.db instance/eko_production.db.backup-$(date +%Y%m%d-%H%M%S)
# Update app
git clone https://github.com/Nightsteve-art/CRMLocal.git /opt/eko-crm
cd /opt/eko-crm
# Copy production .env (not from git)
cp /home/crm/.env .env
# Migrate DB
python init_db.py
# Restart
systemctl start eko-crm
# Verify
curl https://your-domain.com/
systemctl status eko-crm
```

---

## QUICK ISSUE TROUBLESHOOTING

| Issue | Solution |
|---|---|
| 404 on KП download | Check `app.py:717-745` proposal_download function; verify `UPLOAD_FOLDER` exists |
| CSRF token missing | Ensure `csrf_protect.py` imported and `{% csrf_token() %}` in all POST forms |
| DB locked error | Stop all running instances: `killall python` |
| 'No module' error | `pip install -r requirements.txt` and check virtualenv is active |
| Can't login | Verify `.env` has `SQLALCHEMY_DATABASE_URI` pointing to correct DB |
| Telegram not sending | Check token in `.env` with: `curl https://api.telegram.org/botTOKEN/getMe` |
| Email not sending | Verify SMTP credentials and firewall allows port 587 |
| High memory usage | Check for connection pool leaks: `SQLALCHEMY_ECHO=False` (disable debug) |

---

## ROLLBACK PROCEDURE (If Critical Issue)

```bash
# Stop current version
systemctl stop eko-crm

# Restore previous DB
cp instance/eko_production.db instance/eko_production.db.broken
cp instance/eko_production.db.backup instance/eko_production.db

# Revert code
git checkout previous-stable-commit
pip install -r requirements.txt --downgrade  # Or reinstall dependencies

# Restart
systemctl start eko-crm

# Investigate issue, create fix, test on staging
```

---

## NEXT STEPS AFTER DEPLOYMENT

1. **Gather Feedback**: Ask users about UX, bugs, feature requests
2. **Refine AI Assistant**: Collect prediction accuracy data
3. **Optimize Performance**: Monitor slow queries, add caching
4. **Security Hardening**: Run penetration test
5. **Mobile App**: Deploy PWA or native iOS/Android
6. **Extended Integrations**: Add payment gateway, ERP sync, BI tools

---

**Questions or blockers?** Create GitHub Issue with tag `deployment:` or `bug:`
