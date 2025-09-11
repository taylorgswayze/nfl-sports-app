#!/bin/bash

# NFL Sports App - Raspberry Pi Production Setup Script
# This script sets up the NFL sports application on a Raspberry Pi server
# Run with: bash setup_raspberry_pi.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
APP_NAME="nfl-sports-app"
APP_USER="nflapp"
APP_DIR="/opt/$APP_NAME"
DOMAIN="your-domain.com"  # Change this to your actual domain
DB_NAME="nfl_production"
DB_USER="nfl_user"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root. Please run as a regular user with sudo privileges."
        exit 1
    fi
}

# Update system packages
update_system() {
    print_status "Updating system packages..."
    sudo apt update && sudo apt upgrade -y
    print_success "System packages updated"
}

# Install required system packages
install_system_packages() {
    print_status "Installing system packages..."
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        nodejs \
        npm \
        nginx \
        postgresql \
        postgresql-contrib \
        git \
        curl \
        supervisor \
        certbot \
        python3-certbot-nginx \
        build-essential \
        python3-dev \
        libpq-dev
    print_success "System packages installed"
}

# Create application user
create_app_user() {
    print_status "Creating application user..."
    if ! id "$APP_USER" &>/dev/null; then
        sudo useradd -r -s /bin/bash -d $APP_DIR -m $APP_USER
        print_success "User $APP_USER created"
    else
        print_warning "User $APP_USER already exists"
    fi
}

# Setup PostgreSQL database
setup_database() {
    print_status "Setting up PostgreSQL database..."
    
    # Generate random password
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DB_USER SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\q
EOF
    
    # Save database credentials
    echo "DB_NAME=$DB_NAME" | sudo tee $APP_DIR/.env
    echo "DB_USER=$DB_USER" | sudo tee -a $APP_DIR/.env
    echo "DB_PASSWORD=$DB_PASSWORD" | sudo tee -a $APP_DIR/.env
    echo "DB_HOST=localhost" | sudo tee -a $APP_DIR/.env
    echo "DB_PORT=5432" | sudo tee -a $APP_DIR/.env
    
    sudo chown $APP_USER:$APP_USER $APP_DIR/.env
    sudo chmod 600 $APP_DIR/.env
    
    print_success "Database setup completed"
    print_warning "Database credentials saved to $APP_DIR/.env"
}

# Clone and setup application
setup_application() {
    print_status "Setting up application..."
    
    # Create application directory
    sudo mkdir -p $APP_DIR
    sudo chown $APP_USER:$APP_USER $APP_DIR
    
    # Copy application files (assuming script is run from project directory)
    print_status "Copying application files..."
    sudo -u $APP_USER cp -r . $APP_DIR/
    
    # Setup Python virtual environment
    print_status "Setting up Python virtual environment..."
    sudo -u $APP_USER python3 -m venv $APP_DIR/venv
    
    # Install Python dependencies
    print_status "Installing Python dependencies..."
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install gunicorn psycopg2-binary
    
    print_success "Application setup completed"
}

# Setup Django production settings
setup_django_production() {
    print_status "Configuring Django for production..."
    
    # Create production settings file
    sudo -u $APP_USER tee $APP_DIR/backend/sports/production_settings.py > /dev/null << EOF
from .settings import *
import os

# Security settings
DEBUG = False
ALLOWED_HOSTS = ['$DOMAIN', 'www.$DOMAIN', 'localhost', '127.0.0.1']

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

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# CORS settings for production
CORS_ALLOWED_ORIGINS = [
    "https://$DOMAIN",
    "https://www.$DOMAIN",
]

CSRF_TRUSTED_ORIGINS = [
    "https://$DOMAIN",
    "https://www.$DOMAIN",
]

# Generate secret key
SECRET_KEY = os.environ.get('SECRET_KEY', '$(openssl rand -base64 50)')
EOF
    
    # Add SECRET_KEY to environment
    SECRET_KEY=$(openssl rand -base64 50)
    echo "SECRET_KEY=$SECRET_KEY" | sudo tee -a $APP_DIR/.env
    
    print_success "Django production settings configured"
}

