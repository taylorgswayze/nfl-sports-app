#!/bin/bash

# Kill any existing tmux session named "nfl-app"
tmux kill-session -t nfl-app 2>/dev/null

# Create a new detached tmux session named "nfl-app"
tmux new-session -d -s nfl-app

# Split the window into two panes
tmux split-window -h

# Send commands to the first pane (backend)
tmux send-keys -t nfl-app:0.0 'source venv/bin/activate && python backend/manage.py runserver 8001' C-m

# Send commands to the second pane (frontend)
tmux send-keys -t nfl-app:0.1 'npm --prefix frontend run dev' C-m

echo "Servers starting in tmux session 'nfl-app'."
echo "Attach to session with: tmux attach -t nfl-app"