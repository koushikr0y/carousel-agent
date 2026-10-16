"""Instagram carousel agent: trends -> LLM script -> BentoGrid slides -> publish.

Usage:
    python main.py selftest         # render sample BentoGrid slides (checks Chromium/fonts, no keys needed)
    python main.py trends           # fetch trend signals for TOPIC (no keys needed)
    python main.py generate         # build modern BentoGrid slides + caption into posts/<timestamp>/ (needs GEMINI_API_KEY)
    python main.py ig-login         # verify active Instagram session from your local Firefox profile
    python main.py publish          # publish latest carousel using your active Firefox Instagram session
    python main.py check-ig         # verify Meta Graph API credentials if using official API
"""
import datetime as dt
import html
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import feedparser
import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()  # reads .env in the project folder if present

# ---------- config (all via environment variables) ----------
TOPIC = os.getenv("TOPIC", "Godot game development")
REGION = os.getenv("REGION", "US")  # country code for trends/news, e.g. US, IN, GB
BRAND = os.getenv("BRAND", "@intentdev")  # footer brand handle on each slide
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")  # change if retired
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "")  # e.g. /usr/bin/chromium (Arch/EndeavourOS)
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "")
GRAPH = f"https://graph.facebook.com/{os.getenv('GRAPH_VERSION', 'v23.0')}"
REPO = os.getenv("GITHUB_REPOSITORY", "")  # owner/name, set automatically in Actions or .env
BRANCH = os.getenv("GITHUB_REF_NAME", "main")

POSTS = Path("posts")
HISTORY = POSTS / "history.json"
LATEST = POSTS / "latest.json"


# ---------- 1. trend signals ----------
def get_signals(topic: str) -> list[str]:
    signals = []
    try:  # Google Trends (unofficial, can be rate-limited, so failure is OK)
        from pytrends.request import TrendReq

        pt = TrendReq(hl="en-US", tz=0)
        pt.build_payload([topic], timeframe="now 7-d", geo=REGION)
        rising = pt.related_queries().get(topic, {}).get("rising")
        if rising is not None:
            signals += [f"Rising search: {q}" for q in rising["query"].head(8).tolist()]
    except Exception as e:
        print(f"[warn] pytrends failed: {e}")

    url = (
        "https://news.google.com/rss/search?q="
        f"{quote(topic + ' when:3d')}&hl=en-{REGION}&gl={REGION}&ceid={REGION}:en"
    )
    feed = feedparser.parse(url)
    signals += [f"News headline: {e.title}" for e in feed.entries[:10]]
    return signals


# ---------- 2. write the carousel with Gemini ----------
def build_prompt(topic: str, signals: list[str], history: list[str]) -> str:
    return f"""You are a top-tier tech educator and social media designer running an Instagram page about "{topic}".
Today's date: {dt.date.today().isoformat()}.

Current trend signals:
{chr(10).join('- ' + s for s in signals)}

Recent trends already posted (do NOT repeat): {history or 'none'}

Pick ONE compelling trend or concept from the signals and turn it into a high-value, modern BentoGrid educational carousel (6 to 8 slides).
Rules:
- Be factual and specific to {topic}. Focus on practical insights, architecture, performance, or engine capabilities.
- Slide 1 MUST be a scroll-stopping hook title.
- Slides 2 to N-1 MUST teach step-by-step practical insights.
- Slide N MUST be a call to action (save, comment, follow).

Return STRICT JSON ONLY, matching exactly this structure:
{{
  "trend": "short name of chosen trend",
  "caption": "max 1500 chars, engaging developer tone, bullet takeaways, ends with an interactive question, then 5-8 relevant hashtags",
  "slides": [
    {{
      "badge": "2-3 word uppercase category, e.g. GODOT 4.3, ARCHITECTURE, PERFORMANCE, PRO TIP, DEV TOOLING",
      "title": "Punchy title (max 7 words)",
      "body": "Engaging explanation (max 35 words)",
      "card_1_label": "Uppercase badge, e.g. PRO TIP, KEY BENEFIT, CODE INSIGHT, or WHY IT MATTERS",
      "card_1_text": "One crisp takeaway (max 18 words)",
      "card_2_label": "Uppercase badge, e.g. DEV IMPACT, BEST PRACTICE, or WATCH OUT",
      "card_2_text": "Practical benefit or insight (max 18 words)"
    }}
  ]
}}"""


