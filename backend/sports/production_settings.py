import os

from .settings import *

# --- PRODUCTION-SPECIFIC SETTINGS ---
# Run with DJANGO_SETTINGS_MODULE=sports.production_settings (set in
# deploy/nfl.service). Secrets come from the environment / .env file.

DEBUG = False

ALLOWED_HOSTS = ['nfl.taylorswayze.com', 'localhost', '127.0.0.1']

# Require a real secret key in production; see .env.example.
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

# Behind the Cloudflare tunnel everything arrives over HTTPS.
CSRF_TRUSTED_ORIGINS = ['https://nfl.taylorswayze.com']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Tell Django where to find the main index.html for the React app
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']

# Tell Django where to find the static JS and CSS files
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
