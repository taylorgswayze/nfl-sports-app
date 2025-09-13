from .settings import *

# --- PRODUCTION-SPECIFIC SETTINGS ---

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Tell Django where to find the main index.html for the React app
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']

# Tell Django where to find the static JS and CSS files
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
