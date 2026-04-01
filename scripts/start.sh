#!/usr/bin/env bash
# Start StockScan backend + frontend
set -e

PROJECT=/Users/zyzbot/MyProject/StockScan

echo "Starting backend on :8000..."
cd "$PROJECT"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "Starting frontend on :5173..."
cd "$PROJECT/frontend"
npm run dev -- --host &
FRONTEND_PID=$!

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "YOUR_IP")

echo ""
echo "StockScan running:"
echo "  Backend API: http://localhost:8000  |  http://${LOCAL_IP}:8000"
echo "  Swagger UI:  http://localhost:8000/docs"
echo "  Frontend:    http://localhost:5173  |  http://${LOCAL_IP}:5173"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
