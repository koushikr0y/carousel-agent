#!/usr/bin/env bash
# Simple local controller for Carousel Agent Telegram Bot
# Usage:
#   ./bot.sh start    - Start the bot in the background
#   ./bot.sh stop     - Stop the background bot
#   ./bot.sh restart  - Restart the bot
#   ./bot.sh status   - Check if the bot is currently running
#   ./bot.sh logs     - View live output logs
#   ./bot.sh run      - Run in foreground (Ctrl+C to stop)

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/.bot.pid"
LOG_FILE="$DIR/bot.log"
PYTHON="$DIR/venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "[-] Virtual environment not found at $PYTHON"
    echo "    Run setup first or create venv: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi

is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

start_bot() {
    if is_running; then
        echo "[i] Bot is already running with PID: $(cat "$PID_FILE")"
        echo "    View logs: ./bot.sh logs"
        exit 0
    fi

    echo ">> Starting Carousel Telegram Bot in background..."
    nohup "$PYTHON" "$DIR/main.py" bot > "$LOG_FILE" 2>&1 &
    BOT_PID=$!
    echo "$BOT_PID" > "$PID_FILE"
    sleep 1.5

    if kill -0 "$BOT_PID" 2>/dev/null; then
        echo "[✓] Bot started successfully! (PID: $BOT_PID)"
        echo "    • View logs:   ./bot.sh logs"
        echo "    • Stop bot:    ./bot.sh stop"
        echo "    • Status:      ./bot.sh status"
    else
        echo "[-] Failed to start bot. Check log output below:"
        cat "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop_bot() {
    if ! is_running; then
        echo "[i] Bot is not currently running."
        # Also clean up any lingering main.py bot processes
        pkill -f "main.py bot" 2>/dev/null || true
        exit 0
    fi

    PID=$(cat "$PID_FILE")
    echo ">> Stopping bot (PID: $PID)..."
    kill "$PID" 2>/dev/null || true

    for _ in {1..10}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi
        sleep 0.5
    done

    # Force kill if still hanging
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "[✓] Bot stopped."
}

status_bot() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo "=================================================="
        echo " [✓] Carousel Bot is RUNNING (PID: $PID)"
        echo "=================================================="
        echo "Recent activity (last 8 log lines):"
        tail -n 8 "$LOG_FILE" 2>/dev/null || echo "(no logs yet)"
        echo "=================================================="
        echo "Commands:"
        echo "  • View live logs:  ./bot.sh logs"
        echo "  • Stop bot:        ./bot.sh stop"
        echo "  • Restart bot:     ./bot.sh restart"
    else
        echo "=================================================="
        echo " [x] Carousel Bot is STOPPED"
        echo "=================================================="
        echo "Start it with: ./bot.sh start"
    fi
}

show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        touch "$LOG_FILE"
    fi
    echo ">> Following live bot logs (Press Ctrl+C to exit log viewer)..."
    tail -f "$LOG_FILE"
}

run_foreground() {
    if is_running; then
        echo "[!] A background bot is already running (PID: $(cat "$PID_FILE")). Stop it first with: ./bot.sh stop"
        exit 1
    fi
    echo ">> Running Carousel Bot in foreground (Ctrl+C to stop)..."
    exec "$PYTHON" "$DIR/main.py" bot
}

case "$1" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        stop_bot
        sleep 1
        start_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        show_logs
        ;;
    run)
        run_foreground
        ;;
    *)
        echo "=================================================="
        echo "       Carousel Agent Bot Local Controller"
        echo "=================================================="
        echo "Usage: ./bot.sh {start|stop|restart|status|logs|run}"
        echo ""
        echo "Commands:"
        echo "  ./bot.sh start    - Start bot in the background"
        echo "  ./bot.sh stop     - Stop background bot"
        echo "  ./bot.sh restart  - Restart the bot"
        echo "  ./bot.sh status   - Check if bot is running"
        echo "  ./bot.sh logs     - Tail live logs in real time"
        echo "  ./bot.sh run      - Run in foreground (interactive)"
        echo "=================================================="
        exit 1
        ;;
esac
