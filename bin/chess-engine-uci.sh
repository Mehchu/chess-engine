#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${CHESS_ENGINE_PYTHON:-}" ]; then
    interpreter=$CHESS_ENGINE_PYTHON
elif [ -x "$project_dir/.venv/bin/python" ]; then
    interpreter=$project_dir/.venv/bin/python
else
    interpreter=python3
fi

# The bot bridge needs the token. The engine process does not.
unset LICHESS_BOT_TOKEN
exec "$interpreter" "$project_dir/uci.py"
