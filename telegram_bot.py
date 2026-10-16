"""Telegram Bot for Instagram Carousel Agent.

Enables interactive topic submission, instant multi-slide visual previews,
and one-tap approval before publishing directly to Instagram.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USERS = [u.strip().lstrip("@").lower() for u in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if u.strip()]
BASE_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""


class TelegramAPI:
    """Lightweight, robust Telegram Bot API client using standard requests."""

    def __init__(self, token: str):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"

    def get_me(self) -> dict:
        r = requests.get(f"{self.base}/getMe", timeout=15)
        return r.json()

    def get_updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]:
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            r = requests.get(f"{self.base}/getUpdates", params=params, timeout=timeout + 10)
            if r.status_code == 200:
                data = r.json()
                return data.get("result", [])
        except requests.RequestException:
            pass
        return []

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str = "HTML",
    ) -> dict:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        r = requests.post(f"{self.base}/sendMessage", json=payload, timeout=20)
        return r.json()

    def send_chat_action(self, chat_id: int | str, action: str = "typing") -> None:
        try:
            requests.post(f"{self.base}/sendChatAction", json={"chat_id": chat_id, "action": action}, timeout=10)
        except Exception:
            pass

    def send_carousel_album(self, chat_id: int | str, image_paths: list[Path]) -> bool:
        """Sends up to 10 slides as a single native Telegram swipeable photo album."""
        media = []
        files = {}
        file_handles = []

        try:
            for i, p in enumerate(image_paths[:10]):
                attach_name = f"photo_{i}"
                media.append({"type": "photo", "media": f"attach://{attach_name}"})
                fh = open(p, "rb")
                file_handles.append(fh)
                files[attach_name] = (p.name, fh, "image/jpeg")

            r = requests.post(
                f"{self.base}/sendMediaGroup",
                data={"chat_id": chat_id, "media": json.dumps(media)},
                files=files,
                timeout=90,
            )
            return r.status_code == 200 and r.json().get("ok", False)
        finally:
            for fh in file_handles:
                fh.close()

    def answer_callback_query(self, callback_query_id: str, text: str = "", show_alert: bool = False) -> None:
        try:
            requests.post(
                f"{self.base}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text, "show_alert": show_alert},
                timeout=10,
            )
        except Exception:
            pass

    def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str = "HTML",
    ) -> dict:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        r = requests.post(f"{self.base}/editMessageText", json=payload, timeout=20)
        return r.json()


def is_authorized(user: dict) -> bool:
    """Security check to ensure only the bot owner can command generations & publishing."""
    if not ALLOWED_USERS:
        return True
    username = (user.get("username") or "").lower()
    user_id = str(user.get("id", ""))
    return username in ALLOWED_USERS or user_id in ALLOWED_USERS


def run_bot() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("\n" + "=" * 65)
        print("          TELEGRAM BOT TOKEN REQUIRED")
        print("=" * 65)
        print("To enable Telegram automation:")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot and choose a name & username (e.g. MyGamedevAgentBot)")
        print("3. Copy the HTTP API token provided by BotFather")
        print("4. Add it to your .env file:")
        print("   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz")
        print("5. (Optional) Restrict to your handle:")
        print("   TELEGRAM_ALLOWED_USERS=your_telegram_username")
        print("=" * 65 + "\n")
        sys.exit(1)

    tg = TelegramAPI(token)
    me_resp = tg.get_me()
    if not me_resp.get("ok"):
        sys.exit(f"Failed to connect to Telegram API: {me_resp}")

    bot_info = me_resp["result"]
    bot_name = bot_info.get("first_name", "Carousel Bot")
    bot_username = bot_info.get("username", "")
    print(f"[✓] Connected to Telegram as @{bot_username} ({bot_name})")
    print(">> Listening for commands and topics... (Press Ctrl+C to stop)\n")

    from main import generate, LATEST
    from browser_publisher import publish_via_browser, get_firefox_cookies

    ACTIVE_PUBLISHING_LOCKS: set[str] = set()
    ACTIVE_GENERATING_LOCKS: set[int] = set()

    offset = None

    while True:
        try:
            updates = tg.get_updates(offset=offset, timeout=25)
            for update in updates:
                offset = update["update_id"] + 1

                # 1. Handle Inline Button Callbacks (Approve / Publish / Regenerate)
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb["id"]
                    from_user = cb["from"]
                    chat_id = cb["message"]["chat"]["id"]
                    msg_id = cb["message"]["message_id"]
                    data = cb.get("data", "")

                    if not is_authorized(from_user):
                        tg.answer_callback_query(cb_id, "⚠️ Unauthorized access.")
                        continue

                    if data.startswith("pub:"):
                        folder_name = data.split("pub:", 1)[1]
                        folder_path = Path("posts") / folder_name
                        if not folder_path.exists():
                            tg.answer_callback_query(cb_id, "⚠️ Carousel folder not found!", show_alert=True)
                            continue

                        published_marker = folder_path / "published.json"

                        # Check 1: Prevent duplicate uploads if already published previously
                        if published_marker.exists():
                            tg.answer_callback_query(
                                cb_id,
                                "⚠️ Already Published!\n\nThis carousel is already live on Instagram (@intentdev).",
                                show_alert=True,
                            )
                            tg.edit_message_text(
                                chat_id,
                                msg_id,
                                f"✅ <b>Already Published to Instagram!</b>\n\n"
                                f"<b>Account:</b> @intentdev\n"
                                f"<b>Folder:</b> <code>{folder_name}</code>\n"
                                f"<b>Status:</b> Live on feed",
                                reply_markup=None,
                            )
                            continue

                        # Check 2: Prevent race conditions if button tapped multiple times rapidly
                        if folder_name in ACTIVE_PUBLISHING_LOCKS:
                            tg.answer_callback_query(
                                cb_id,
                                "⏳ Upload in progress! Please wait a moment...",
                                show_alert=False,
                            )
                            continue

                        ACTIVE_PUBLISHING_LOCKS.add(folder_name)
                        tg.answer_callback_query(cb_id, "🚀 Launching Instagram publisher...")

                        # Immediately remove buttons so user cannot click again
                        tg.edit_message_text(
                            chat_id,
                            msg_id,
                            f"⏳ <b>Publishing carousel to Instagram (@intentdev)...</b>\n\n"
                            f"<i>Uploading 6 BentoGrid slides via Firefox session...</i>",
                            reply_markup=None,
                        )

                        try:
                            publish_via_browser(folder_path, headless=True, auto_share=True)
                            # Record permanent marker on disk
                            published_marker.write_text(
                                json.dumps({
                                    "published_at": time.time(),
                                    "folder": folder_name,
                                    "account": os.getenv("BRAND", "@intentdev"),
                                }, indent=2)
                            )
                            tg.edit_message_text(
                                chat_id,
                                msg_id,
                                f"✅ <b>Successfully published to Instagram!</b> 🎉\n\n"
                                f"<b>Account:</b> @intentdev\n"
                                f"<b>Folder:</b> <code>{folder_name}</code>\n"
                                f"<b>Status:</b> Live on feed",
                                reply_markup=None,
                            )
                        except Exception as e:
                            tg.edit_message_text(
                                chat_id,
                                msg_id,
                                f"❌ <b>Publishing Error:</b> <code>{e}</code>\n\n"
                                f"Check local terminal logs for details.",
                                reply_markup={
                                    "inline_keyboard": [
                                        [{"text": "🔄 Retry Publish", "callback_data": f"pub:{folder_name}"}],
                                        [{"text": "❌ Discard", "callback_data": f"discard:{folder_name}"}],
                                    ]
                                },
                            )
                        finally:
                            ACTIVE_PUBLISHING_LOCKS.discard(folder_name)

                    elif data.startswith("regen:"):
                        topic = data.split("regen:", 1)[1]
                        if chat_id in ACTIVE_GENERATING_LOCKS:
                            tg.answer_callback_query(cb_id, "⏳ A carousel is already generating, please wait!")
                            continue

                        ACTIVE_GENERATING_LOCKS.add(chat_id)
                        tg.answer_callback_query(cb_id, f"Regenerating: {topic}...")
                        tg.send_message(chat_id, f"🔄 <b>Generating new carousel angle for:</b> <i>{topic}</i>...")
                        tg.send_chat_action(chat_id, "upload_photo")

                        try:
                            folder = generate(custom_topic=topic)
                            slides = sorted(list(folder.glob("slide_*.jpg")))
                            caption = (folder / "caption.txt").read_text(encoding="utf-8")

                            tg.send_carousel_album(chat_id, slides)
                            tg.send_message(
                                chat_id,
                                f"<b>📝 Suggested Caption:</b>\n\n{caption}\n\n"
                                f"👉 <i>Review the slides above and tap an option below:</i>",
                                reply_markup={
                                    "inline_keyboard": [
                                        [{"text": "🚀 Approve & Publish to Instagram", "callback_data": f"pub:{folder.name}"}],
                                        [{"text": "🔄 Regenerate Different Angle", "callback_data": f"regen:{topic}"}],
                                        [{"text": "❌ Discard", "callback_data": f"discard:{folder.name}"}],
                                    ]
                                },
                            )
                        except Exception as e:
                            tg.send_message(chat_id, f"❌ Generation error: <code>{e}</code>")
                        finally:
                            ACTIVE_GENERATING_LOCKS.discard(chat_id)

                    elif data.startswith("discard:"):
                        tg.answer_callback_query(cb_id, "Carousel discarded.")
                        tg.edit_message_text(chat_id, msg_id, "🗑️ <i>Carousel discarded. Ready for the next topic!</i>")

                    continue

                # 2. Handle Text Messages & Commands
                if "message" in update:
                    msg = update["message"]
                    from_user = msg.get("from", {})
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "").strip()

                    if not text:
                        continue

                    if not is_authorized(from_user):
                        tg.send_message(
                            chat_id,
                            f"⛔ <b>Access Restricted.</b>\nYour Telegram ID: <code>{from_user.get('id')}</code>\n"
                            f"Username: <code>@{from_user.get('username', 'none')}</code>\n\n"
                            f"Add your handle to <code>TELEGRAM_ALLOWED_USERS</code> in <code>.env</code>.",
                        )
                        continue

                    if text in ("/start", "/help"):
                        default_topic = os.getenv("TOPIC", "Godot game development")
                        brand = os.getenv("BRAND", "@intentdev")
                        tg.send_message(
                            chat_id,
                            f"👋 <b>Welcome to the Instagram Carousel Agent!</b>\n\n"
                            f"🎨 <b>Current Topic Focus:</b> <i>{default_topic}</i>\n"
                            f"🏷️ <b>Brand Handle:</b> <i>{brand}</i>\n"
                            f"📐 <b>Style:</b> Glassmorphic BentoGrid Dark Mode (4:5 Portrait)\n\n"
                            f"<b>How to use:</b>\n"
                            f"1. <b>Send any topic or idea</b> directly in this chat:\n"
                            f"   • <i>Godot 4.3 NavMesh Pathfinding</i>\n"
                            f"   • <i>Putting 5000 Particles on the GPU in Godot</i>\n"
                            f"   • <i>Godot Node Architecture Patterns</i>\n"
                            f"2. The bot will create 6 BentoGrid slides and preview them as a photo album.\n"
                            f"3. Tap <b>[ 🚀 Approve & Publish ]</b> to immediately share it to Instagram!\n\n"
                            f"<b>Commands:</b>\n"
                            f"• <code>/generate [optional topic]</code> - Create new carousel\n"
                            f"• <code>/status</code> - Check Instagram login session\n"
                            f"• <code>/latest</code> - Preview the last generated post\n",
                        )
                        continue

                    elif text == "/status":
                        cookies = get_firefox_cookies()
                        if cookies:
                            tg.send_message(
                                chat_id,
                                f"✅ <b>Instagram Session: Active</b>\n"
                                f"• Account: <b>@intentdev</b>\n"
                                f"• Publisher: Firefox Session Automation\n"
                                f"• Ready to publish without Meta API keys!",
                            )
                        else:
                            tg.send_message(
                                chat_id,
                                "⚠️ <b>No active Instagram session found in Firefox.</b>\n"
                                "Please log into https://www.instagram.com in your Firefox browser.",
                            )
                        continue

                    elif text == "/latest":
                        if not LATEST.exists():
                            tg.send_message(chat_id, "No carousels generated yet. Send a topic to create one!")
                            continue
                        meta = json.loads(LATEST.read_text())
                        folder = Path(meta["folder"])
                        slides = sorted(list(folder.glob("slide_*.jpg")))
                        caption = (folder / "caption.txt").read_text(encoding="utf-8") if (folder / "caption.txt").exists() else ""

                        tg.send_carousel_album(chat_id, slides)
                        is_pub = (folder / "published.json").exists()
                        action_btn = (
                            {"text": "✅ Already Published", "callback_data": f"pub:{folder.name}"}
                            if is_pub
                            else {"text": "🚀 Approve & Publish to Instagram", "callback_data": f"pub:{folder.name}"}
                        )
                        tg.send_message(
                            chat_id,
                            f"<b>📂 Latest Carousel ({folder.name}):</b>\n\n{caption}",
                            reply_markup={
                                "inline_keyboard": [
                                    [action_btn],
                                    [{"text": "❌ Discard", "callback_data": f"discard:{folder.name}"}],
                                ]
                            },
                        )
                        continue

                    # Treat any text or /generate <topic> as a carousel creation request
                    if chat_id in ACTIVE_GENERATING_LOCKS:
                        tg.send_message(chat_id, "⏳ <b>A carousel is already being generated!</b> Please wait a few seconds.")
                        continue

                    topic = text
                    if topic.startswith("/generate"):
                        topic = topic.removeprefix("/generate").strip()
                    if not topic:
                        topic = os.getenv("TOPIC", "Godot game development")

                    ACTIVE_GENERATING_LOCKS.add(chat_id)
                    tg.send_message(
                        chat_id,
                        f"🎨 <b>Creating BentoGrid Carousel...</b>\n\n"
                        f"• <b>Topic:</b> <i>{topic}</i>\n"
                        f"• <b>Model:</b> Gemini 3.5 Flash\n"
                        f"• <b>Format:</b> 6 Slides (1080x1350 BentoGrid)\n\n"
                        f"<i>Please wait ~20 seconds while slides are being written & rendered...</i>",
                    )
                    tg.send_chat_action(chat_id, "upload_photo")

                    try:
                        folder = generate(custom_topic=topic)
                        slides = sorted(list(folder.glob("slide_*.jpg")))
                        caption = (folder / "caption.txt").read_text(encoding="utf-8")

                        tg.send_carousel_album(chat_id, slides)
                        tg.send_message(
                            chat_id,
                            f"<b>📝 Suggested Caption:</b>\n\n{caption}\n\n"
                            f"👉 <b>Review the 6 slides above. What would you like to do?</b>",
                            reply_markup={
                                "inline_keyboard": [
                                    [{"text": "🚀 Approve & Publish to Instagram", "callback_data": f"pub:{folder.name}"}],
                                    [{"text": "🔄 Regenerate Different Angle", "callback_data": f"regen:{topic}"}],
                                    [{"text": "❌ Discard", "callback_data": f"discard:{folder.name}"}],
                                ]
                            },
                        )
                    except Exception as e:
                        tg.send_message(chat_id, f"❌ <b>Generation Failed:</b> <code>{e}</code>")
                    finally:
                        ACTIVE_GENERATING_LOCKS.discard(chat_id)

        except KeyboardInterrupt:
            print("\n>> Bot stopped by user.")
            break
        except Exception as e:
            print(f"[warn] Polling error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    run_bot()
