# 🚀 AI-Powered Instagram Carousel Agent (BentoGrid Edition)

An automated agent that generates and publishes viral, high-retention multi-slide Instagram carousels with a consistent **BentoGrid Dark Mode** design system.

Engineered for **Game Development (Godot Engine, Shaders, Systems Architecture)** and easily customizable to any niche.

---

## ✨ Features

- **🎨 Modern BentoGrid Visuals:** Clean glassmorphism cards, Plus Jakarta Sans typography, JetBrains Mono code snippets, and high-contrast metric callouts.
- **📐 4:5 Portrait Optimized:** Designed to occupy maximum mobile screen real estate on Instagram feeds.
- **⚡ Two Powerful Publishing Engines:**
  1. **Zero-Config Browser Automation (Default):** Uses your existing logged-in Firefox profile session. No Meta Developer accounts, no Facebook Pages, and no API tokens required.
  2. **Official Meta Graph API:** Fully supported for cloud and headless CI/CD deployments.
- **🧠 Google Gemini Integration:** Fast slide copywriting and breakdown with automatic fallback between models (`gemini-3.5-flash` & `gemini-3.5-flash-lite`).
- **🔍 Trend & Signal Detection:** Analyzes developer news feeds and search signals for timely topics.

---

## 📸 Design Preview

Every generated carousel follows a consistent 6-slide BentoGrid pattern:
1. **Hook Slide:** Bold high-contrast headline, difficulty pill, reading time, and teaser stat.
2. **The Problem / Architecture:** Breakdown of the bottleneck with technical specs and diagrams.
3. **The Solution / Code:** Code snippets with syntax highlighting and callout tags.
4. **Implementation Deep Dive:** Key insights with visual cards and status badges.
5. **Results & Benchmarks:** Before/After performance metrics (FPS, Draw Calls, Memory).
6. **Actionable Takeaways / CTA:** Key checklist and community discussion prompt.

---

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.10+
- Firefox browser (logged into Instagram)
- Free Gemini API key from [Google AI Studio](https://aistudio.google.com)

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
```

---

## 🚀 Usage

### 1. Verify Instagram Session
Detects and confirms your active Instagram session from your local Firefox profile:

```bash
python main.py ig-login
```

### 2. Generate a New Carousel
Generates high-resolution 1080x1350 JPEG slides and an engaging caption in `posts/`:

```bash
python main.py generate
```

### 3. Publish to Instagram
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
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
├── .gitignore               # Environment & secrets protection
├── setup.sh                 # Environment installer
└── posts/                   # Generated carousels & captions
    └── 20261016-1716/       # Latest published Godot BentoGrid carousel
```

---

## ⚙️ Configuration Reference

| Variable | Description | Default |
|---|---|---|
| `TOPIC` | Niche/focus for trends and content generation | `Godot game development` |
| `BRAND` | Footer watermark / handle across slides | `@intentdev` |
| `GEMINI_API_KEY` | Gemini API key from Google AI Studio | Required |
| `GEMINI_MODEL` | Gemini model to query | `gemini-3.5-flash` |
| `IG_USER_ID` | Optional: Meta Graph API User ID | *(Optional)* |
| `IG_ACCESS_TOKEN` | Optional: Meta Graph API Access Token | *(Optional)* |

---

## 🛡️ License

MIT License. Crafted for automated developer content creation.
