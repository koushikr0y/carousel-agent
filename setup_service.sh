#!/usr/bin/env bash
# Sets up the Instagram Carousel Telegram Bot as a background systemd user service.
# Runs silently 24/7 on boot, with auto-restart on failure, no terminal required.

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/carousel-bot.service"

mkdir -p "$SERVICE_DIR"

echo ">> Creating systemd user service at: $SERVICE_FILE"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Instagram Carousel Agent Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/main.py bot
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Reload and enable
systemctl --user daemon-reload
systemctl --user enable carousel-bot.service
systemctl --user restart carousel-bot.service

echo ""
echo "=================================================================="
echo " [✓] Carousel Bot is now running silently in the background 24/7!"
echo "=================================================================="
echo "You can close this terminal anytime. The bot stays alive."
echo ""
echo "Useful Commands:"
echo "  • Check status:  systemctl --user status carousel-bot"
echo "  • View live logs: journalctl --user -u carousel-bot -f"
echo "  • Restart bot:   systemctl --user restart carousel-bot"
echo "  • Stop bot:      systemctl --user stop carousel-bot"
echo "=================================================================="
