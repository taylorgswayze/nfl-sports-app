#!/bin/bash

# Kill any existing tmux session named "nfl-app-dev"
tmux kill-session -t nfl-app-dev 2>/dev/null

# Create a new detached tmux session
tmux new-session -d -s nfl-app-dev

# Split the window into two panes
tmux split-window -h

# Send commands to the first pane (backend)
# Uses the default settings.py
tmux send-keys -t nfl-app-dev:0.0 'source venv/bin/activate && python backend/manage.py runserver 8000' C-m

# Send commands to the second pane (frontend)
tmux send-keys -t nfl-app-dev:0.1 'npm --prefix frontend run dev' C-m

echo "Development servers starting in tmux session 'nfl-app-dev'."
echo "Attach to session with: tmux attach -t nfl-app-dev"
