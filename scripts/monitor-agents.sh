#!/bin/bash
# =============================================================
# monitor-agents.sh — Launch tmux session for agent monitoring
# =============================================================
# Creates a 5-pane tmux layout to watch all agents simultaneously
# No third-party tools. No open ports. No data logging.
# =============================================================

SESSION="sof-agents"

# Kill existing session if present
tmux kill-session -t $SESSION 2>/dev/null

# Create new session — Pane 0: Project Manager
tmux new-session -d -s $SESSION -n "agents"
tmux send-keys -t $SESSION "echo '🎯 PANE 0: PROJECT MANAGER'" C-m

# Pane 1: Code Expert (split right)
tmux split-window -h -t $SESSION
tmux send-keys -t $SESSION "echo '💻 PANE 1: CODE EXPERT'" C-m

# Pane 2: Branding Expert (split below pane 0)
tmux select-pane -t 0
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "echo '🎨 PANE 2: BRANDING EXPERT'" C-m

# Pane 3: Security Expert (split below pane 1)
tmux select-pane -t 1
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "echo '🔒 PANE 3: SECURITY EXPERT'" C-m

# Pane 4: Review Team Lead (split bottom-right for pane 3)
tmux select-pane -t 3
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "echo '📋 PANE 4: REVIEW TEAM LEAD'" C-m

# Set even layout
tmux select-layout -t $SESSION tiled

# Attach to the session
tmux attach -t $SESSION
