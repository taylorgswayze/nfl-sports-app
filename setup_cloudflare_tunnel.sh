#!/bin/bash

# NFL Sports App - Cloudflare Tunnel Setup Script
# This script sets up the NFL sports application with Cloudflare tunnel on Raspberry Pi

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_NAME="nfl-sports-app"
APP_USER="nflapp"
APP_DIR="/opt/$APP_NAME"
DOMAIN="nfl.taylorswayze.com"
DB_NAME="nfl_production"
DB_USER="nfl_user"

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Install Cloudflared
install_cloudflared() {
    print_status "Installing Cloudflared..."
    
    # Download and install cloudflared for ARM64
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
    sudo dpkg -i cloudflared-linux-arm64.deb
    rm cloudflared-linux-arm64.deb
    
    print_success "Cloudflared installed"
}

# Setup system packages (without nginx/certbot)
install_system_packages() {
    print_status "Installing system packages..."
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        nodejs \
        npm \
        postgresql \
        postgresql-contrib \
        git \
        curl \
        supervisor \
        build-essential \
        python3-dev \
        libpq-dev \
        wget
    print_success "System packages installed"
}

# Create application user
create_app_user() {
    print_status "Creating application user..."
    if ! id "$APP_USER" &>/dev/null; then
        sudo useradd -r -s /bin/bash -d $APP_DIR -m $APP_USER
        print_success "User $APP_USER created"
    else
        print_status "User $APP_USER already exists"
    fi
}

# Setup database
setup_database() {
    print_status "Setting up PostgreSQL database..."
    
    DB_PASSWORD=$(openssl rand -base64 32)
    
    sudo -u postgres psql << EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DB_USER SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\q
EOF
    
    echo "DB_NAME=$DB_NAME" | sudo tee $APP_DIR/.env
    echo "DB_USER=$DB_USER" | sudo tee -a $APP_DIR/.env
    echo "DB_PASSWORD=$DB_PASSWORD" | sudo tee -a $APP_DIR/.env
    echo "DB_HOST=localhost" | sudo tee -a $APP_DIR/.env
    echo "DB_PORT=5432" | sudo tee -a $APP_DIR/.env
    
    sudo chown $APP_USER:$APP_USER $APP_DIR/.env
    sudo chmod 600 $APP_DIR/.env
    
    print_success "Database setup completed"
}

# Setup application
setup_application() {
    print_status "Setting up application..."
    
    sudo mkdir -p $APP_DIR
    sudo chown $APP_USER:$APP_USER $APP_DIR
    
    # Copy application files
    sudo -u $APP_USER cp -r . $APP_DIR/
    
    # Setup Python virtual environment
    sudo -u $APP_USER python3 -m venv $APP_DIR/venv
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install gunicorn psycopg2-binary
    
    print_success "Application setup completed"
}

