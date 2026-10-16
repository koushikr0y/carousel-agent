#!/usr/bin/env bash
# One-time setup for EndeavourOS / Arch Linux
set -e

echo ">> Installing system packages (needs sudo)..."
sudo pacman -S --needed --noconfirm python python-pip chromium git \
  noto-fonts noto-fonts-emoji ttf-liberation

echo ">> Creating virtual environment..."
python -m venv venv
source venv/bin/activate

echo ">> Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

[ -f .env ] || cp .env.example .env

echo
echo "Setup done. Next:"
echo "  1) nano .env            (add your GEMINI_API_KEY and TOPIC)"
echo "  2) source venv/bin/activate"
echo "  3) python main.py selftest"