def ask_gemini(prompt: str) -> dict:
    models = [GEMINI_MODEL]
    if "flash-lite" not in GEMINI_MODEL:
        models.append("gemini-3.5-flash-lite")

    last_err = None
    for model in models:
        for attempt in range(3):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": GEMINI_KEY},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
                    },
                    timeout=90,
                )
                if r.status_code in (429, 503):
                    time.sleep(2 * (attempt + 1))
                    continue
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(2)
    raise last_err


# ---------- 3. render slides (HTML -> PNG -> JPEG) ----------
def render_slide_html(s: dict, i: int, total: int, brand: str, topic: str) -> str:
    """Generate modern, high-contrast BentoGrid HTML for an Instagram slide."""
    is_cover = (i == 1)
    is_cta = (i == total)
    counter_left = f"{i:02d}"
    counter_right = f"{total:02d}"

    badge = html.escape(s.get("badge") or ("GAMEDEV HOOK" if is_cover else ("NEXT STEPS" if is_cta else "CORE CONCEPT")))
    raw_title = s.get("title", "")
    title_words = raw_title.split()
    if len(title_words) > 2:
        main_part = html.escape(" ".join(title_words[:-2]))
        grad_part = html.escape(" ".join(title_words[-2:]))
        title_html = f'{main_part} <span class="gradient-text">{grad_part}</span>'
    else:
        title_html = f'<span class="gradient-text">{html.escape(raw_title)}</span>'

    body_html = html.escape(s.get("body", ""))

    c1_lbl = html.escape(s.get("card_1_label") or ("QUICK SUMMARY" if is_cover else ("SAVE POST" if is_cta else "KEY INSIGHT")))
    c1_txt = html.escape(s.get("card_1_text") or ("Essential breakdown for Godot developers." if is_cover else ("Bookmark this guide for your next game project." if is_cta else "Optimized for cleaner architecture and speed.")))

    c2_lbl = html.escape(s.get("card_2_label") or ("WHY IT MATTERS" if is_cover else ("JOIN THE CHAT" if is_cta else "DEV IMPACT")))
    c2_txt = html.escape(s.get("card_2_text") or ("Level up your workflow with modern patterns." if is_cover else ("Drop your questions and thoughts below." if is_cta else "Saves hours of debugging in production.")))

    swipe_text = "FOLLOW FOR MORE ➔" if is_cta else ("SWIPE TO DISCOVER ➔" if is_cover else "SWIPE ➔")
    topic_badge = html.escape(topic.upper())
    brand_text = html.escape(brand)

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1080px;
    height: 1350px;
    background-color: #080c14;
    background-image:
      radial-gradient(circle at 12% 15%, rgba(71, 140, 191, 0.28) 0%, transparent 45%),
      radial-gradient(circle at 88% 82%, rgba(99, 102, 241, 0.24) 0%, transparent 45%),
      radial-gradient(circle at 50% 50%, rgba(56, 189, 248, 0.08) 0%, transparent 60%);
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    color: #f8fafc;
    padding: 70px 65px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
    position: relative;
  }}

  body::before {{
    content: '';
    position: absolute;
    inset: 0;
    background-image: linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
    background-size: 40px 40px;
    mask-image: radial-gradient(ellipse at center, black 40%, transparent 80%);
    pointer-events: none;
  }}

  /* Top Header */
  .top-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    z-index: 10;
  }}
  .tag-badge {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: rgba(71, 140, 191, 0.16);
    border: 1px solid rgba(71, 140, 191, 0.4);
    color: #38bdf8;
    padding: 10px 22px;
    border-radius: 999px;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  .slide-counter {{
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 10px 22px;
    border-radius: 999px;
    font-size: 22px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #94a3b8;
  }}
  .slide-counter span {{ color: #f8fafc; }}

  /* Bento Grid */
  .bento-grid {{
    display: flex;
    flex-direction: column;
    gap: 24px;
    position: relative;
    z-index: 10;
    margin: 30px 0;
    flex-grow: 1;
    justify-content: center;
  }}

  .bento-card {{
    background: rgba(15, 23, 42, 0.68);
    backdrop-filter: blur(16px);
    border: 1.5px solid rgba(255, 255, 255, 0.09);
    border-radius: 32px;
    padding: 44px;
    box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    position: relative;
    overflow: hidden;
  }}

  .bento-card::after {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.25), transparent);
  }}

  .hero-card {{
    padding: 52px 48px;
    background: linear-gradient(145deg, rgba(30, 41, 59, 0.72), rgba(15, 23, 42, 0.88));
    border: 1.5px solid rgba(71, 140, 191, 0.35);
  }}
  .card-label {{
    display: inline-block;
    color: #38bdf8;
    font-size: 20px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 20px;
  }}
  .hero-title {{
    font-size: {'68px' if is_cover else '54px'};
    font-weight: 800;
    line-height: 1.14;
    letter-spacing: -0.025em;
    color: #ffffff;
    margin-bottom: 24px;
  }}
  .gradient-text {{
    background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .hero-body {{
    font-size: {'36px' if is_cover else '32px'};
    line-height: 1.48;
    color: #cbd5e1;
    font-weight: 400;
  }}

  .bento-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }}
  .mini-card {{
    padding: 34px 36px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .mini-label {{
    font-size: 18px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 14px;
  }}
  .accent-cyan {{ color: #38bdf8; }}
  .accent-purple {{ color: #a78bfa; }}
  .mini-text {{
    font-size: 27px;
    line-height: 1.38;
    color: #f1f5f9;
    font-weight: 600;
  }}

  /* Bottom Bar */
  .bottom-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    z-index: 10;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 24px;
  }}
  .brand-pill {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 24px;
    font-weight: 700;
    color: #f8fafc;
  }}
  .brand-dot {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 12px #38bdf8;
  }}
  .swipe-pill {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 20px;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}
</style>
</head>
<body>
  <div class="top-bar">
    <div class="tag-badge">🎮 {topic_badge}</div>
    <div class="slide-counter"><span>{counter_left}</span> / {counter_right}</div>
  </div>

  <div class="bento-grid">
    <div class="bento-card hero-card">
      <div class="card-label">⚡ {badge}</div>
      <h1 class="hero-title">{title_html}</h1>
      <p class="hero-body">{body_html}</p>
    </div>

    <div class="bento-row">
      <div class="bento-card mini-card">
        <div class="mini-label accent-cyan">⚡ {c1_lbl}</div>
        <p class="mini-text">{c1_txt}</p>
      </div>
      <div class="bento-card mini-card">
        <div class="mini-label accent-purple">💡 {c2_lbl}</div>
        <p class="mini-text">{c2_txt}</p>
      </div>
    </div>
  </div>

  <div class="bottom-bar">
    <div class="brand-pill">
      <div class="brand-dot"></div>
      {brand_text}
    </div>
    <div class="swipe-pill">{swipe_text}</div>
  </div>
</body>
</html>"""


def render(slides: list[dict], folder: Path) -> None:
    from playwright.sync_api import sync_playwright

    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH or None)
        page = browser.new_page(viewport={"width": 1080, "height": 1350})  # 4:5 portrait
        for i, s in enumerate(slides, 1):
            slide_html = render_slide_html(s, i, len(slides), BRAND, TOPIC)
            page.set_content(slide_html)
            png = folder / f"slide_{i}.png"
            page.screenshot(path=str(png))
            # Instagram's API only accepts JPEG
            Image.open(png).convert("RGB").save(folder / f"slide_{i}.jpg", quality=95)
            png.unlink()
        browser.close()


def generate() -> None:
    signals = get_signals(TOPIC)
    if not signals:
        sys.exit("No trend signals found. Aborting.")
    POSTS.mkdir(exist_ok=True)
    history = json.loads(HISTORY.read_text()) if HISTORY.exists() else []

    plan = ask_gemini(build_prompt(TOPIC, signals, history[-15:]))
    slides = plan["slides"][:10]  # API max is 10 items per carousel
    if len(slides) < 3:
        sys.exit("Model returned too few slides.")

    folder = POSTS / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M")
    render(slides, folder)
    (folder / "caption.txt").write_text(plan["caption"], encoding="utf-8")
    LATEST.write_text(
        json.dumps({"folder": folder.as_posix(), "slides": len(slides), "trend": plan["trend"]})
    )
    HISTORY.write_text(json.dumps((history + [plan["trend"]])[-30:], indent=2))
    print(f"Generated {len(slides)} BentoGrid slides in {folder} (trend: {plan['trend']})")
    print("\nCaption:\n" + plan["caption"])


# ---------- test helpers (no API keys needed) ----------
def trends() -> None:
    """Test only the trend-fetching step."""
    for s in get_signals(TOPIC):
        print("-", s)


def selftest() -> None:
    """Render 3 sample BentoGrid slides to check Chromium + fonts work."""
    sample = [
        {
            "badge": "GAMEDEV HOOK",
            "title": "Why Indie Devs Love Godot 4",
            "body": "Fast, lightweight, and 100% free forever. Here is why the community is shifting.",
            "card_1_label": "LIGHTWEIGHT",
            "card_1_text": "Under 100MB download with instant startup and zero bloat.",
            "card_2_label": "100% FREE",
            "card_2_text": "True MIT open-source license with zero royalties.",
        },
        {
            "badge": "NODE ARCHITECTURE",
            "title": "Mastering the Node Tree Pattern",
            "body": "Everything in Godot is a Scene and every Scene is a tree of Nodes. Keep them decoupled.",
            "card_1_label": "PRO TIP",
            "card_1_text": "Use Signal buses instead of direct node references.",
            "card_2_label": "BENEFIT",
            "card_2_text": "Effortless refactoring and modular game mechanics.",
        },
        {
            "badge": "COMMUNITY CTA",
            "title": "Build Your Next Game in Godot",
            "body": "Save this carousel and share it with your fellow developers.",
            "card_1_label": "SAVE POST",
            "card_1_text": "Bookmark this reference for your next prototype.",
            "card_2_label": "FOLLOW US",
            "card_2_text": "Follow @intentdev for daily gamedev breakdowns.",
        },
    ]
    folder = POSTS / "selftest"
    render(sample, folder)
    print(f"Rendered sample BentoGrid slides to {folder}/ - open them to check.")


# ---------- 4. publish via Instagram Graph API ----------
def graph(method: str, path: str, **params) -> dict:
    params["access_token"] = IG_TOKEN
    r = requests.request(
        method,
        f"{GRAPH}/{path}",
        params=params if method == "GET" else None,
        data=params if method != "GET" else None,
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"Graph API error {r.status_code}: {r.text}")
    return r.json()


def wait_for_url(url: str, tries: int = 24) -> None:
    for _ in range(tries):
        try:
            res = requests.head(url, timeout=15)
            if res.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError(f"Image not publicly reachable: {url}")


def wait_for_container(cid: str, tries: int = 40) -> None:
    for _ in range(tries):
        status = graph("GET", cid, fields="status_code").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {cid} failed with status {status}")
        time.sleep(3)
    raise RuntimeError(f"Container {cid} timed out")


def check_ig() -> None:
    """Validate Instagram API credentials and connection."""
    print("=" * 60)
    print("       Instagram Publishing Credentials & Connection Check")
    print("=" * 60)

    if not IG_USER_ID or not IG_TOKEN:
        print("\n[!] Incomplete Instagram configuration in .env:")
        print(f"    IG_USER_ID:      {repr(IG_USER_ID) if IG_USER_ID else 'EMPTY'}")
        print(f"    IG_ACCESS_TOKEN: {'SET' if IG_TOKEN else 'EMPTY'}")
        print("\n--- Setup Guide to Enable Instagram Publishing ---")
        print("1. Switch your Instagram account to Professional (Business or Creator):")
        print("   In Instagram App: Settings -> Account type and tools -> Switch to Professional account.")
        print("2. Link your Instagram account to a Facebook Page (Meta Business Suite / FB Settings).")
        print("3. Create a Meta Developer App at https://developers.facebook.com:")
        print("   - Type: 'Business' or 'Other'")
        print("   - Add Product: 'Instagram Graph API'")
        print("4. Get your IG_USER_ID and IG_ACCESS_TOKEN:")
        print("   - In Graph API Explorer (https://developers.facebook.com/tools/explorer/):")
        print("   - Select your App.")
        print("   - Under Permissions, add: instagram_basic, instagram_content_publish, pages_read_engagement")
        print("   - Click 'Generate Access Token'")
        print("   - Query: GET me/accounts?fields=instagram_business_account{id,username}")
        print("   - Copy the numeric 'id' inside 'instagram_business_account' -> set as IG_USER_ID in .env")
        print("   - Exchange your token for a Long-Lived Page Access Token (valid for 60 days) -> set as IG_ACCESS_TOKEN in .env")
        print("\nOnce saved in .env, run 'python main.py check-ig' again to verify!")
        return

    print(f"\n>> Querying Meta Graph API for Instagram User ID: {IG_USER_ID}...")
    try:
        data = graph("GET", IG_USER_ID, fields="id,username,name,profile_picture_url")
        print("\n[✓] Successfully connected to Instagram Professional Account!")
        print(f"    • Username: @{data.get('username')}")
        print(f"    • Name:     {data.get('name')}")
        print(f"    • User ID:  {data.get('id')}")
        print("\nYour credentials are valid and ready to publish with 'python main.py publish'!")
    except Exception as e:
        print(f"\n[!] Connection failed: {e}")
        print("Please check that your IG_USER_ID is numeric and IG_ACCESS_TOKEN is not expired.")


def publish() -> None:
    if not LATEST.exists():
        sys.exit("No generated carousel found in posts/. Run 'python main.py generate' first.")

    # Seamless fallback: If Meta Graph API credentials are not set, use browser automation
    if not IG_USER_ID or not IG_TOKEN:
        print("[i] Meta Developer API credentials not configured in .env.")
        print(">> Falling back to Playwright browser automation (no API keys needed)...")
        from browser_publisher import publish_via_browser
        meta = json.loads(LATEST.read_text())
        publish_via_browser(Path(meta["folder"]))
        return

    meta = json.loads(LATEST.read_text())
    folder = meta["folder"]
    caption = (Path(folder) / "caption.txt").read_text(encoding="utf-8")

    # Determine public image URL base
    image_base = IMAGE_BASE_URL.rstrip("/")
    if not image_base:
        repo = REPO
        if not repo:
            try:
                import subprocess
                remote_out = subprocess.check_output(
                    ["git", "config", "--get", "remote.origin.url"], text=True
                ).strip()
                if "github.com" in remote_out:
                    parts = remote_out.split("github.com")[-1].strip("/:").removesuffix(".git").split("/")
                    if len(parts) >= 2:
                        repo = f"{parts[0]}/{parts[1]}"
            except Exception:
                pass

        if repo:
            image_base = f"https://raw.githubusercontent.com/{repo}/{BRANCH}/{folder}"
        else:
            sys.exit(
                "Instagram requires public HTTPS URLs for your images.\n"
                "Options to provide public image URLs:\n"
                "  1. Push project to a public GitHub repo and set GITHUB_REPOSITORY=username/repo in .env\n"
                "  2. Or host images / tunnel them and set IMAGE_BASE_URL=https://... in .env\n"
                "  3. Or run 'python main.py publish-browser' to publish directly via your browser."
            )

    print(f">> Checking image accessibility at: {image_base}...")
    children = []
    for i in range(1, meta["slides"] + 1):
        url = f"{image_base}/slide_{i}.jpg"
        print(f"   Slide {i}: {url}")
        wait_for_url(url)
        res = graph("POST", f"{IG_USER_ID}/media", image_url=url, is_carousel_item="true")
        children.append(res["id"])

    print(">> Processing slide containers...")
    for cid in children:
        wait_for_container(cid)

    print(">> Creating carousel container...")
    parent = graph(
        "POST",
        f"{IG_USER_ID}/media",
        media_type="CAROUSEL",
        children=",".join(children),
        caption=caption,
    )["id"]
    wait_for_container(parent)

    print(">> Publishing to Instagram...")
    post = graph("POST", f"{IG_USER_ID}/media_publish", creation_id=parent)
    print(f"\n[✓] Published successfully! Instagram Media ID: {post['id']}")


def publish_browser() -> None:
    """Explicitly publish latest carousel via Playwright browser automation."""
    if not LATEST.exists():
        sys.exit("No generated carousel found in posts/. Run 'python main.py generate' first.")
    from browser_publisher import publish_via_browser
    meta = json.loads(LATEST.read_text())
    headless = "--head" not in sys.argv and "--watch" not in sys.argv
    publish_via_browser(Path(meta["folder"]), headless=headless, auto_share=True)


def ig_login() -> None:
    """Verify Instagram session from local Firefox profile."""
    from browser_publisher import get_firefox_cookies
    cookies = get_firefox_cookies()
    if cookies:
        print("[✓] Instagram session is active and verified from your Firefox profile!")
        print("    Ready to publish with: python main.py publish")
    else:
        print("[!] No active Instagram session found in Firefox.")
        print("    Please log into https://www.instagram.com in your Firefox browser first.")


if __name__ == "__main__":
    commands = {
        "generate": generate,
        "publish": publish,
        "publish-browser": publish_browser,
        "ig-login": ig_login,
        "trends": trends,
        "selftest": selftest,
        "check-ig": check_ig,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