# Setup Django for Cloudflare tunnel
setup_django_production() {
    print_status "Configuring Django for Cloudflare tunnel..."
    
    sudo -u $APP_USER tee $APP_DIR/backend/sports/production_settings.py > /dev/null << EOF
from .settings import *
import os

DEBUG = False
ALLOWED_HOSTS = ['$DOMAIN', 'localhost', '127.0.0.1']

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', '$DB_NAME'),
        'USER': os.environ.get('DB_USER', '$DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# CORS settings for Cloudflare tunnel
CORS_ALLOWED_ORIGINS = [
    "https://$DOMAIN",
]

CSRF_TRUSTED_ORIGINS = [
    "https://$DOMAIN",
]

# Trust Cloudflare proxy headers
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECRET_KEY = os.environ.get('SECRET_KEY', '$(openssl rand -base64 50)')
EOF
    
    SECRET_KEY=$(openssl rand -base64 50)
    echo "SECRET_KEY=$SECRET_KEY" | sudo tee -a $APP_DIR/.env
    
    print_success "Django production settings configured"
}

# Build frontend for single-page app
build_frontend() {
    print_status "Building frontend for single-page deployment..."
    
    cd $APP_DIR/frontend
    
    # Update API base URL to use same domain
    sudo -u $APP_USER sed -i "s|http://localhost:8000|https://$DOMAIN|g" src/api.js
    
    sudo -u $APP_USER npm install
    sudo -u $APP_USER npm run build
    
    # Copy built files to Django static directory
    sudo mkdir -p $APP_DIR/backend/static
    sudo cp -r dist/* $APP_DIR/backend/static/
    sudo chown -R $APP_USER:$APP_USER $APP_DIR/backend/static
    
    print_success "Frontend built and integrated with Django"
}

# Setup Django to serve frontend
setup_django_frontend_serving() {
    print_status "Configuring Django to serve React frontend..."
    
    # Update Django URLs to serve frontend
    sudo -u $APP_USER tee $APP_DIR/backend/sports/urls.py > /dev/null << 'EOF'
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('nfl.urls')),  # API endpoints under /api/
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),  # Catch-all for React
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
EOF
    
    # Update NFL app URLs
    sudo -u $APP_USER sed -i "s|path('', views.api_root|path('', views.api_root|g" $APP_DIR/backend/nfl/urls.py
    
    # Create templates directory and copy index.html
    sudo mkdir -p $APP_DIR/backend/templates
    sudo cp $APP_DIR/backend/static/index.html $APP_DIR/backend/templates/
    sudo chown -R $APP_USER:$APP_USER $APP_DIR/backend/templates
    
    # Update Django settings for templates
    sudo -u $APP_USER tee -a $APP_DIR/backend/sports/production_settings.py > /dev/null << 'EOF'

# Template configuration for React frontend
TEMPLATES[0]['DIRS'] = [os.path.join(BASE_DIR, 'templates')]

# Static files configuration
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
EOF
    
    print_success "Django configured to serve React frontend"
}

# Run Django setup
setup_django() {
    print_status "Running Django setup..."
    
    cd $APP_DIR/backend
    
    sudo -u $APP_USER bash -c "
        source $APP_DIR/.env
        source $APP_DIR/venv/bin/activate
        export DJANGO_SETTINGS_MODULE=sports.production_settings
        python manage.py migrate
        python manage.py collectstatic --noinput
        python manage.py initial
    "
    
    print_success "Django setup completed"
}

# Setup Gunicorn service
setup_gunicorn() {
    print_status "Setting up Gunicorn service..."
    
    sudo tee /etc/supervisor/conf.d/$APP_NAME.conf > /dev/null << EOF
[program:$APP_NAME]
command=$APP_DIR/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 sports.wsgi:application
directory=$APP_DIR/backend
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/$APP_NAME.log
environment=DJANGO_SETTINGS_MODULE="sports.production_settings"
EOF
    
    sudo supervisorctl reread
    sudo supervisorctl update
    sudo supervisorctl start $APP_NAME
    
    print_success "Gunicorn service configured"
}

# Setup Cloudflare tunnel
setup_cloudflare_tunnel() {
    print_status "Setting up Cloudflare tunnel..."
    
    print_status "Please complete these steps manually:"
    echo "1. Login to Cloudflare: cloudflared tunnel login"
    echo "2. Create tunnel: cloudflared tunnel create nfl-app"
    echo "3. Copy the tunnel ID and update nfl-tunnel.yml"
    echo "4. Add DNS record in Cloudflare dashboard:"
    echo "   Type: CNAME"
    echo "   Name: nfl"
    echo "   Content: TUNNEL_ID.cfargotunnel.com"
    echo "5. Run tunnel: cloudflared tunnel --config $APP_DIR/nfl-tunnel.yml run"
    
    # Copy tunnel config
    sudo cp $APP_DIR/nfl-tunnel.yml /etc/cloudflared/
    
    # Create systemd service for tunnel
    sudo tee /etc/systemd/system/cloudflared-nfl.service > /dev/null << EOF
[Unit]
Description=Cloudflare Tunnel for NFL App
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --config /etc/cloudflared/nfl-tunnel.yml run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF
    
    print_success "Cloudflare tunnel service created (manual steps required)"
}

# Setup cron jobs
setup_cron() {
    print_status "Setting up cron jobs..."
    
    sudo -u $APP_USER tee $APP_DIR/run_cron.sh > /dev/null << 'EOF'
#!/bin/bash
cd /opt/nfl-sports-app/backend
source /opt/nfl-sports-app/.env
source /opt/nfl-sports-app/venv/bin/activate
export DJANGO_SETTINGS_MODULE=sports.production_settings
python manage.py runcrons
EOF
    
    sudo chmod +x $APP_DIR/run_cron.sh
    (sudo -u $APP_USER crontab -l 2>/dev/null; echo "*/10 * * * * $APP_DIR/run_cron.sh") | sudo -u $APP_USER crontab -
    
    print_success "Cron jobs configured"
}

# Main installation
main() {
    print_status "Starting NFL Sports App installation with Cloudflare tunnel..."
    
    install_system_packages
    install_cloudflared
    create_app_user
    setup_database
    setup_application
    setup_django_production
    build_frontend
    setup_django_frontend_serving
    setup_django
    setup_gunicorn
    setup_cloudflare_tunnel
    setup_cron
    
    print_success "Installation completed!"
    echo
    print_status "Next Steps:"
    echo "1. Complete Cloudflare tunnel setup (see instructions above)"
    echo "2. Start tunnel service: sudo systemctl enable --now cloudflared-nfl"
    echo "3. Create Django superuser: cd $APP_DIR/backend && sudo -u $APP_USER $APP_DIR/venv/bin/python manage.py createsuperuser"
    echo "4. Test at: https://$DOMAIN"
    echo
    print_status "Management Commands:"
    echo "  - Restart App: sudo supervisorctl restart $APP_NAME"
    echo "  - View Logs: sudo tail -f /var/log/$APP_NAME.log"
    echo "  - Tunnel Status: sudo systemctl status cloudflared-nfl"
}

main "$@"
