#!/bin/bash

# Kill any existing cloudflared processes
pkill cloudflared

# Kill any existing tmux session named "nfl-app"
tmux kill-session -t nfl-app 2>/dev/null

# Create a new detached tmux session named "nfl-app"
tmux new-session -d -s nfl-app

# Split the window into two panes
tmux split-window -h

# Send commands to the first pane (backend)
tmux send-keys -t nfl-app:0.0 'export DJANGO_SETTINGS_MODULE=sports.production_settings && source venv/bin/activate && python backend/manage.py runserver 8001' C-m

# Send commands to the second pane (tunnel)
tmux send-keys -t nfl-app:0.1 'cloudflared tunnel --config /home/t/projects/nfl-sports-app/sports-info-tunnel.yml run' C-m

echo "Production server and tunnel starting in tmux session 'nfl-app'."
echo "Attach to session with: tmux attach -t nfl-app"