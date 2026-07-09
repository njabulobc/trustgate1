#!/usr/bin/env bash
# Portable starter for Unix-like systems. Place in project root and run ./start.sh
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# find virtualenv
VENV=""
for d in .venv venv env; do
  if [ -f "$d/bin/activate" ]; then VENV="$d"; break; fi
done

# backend command detection
if [ -f manage.py ]; then
  BACKEND_CMD='python manage.py runserver 0.0.0.0:8000'
elif [ -f main.py ]; then
  BACKEND_CMD='python -m uvicorn main:app --reload --port 8000'
elif [ -f app.py ]; then
  BACKEND_CMD='python -m uvicorn app:app --reload --port 8000'
else
  BACKEND_CMD="bash -c 'echo No recognized backend start command found; read -p \"Press Enter to continue...\"'"
fi

# Start backend in a new terminal if available, otherwise background it
if command -v gnome-terminal >/dev/null 2>&1; then
  if [ -n "$VENV" ]; then
    gnome-terminal -- bash -c "source \"$VENV/bin/activate\"; cd \"$DIR\"; $BACKEND_CMD; exec bash"
  else
    gnome-terminal -- bash -c "cd \"$DIR\"; $BACKEND_CMD; exec bash"
  fi
elif command -v xterm >/dev/null 2>&1; then
  if [ -n "$VENV" ]; then
    xterm -e bash -lc "source \"$VENV/bin/activate\"; cd \"$DIR\"; $BACKEND_CMD; bash" &
  else
    xterm -e bash -lc "cd \"$DIR\"; $BACKEND_CMD; bash" &
  fi
else
  if [ -n "$VENV" ]; then
    (source "$VENV/bin/activate"; cd "$DIR"; $BACKEND_CMD) &
  else
    ({ cd "$DIR"; $BACKEND_CMD; } &) || true
  fi
fi

# frontend
if [ -f frontend/package.json ]; then
  FRONTDIR="$DIR/frontend"
elif [ -f package.json ]; then
  FRONTDIR="$DIR"
else
  FRONTDIR=""
fi

if [ -n "$FRONTDIR" ]; then
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -c "cd \"$FRONTDIR\"; npm install --no-audit --no-fund; npm run dev || npm start; exec bash"
  elif command -v xterm >/dev/null 2>&1; then
    xterm -e bash -lc "cd \"$FRONTDIR\"; npm install --no-audit --no-fund; npm run dev || npm start; bash" &
  else
    (cd "$FRONTDIR"; npm install --no-audit --no-fund; npm run dev || npm start) &
  fi
else
  echo "No frontend package.json found. Skipping frontend."
fi

echo "Starter attempted to launch backend and frontend."