# Build frontend
build_frontend() {
    print_status "Building frontend application..."
    
    cd $APP_DIR/frontend
    
    # Update API base URL for production
    sudo -u $APP_USER sed -i "s|http://localhost:8000|https://$DOMAIN/api|g" src/api.js
    
    # Install dependencies and build
    sudo -u $APP_USER npm install
    sudo -u $APP_USER npm run build
    
    # Copy built files to nginx directory
    sudo mkdir -p /var/www/$APP_NAME
    sudo cp -r dist/* /var/www/$APP_NAME/
    sudo chown -R www-data:www-data /var/www/$APP_NAME
    
    print_success "Frontend built and deployed"
}

# Run Django setup
setup_django() {
    print_status "Running Django setup..."
    
    cd $APP_DIR/backend
    
    # Load environment variables and run Django commands
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
    
    # Create Gunicorn configuration
    sudo tee /etc/supervisor/conf.d/$APP_NAME.conf > /dev/null << EOF
[program:$APP_NAME]
command=$APP_DIR/venv/bin/gunicorn --workers 3 --bind unix:$APP_DIR/gunicorn.sock sports.wsgi:application
directory=$APP_DIR/backend
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/$APP_NAME.log
environment=DJANGO_SETTINGS_MODULE="sports.production_settings"
EOF
    
    # Create environment file for supervisor
    sudo tee /etc/supervisor/conf.d/$APP_NAME-env.conf > /dev/null << EOF
[supervisord]
environment=
    DB_NAME="$DB_NAME",
    DB_USER="$DB_USER",
    DB_PASSWORD="$(grep DB_PASSWORD $APP_DIR/.env | cut -d'=' -f2)",
    DB_HOST="localhost",
    DB_PORT="5432",
    SECRET_KEY="$(grep SECRET_KEY $APP_DIR/.env | cut -d'=' -f2)"
EOF
    
    # Reload supervisor
    sudo supervisorctl reread
    sudo supervisorctl update
    sudo supervisorctl start $APP_NAME
    
    print_success "Gunicorn service configured"
}

# Setup Nginx
setup_nginx() {
    print_status "Setting up Nginx..."
    
    # Create Nginx configuration
    sudo tee /etc/nginx/sites-available/$APP_NAME > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    
    # Redirect HTTP to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;
    
    # SSL configuration (certificates will be added by certbot)
    
    # Frontend static files
    location / {
        root /var/www/$APP_NAME;
        try_files \$uri \$uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://unix:$APP_DIR/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Remove /api prefix when forwarding to Django
        rewrite ^/api/(.*) /\$1 break;
    }
    
    # Django admin
    location /admin/ {
        proxy_pass http://unix:$APP_DIR/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Django static files
    location /static/ {
        alias $APP_DIR/backend/staticfiles/;
        expires 1y;
        add_header Cache-Control "public";
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
EOF
    
    # Enable site
    sudo ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Test Nginx configuration
    sudo nginx -t
    
    print_success "Nginx configured"
}

# Setup SSL with Let's Encrypt
setup_ssl() {
    print_status "Setting up SSL certificate..."
    
    # Start Nginx
    sudo systemctl restart nginx
    
    # Get SSL certificate
    sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
    
    # Setup auto-renewal
    sudo systemctl enable certbot.timer
    
    print_success "SSL certificate configured"
}

# Setup cron jobs
setup_cron() {
    print_status "Setting up cron jobs..."
    
    # Create cron script
    sudo -u $APP_USER tee $APP_DIR/run_cron.sh > /dev/null << 'EOF'
#!/bin/bash
cd /opt/nfl-sports-app/backend
source /opt/nfl-sports-app/.env
source /opt/nfl-sports-app/venv/bin/activate
export DJANGO_SETTINGS_MODULE=sports.production_settings
python manage.py runcrons
EOF
    
    sudo chmod +x $APP_DIR/run_cron.sh
    
    # Add to crontab
    (sudo -u $APP_USER crontab -l 2>/dev/null; echo "*/10 * * * * $APP_DIR/run_cron.sh") | sudo -u $APP_USER crontab -
    
    print_success "Cron jobs configured"
}

