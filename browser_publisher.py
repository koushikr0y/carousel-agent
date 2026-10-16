"""Instagram browser publisher: automated upload & publish via Playwright Firefox.

Uses your existing logged-in Firefox profile session.
No Chromium issues, no Meta Developer account, no Facebook Page, and no API tokens required.
"""
import glob
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def get_firefox_cookies() -> list[dict]:
    """Extract active Instagram login session cookies from local Firefox profile."""
    candidates = (
        glob.glob(os.path.expanduser("~/.config/mozilla/firefox/*/cookies.sqlite"))
        + glob.glob(os.path.expanduser("~/.mozilla/firefox/*/cookies.sqlite"))
    )
    # Sort by newest modified
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    session_file = Path(".ig_session/cookies.json")

    for cf in candidates:
        tmp_db = f"/tmp/ff_cookies_{int(time.time())}.sqlite"
        try:
            shutil.copyfile(cf, tmp_db)
            conn = sqlite3.connect(tmp_db)
            c = conn.cursor()
            c.execute(
                'SELECT host, name, value, path, expiry, isSecure, isHttpOnly, sameSite '
                'FROM moz_cookies WHERE host LIKE "%instagram.com%"'
            )
            rows = c.fetchall()
            has_session = any(r[1] == "sessionid" for r in rows)
            conn.close()
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

            if has_session:
                print(f"[✓] Found active Instagram session in Firefox profile: {cf}")
                cookies = []
                for r in rows:
                    host, name, value, path, expiry, is_secure, is_http_only, same_site = r
                    exp = int(expiry) if expiry else -1
                    # Convert microseconds/milliseconds to seconds
                    if exp > 10_000_000_000_000:
                        exp = int(exp / 1_000_000)
                    elif exp > 10_000_000_000:
                        exp = int(exp / 1_000)
                    if exp <= 0:
                        exp = -1

                    ss = {0: "None", 1: "Lax", 2: "Strict"}.get(same_site, "None")
                    if ss == "None" and not is_secure:
                        ss = "Lax"

                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": host,
                        "path": path,
                        "expires": exp,
                        "secure": bool(is_secure),
                        "httpOnly": bool(is_http_only),
                        "sameSite": ss,
                    })

                # Automatically cache for Docker / cloud deployments
                try:
                    Path(".ig_session").mkdir(exist_ok=True)
                    session_file.write_text(json.dumps(cookies, indent=2))
                except Exception:
                    pass

                return cookies
        except Exception:
            if os.path.exists(tmp_db):
                try:
                    os.remove(tmp_db)
                except Exception:
                    pass

    # Fallback to saved session file if running on a headless server without Firefox desktop
    if session_file.exists():
        try:
            saved_cookies = json.loads(session_file.read_text())
            if any(c.get("name") == "sessionid" for c in saved_cookies):
                print(f"[✓] Loaded active Instagram session from {session_file}")
                return saved_cookies
        except Exception:
            pass

    return []


