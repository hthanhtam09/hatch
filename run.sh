#!/usr/bin/env bash
# Chay Hatch Studio tren macOS / Linux
#   ./run.sh         che do phat trien (sua code giao dien la thay ngay)
#   ./run.sh prod    build giao dien roi chay ban toi uu
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi
if [ ! -d web/node_modules ]; then
  (cd web && npm install)
fi

# Cong dang bi chiem (thuong la ban Flask cu chua tat) -> bao loi thay vi chay voi code cu
for PORT in 5050 3000; do
  OLD=$(lsof -ti tcp:$PORT -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$OLD" ]; then
    echo "Cong $PORT dang duoc dung boi tien trinh $OLD:"
    ps -o pid,lstart,command -p $OLD | tail -n +2
    echo "Tat no bang:  kill $OLD   roi chay lai ./run.sh"
    exit 1
  fi
done

# Flask API chay nen, tat cung luc voi giao dien khi bam Ctrl + C
./.venv/bin/python app.py &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT INT TERM

(sleep 4 && open "http://127.0.0.1:3000" 2>/dev/null || true) &
cd web
if [ "$1" = "prod" ]; then
  npm run build
  npm run start -- -H 127.0.0.1 -p 3000
else
  npm run dev -- -H 127.0.0.1 -p 3000
fi