# Setup log rotation
setup_logging() {
    print_status "Setting up log rotation..."
    
    sudo tee /etc/logrotate.d/$APP_NAME > /dev/null << EOF
/var/log/$APP_NAME.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        supervisorctl restart $APP_NAME
    endscript
}
EOF
    
    print_success "Log rotation configured"
}

# Setup firewall
setup_firewall() {
    print_status "Configuring firewall..."
    
    sudo ufw --force enable
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow ssh
    sudo ufw allow 'Nginx Full'
    
    print_success "Firewall configured"
}

# Create backup script
create_backup_script() {
    print_status "Creating backup script..."
    
    sudo tee $APP_DIR/backup.sh > /dev/null << EOF
#!/bin/bash
# NFL Sports App Backup Script

BACKUP_DIR="/opt/backups"
DATE=\$(date +%Y%m%d_%H%M%S)
APP_DIR="$APP_DIR"

# Create backup directory
mkdir -p \$BACKUP_DIR

# Database backup
sudo -u postgres pg_dump $DB_NAME > \$BACKUP_DIR/db_backup_\$DATE.sql

# Application files backup
tar -czf \$BACKUP_DIR/app_backup_\$DATE.tar.gz -C \$APP_DIR .

# Keep only last 7 days of backups
find \$BACKUP_DIR -name "*.sql" -mtime +7 -delete
find \$BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: \$DATE"
EOF
    
    sudo chmod +x $APP_DIR/backup.sh
    
    # Add daily backup to cron
    (sudo crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh") | sudo crontab -
    
    print_success "Backup script created"
}

# Main installation function
main() {
    print_status "Starting NFL Sports App installation on Raspberry Pi..."
    
    # Prompt for domain name
    read -p "Enter your domain name (e.g., nfl.example.com): " DOMAIN
    if [[ -z "$DOMAIN" ]]; then
        print_error "Domain name is required"
        exit 1
    fi
    
    check_root
    update_system
    install_system_packages
    create_app_user
    setup_database
    setup_application
    setup_django_production
    build_frontend
    setup_django
    setup_gunicorn
    setup_nginx
    setup_ssl
    setup_cron
    setup_logging
    setup_firewall
    create_backup_script
    
    print_success "Installation completed successfully!"
    echo
    print_status "Application Details:"
    echo "  - Domain: https://$DOMAIN"
    echo "  - Admin Panel: https://$DOMAIN/admin/"
    echo "  - Application Directory: $APP_DIR"
    echo "  - Database: PostgreSQL ($DB_NAME)"
    echo "  - Web Server: Nginx with SSL"
    echo "  - Application Server: Gunicorn"
    echo "  - Process Manager: Supervisor"
    echo
    print_status "Important Files:"
    echo "  - Environment Variables: $APP_DIR/.env"
    echo "  - Application Logs: /var/log/$APP_NAME.log"
    echo "  - Nginx Config: /etc/nginx/sites-available/$APP_NAME"
    echo "  - Supervisor Config: /etc/supervisor/conf.d/$APP_NAME.conf"
    echo
    print_status "Management Commands:"
    echo "  - Restart App: sudo supervisorctl restart $APP_NAME"
    echo "  - View Logs: sudo tail -f /var/log/$APP_NAME.log"
    echo "  - Nginx Status: sudo systemctl status nginx"
    echo "  - SSL Renewal: sudo certbot renew"
    echo "  - Run Backup: sudo $APP_DIR/backup.sh"
    echo
    print_warning "Next Steps:"
    echo "1. Create a Django superuser: cd $APP_DIR/backend && sudo -u $APP_USER $APP_DIR/venv/bin/python manage.py createsuperuser"
    echo "2. Test the application at https://$DOMAIN"
    echo "3. Configure DNS to point $DOMAIN to this server's IP address"
    echo "4. Review and customize the application settings as needed"
}

# Run main function
main "$@"