def publish_via_browser(folder_path: Path, headless: bool = True, auto_share: bool = True) -> None:
    """Uploads carousel slides and caption to Instagram using Firefox session."""
    folder = Path(folder_path)
    if not folder.exists():
        sys.exit(f"Folder not found: {folder}")

    caption_file = folder / "caption.txt"
    caption = caption_file.read_text(encoding="utf-8") if caption_file.exists() else ""

    slides = sorted(
        folder.glob("slide_*.jpg"),
        key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 99,
    )
    if not slides:
        sys.exit(f"No slide_*.jpg images found in {folder}")

    slide_paths = [str(s.resolve()) for s in slides]
    print(f"\n>> Preparing to publish {len(slide_paths)} slides from {folder}")

    # Extract Firefox session cookies
    cookies = get_firefox_cookies()
    if not cookies:
        sys.exit(
            "Could not find an active Instagram session in your Firefox profiles.\n"
            "Please ensure you are logged in to https://www.instagram.com in Firefox."
        )

    with sync_playwright() as p:
        print(f">> Launching Firefox (headless={headless}) with your active Instagram session...")
        browser = p.firefox.launch(headless=headless)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies(cookies)

        page = ctx.new_page()
        print(">> Navigating to Instagram...")
        page.goto("https://www.instagram.com/", wait_until="networkidle", timeout=35000)
        time.sleep(1)

        # 1. Dismiss "Turn on Notifications" modal if present
        try:
            not_now = page.locator('button:has-text("Not Now"), button:has-text("Not now")')
            if not_now.first.is_visible(timeout=4000):
                print(">> Dismissing notification popup...")
                not_now.first.click()
                time.sleep(1)
        except Exception:
            pass

        # 2. Open Create -> Post
        print(">> Opening Create Post dialog...")
        create_btn = page.locator('svg[aria-label="New post"]').first
        create_btn.click()
        time.sleep(1.5)

        post_item = page.locator('span:has-text("Post")').last
        post_item.click()
        time.sleep(2)

        # 3. Upload slides
        print(f">> Uploading all {len(slide_paths)} slides into carousel...")
        file_input = page.locator('input[type="file"]').first
        file_input.wait_for(state="attached", timeout=15000)
        file_input.set_input_files(slide_paths)
        time.sleep(3)

        # 4. Set 4:5 aspect ratio (prevent square crop)
        print(">> Setting aspect ratio to 4:5 portrait...")
        crop_btn = page.locator(
            'button:has(svg[aria-label*="crop" i]), button[aria-label*="crop" i], svg[aria-label*="crop" i]'
        ).first
        try:
            if crop_btn.is_visible(timeout=3000):
                crop_btn.click(timeout=3000, force=True)
                time.sleep(0.8)
                ratio_btn = page.locator(
                    'button:has-text("Original"), button:has-text("4:5"), div[role="button"]:has-text("Original"), span:has-text("Original"), span:has-text("4:5")'
                ).first
                if ratio_btn.is_visible(timeout=3000):
                    ratio_btn.click(timeout=3000, force=True)
                    time.sleep(0.8)
        except Exception as e:
            print(f"   (Aspect ratio note: {e})")

        # 5. Click Next (Filters)
        print(">> Proceeding through filter screen...")
        next_btn = page.locator(
            'div[role="button"]:has-text("Next"), button:has-text("Next")'
        ).last
        next_btn.wait_for(state="visible", timeout=10000)
        next_btn.click()
        time.sleep(2)

        # 6. Click Next (Caption)
        print(">> Proceeding to caption screen...")
        next_btn = page.locator(
            'div[role="button"]:has-text("Next"), button:has-text("Next")'
        ).last
        next_btn.wait_for(state="visible", timeout=10000)
        next_btn.click()
        time.sleep(2)

        # 7. Fill Caption
        print(">> Entering caption and hashtags...")
        caption_box = page.locator(
            'div[aria-label*="Write a caption" i], div[aria-label*="caption" i], div[role="textbox"]'
        ).first
        caption_box.wait_for(state="visible", timeout=10000)
        caption_box.click()
        caption_box.fill(caption)
        time.sleep(2)

        # 8. Target the exact header Share button
        print(">> Locating top header Share button...")
        share_btn = page.locator('div[role="dialog"] div[role="button"]').filter(has_text=re.compile(r"^Share$")).first
        share_btn.wait_for(state="visible", timeout=15000)

        def perform_share():
            print(">> Clicking Share now...")
            share_btn.click()
            print(">> Waiting for upload confirmation (uploading carousel slides & caption)...")
            success = False
            for sec in range(1, 90):
                time.sleep(1)
                dialog_text = page.locator('div[role="dialog"]').inner_text() if page.locator('div[role="dialog"]').count() > 0 else ""
                if "your post has been shared" in dialog_text.lower() or "post shared" in dialog_text.lower():
                    print("\n[✓] Post shared successfully to Instagram!")
                    success = True
                    break
                if sec % 10 == 0:
                    print(f"   ...uploading slides in progress ({sec}s)")
            if not success:
                print("\n[i] Post submitted. Please check Instagram to verify.")
            time.sleep(3)

        if auto_share:
            perform_share()
        else:
            print("\n" + "=" * 65)
            print("                 POST READY IN FIREFOX")
            print("=" * 65)
            print("All slides and caption are loaded into Instagram!")
            print("Look at the opened browser window to preview your carousel.")
            try:
                choice = input("\nType 'y' (or press Enter) to click Share now, or 'q' to cancel: ").strip().lower()
            except EOFError:
                choice = "y"
            if choice in ("", "y", "yes"):
                perform_share()
            else:
                print(">> Share cancelled by user.")
                time.sleep(2)

        browser.close()


if __name__ == "__main__":
    latest_file = Path("posts/latest.json")
    if not latest_file.exists():
        sys.exit("No posts found. Run 'python main.py generate' first.")
    import json
    meta = json.loads(latest_file.read_text())
    publish_via_browser(Path(meta["folder"]))
