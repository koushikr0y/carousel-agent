# 🚀 AI-Powered Instagram Carousel Agent (BentoGrid Edition)

An automated agent that generates and publishes viral, high-retention multi-slide Instagram carousels with a consistent **BentoGrid Dark Mode** design system.

Features full **Telegram Bot Automation**: send a topic idea from your phone, preview the 6 rendered slides in Telegram as a native photo album, and tap **[ 🚀 Approve & Publish ]** to post immediately to Instagram!

Engineered for **Game Development (Godot Engine, Shaders, Systems Architecture)** and easily customizable to any niche.

---

## ✨ Features

- **🎨 Modern BentoGrid Visuals:** Clean glassmorphism cards, Plus Jakarta Sans typography, JetBrains Mono code snippets, and high-contrast metric callouts.
- **📱 Telegram Interactive Bot:** Send any topic via Telegram, receive the rendered slides preview, review the caption, and publish with one tap.
- **📐 4:5 Portrait Optimized:** Designed to occupy maximum mobile screen real estate on Instagram feeds.
- **⚡ Zero-Config Browser Publishing (Default):** Uses your existing logged-in Firefox profile session. No Meta Developer accounts, no Facebook Pages, and no API tokens required.
- **🧠 Google Gemini Integration:** Fast slide copywriting and breakdown with automatic fallback between models (`gemini-3.5-flash` & `gemini-3.5-flash-lite`).
- **🔍 Trend & Signal Detection:** Analyzes developer news feeds and search signals for timely topics.

---

## 🤖 Telegram Bot Workflow (Professional Setup)

The bot lets you control your Instagram publishing pipeline entirely from your phone:

```
 You (on Telegram)                Telegram Bot                  Instagram (@intentdev)
       │                               │                               │
       │─── "Godot 4 NavMesh" ────────>│                               │
       │                               │─── Generates 6 Bento Slides ──│
       │                               │─── Writes Caption & Tags ─────│
       │<── Sends Photo Album Preview ─│                               │
       │<── Sends [Approve] Button ────│                               │
       │                               │                               │
       │─── Tap [Approve & Publish] ──>│                               │
       │                               │─── Firefox Automation Upload ─│
       │                               │─── 4:5 Portrait Crop & Share ─> Live on Feed!
       │<── "✅ Published to @intentdev"│                               │
```

---

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.10+
- Firefox browser (logged into Instagram)
- Free Gemini API key from [Google AI Studio](https://aistudio.google.com)
- Free Telegram Bot Token from [@BotFather](https://t.me/BotFather) *(optional, for Telegram automation)*

### 2. Installation

Clone this repository and set up the environment:

```bash
git clone https://github.com/koushikr0y/carousel-agent.git
cd carousel-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install firefox
```

### 3. Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
TOPIC=Godot game development
REGION=US
BRAND=@intentdev

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash

# Telegram Bot (for mobile topic submission & approval)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
TELEGRAM_ALLOWED_USERS=your_telegram_username
```

---

## 🚀 Usage

### Option A: Telegram Bot Automation (Recommended)

Run the bot runner:

```bash
python main.py bot
# or: python telegram_bot.py
```

Then open your bot on Telegram:
1. Send `/start`
2. Send any topic text: e.g. `Godot 4.3 Compute Shaders`
3. View the 6-slide album preview and tap **[ 🚀 Approve & Publish to Instagram ]**!

---

### Option B: Command Line Interface

#### 1. Verify Instagram Session
Detects and confirms your active Instagram session from your local Firefox profile:
```bash
python main.py ig-login
```

#### 2. Generate a New Carousel
Generates high-resolution 1080x1350 JPEG slides and an engaging caption in `posts/`:
```bash
# Uses default TOPIC from .env:
python main.py generate

# Or pass a specific topic:
python main.py generate "Putting 2,500 zombies on GPU in Godot 4"
```

#### 3. Publish to Instagram
Uploads the 6 slides, adjusts aspect ratio to 4:5 portrait, applies captions and hashtags, and submits the post:
```bash
python main.py publish
```

*Tip: To watch the browser interact live in real-time, run:*
```bash
python main.py publish-browser --watch
```

---

## 📂 Repository Structure

```
carousel-agent/
├── main.py                  # Core agent pipeline (trends, LLM generation, HTML rendering, CLI)
├── browser_publisher.py     # Playwright Firefox publisher using local session
├── telegram_bot.py          # Telegram interactive bot (album preview & approval)
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
├── .gitignore               # Environment & secrets protection
├── setup.sh                 # Environment installer
└── posts/                   # Generated carousels & captions
    └── 20261016-1716/       # Latest published Godot BentoGrid carousel
```

---

## 🛡️ License

MIT License. Crafted for automated developer content creation.
