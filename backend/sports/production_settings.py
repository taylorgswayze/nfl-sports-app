import os

from .settings import *

# --- PRODUCTION-SPECIFIC SETTINGS ---
# Run with DJANGO_SETTINGS_MODULE=sports.production_settings (set in
# deploy/nfl.service). Secrets come from the environment / .env file.

DEBUG = False

# The beta shares production's database, and the OLD production checkout's
# crontab still drives the classic hourly jobs. django_cron's lock is
# per-process (LocMemCache), so if this instance ran the same job codes the
# two would execute concurrently against the shared sqlite file. The env
# override lets the beta run only its own new jobs until promotion.
_cron_override = os.environ.get('CRON_CLASSES_OVERRIDE')
if _cron_override:
    CRON_CLASSES = [c.strip() for c in _cron_override.split(',') if c.strip()]

# Env-overridable so the beta deployment (nfl-beta.taylorswayze.com) can run
# this same settings module; defaults preserve production behavior.
ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS', 'nfl.taylorswayze.com,localhost,127.0.0.1').split(',')

# Require a real secret key in production; see .env.example.
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

# Behind the Cloudflare tunnel everything arrives over HTTPS.
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'DJANGO_CSRF_ORIGINS', 'https://nfl.taylorswayze.com').split(',')

# Beta shares production's database read-mostly; point it at the prod file
# via env rather than duplicating data. The busy timeout rides out the
# production cron's brief write locks.
_db_path = os.environ.get('DJANGO_DB_PATH')
if _db_path:
    DATABASES['default']['NAME'] = _db_path
    DATABASES['default'].setdefault('OPTIONS', {})['timeout'] = 20
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Tell Django where to find the main index.html for the React app
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']

# Tell Django where to find the static JS and CSS files
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
