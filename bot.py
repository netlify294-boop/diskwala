import os
import re
import asyncio
import aiohttp
import aiofiles
import logging
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatAction
from config import BOT_TOKEN, COOKIE, PORT, WEBHOOK_URL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Flask app (Render ko lagta hai web server chal raha hai) ─────────────────
flask_app = Flask(__name__)

DISKWALA_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:diskwala\.com|1024terabox\.com|terabox\.com|"
    r"teraboxapp\.com|4funbox\.com|mirrobox\.com|nephobox\.com|freeterabox\.com)"
    r"/(?:s|sharing/link|app)/([A-Za-z0-9_-]+)"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.diskwala.com/",
}

# ─── Telegram Application (global) ───────────────────────────────────────────
ptb_app: Application = None


# ─── VIDEO INFO EXTRACTION ────────────────────────────────────────────────────

async def get_video_info(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url, headers=HEADERS, allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            final_url = str(resp.url)
    except Exception as e:
        logger.error(f"Redirect error: {e}")
        final_url = url

    parsed = urlparse(final_url)
    params = parse_qs(parsed.query)
    surl = params.get("surl", [None])[0]

    # /app/ format se surl extract karo
    if not surl:
        path_parts = parsed.path.rstrip("/").split("/")
        surl = path_parts[-1] if path_parts else None

    if not surl:
        return {"error": "URL se share token nahi mila"}

    # Method 1: TeraBox shorturlinfo API
    cookie_headers = {**HEADERS, "Cookie": COOKIE} if COOKIE else HEADERS
    for api_base in ["https://www.1024tera.com", "https://www.terabox.com", "https://www.diskwala.com"]:
        try:
            api_url = f"{api_base}/api/shorturlinfo"
            api_params = {"app_id": "250528", "shorturl": surl, "root": "1"}
            async with session.get(api_url, params=api_params, headers=cookie_headers,
                                   timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json(content_type=None)
                if data.get("errno") == 0:
                    file_list = data.get("list", [])
                    video_file = next((f for f in file_list if f.get("isdir") == 0), None)
                    if video_file:
                        return {
                            "filename": video_file.get("server_filename", "video.mp4"),
                            "size": int(video_file.get("size", 0)),
                            "dlink": video_file.get("dlink", ""),
                            "thumbnail": video_file.get("thumbs", {}).get("url3", ""),
                        }
        except Exception as e:
            logger.error(f"API {api_base} error: {e}")
            continue

    # Method 2: fileinfo API
    try:
        api_url = "https://www.1024tera.com/api/file/fileinfo"
        api_params = {"app_id": "250528", "shorturl": surl}
        async with session.get(api_url, params=api_params, headers=cookie_headers,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json(content_type=None)
            if data.get("errno") == 0:
                info = data.get("list", [{}])[0]
                if info.get("dlink"):
                    return {
                        "filename": info.get("server_filename", "video.mp4"),
                        "size": int(info.get("size", 0)),
                        "dlink": info.get("dlink", ""),
                        "thumbnail": "",
                    }
    except Exception as e:
        logger.error(f"fileinfo API error: {e}")

    return await get_video_info_v2(session, url, surl)


async def get_video_info_v2(session: aiohttp.ClientSession, url: str, surl: str) -> dict:
    try:
        async with session.post(
            "https://diskwala.net/api/get",
            json={"url": url},
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                return {
                    "filename": data.get("filename", "video.mp4"),
                    "size": data.get("size", 0),
                    "dlink": data.get("url", ""),
                    "thumbnail": data.get("thumbnail", ""),
                }
    except Exception as e:
        logger.error(f"V2 API error: {e}")

    return {
        "filename": "video.mp4",
        "size": 0,
        "dlink": f"https://www.diskwala.com/file/{surl}",
        "thumbnail": "",
        "fallback": True,
    }


async def download_file(session: aiohttp.ClientSession, dlink: str, filepath: str) -> bool:
    dl_headers = {**HEADERS}
    if COOKIE:
        dl_headers["Cookie"] = COOKIE
    try:
        async with session.get(dlink, headers=dl_headers, allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=300)) as resp:
            if resp.status != 200:
                return False
            async with aiofiles.open(filepath, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 1024):
                    await f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False


def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ─── TELEGRAM HANDLERS ────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *DiskWala Video Downloader Bot*\n\n"
        "Koi bhi DiskWala link bhejo, main video seedha yahan bhej dunga!\n\n"
        "✅ *Supported:*\n"
        "• `diskwala.com/s/...`\n"
        "• `diskwala.com/sharing/link/...`\n\n"
        "📌 Link copy karo aur yahan paste karo — bas!",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Help*\n\n"
        "1️⃣ DiskWala app mein video ka share link copy karo\n"
        "2️⃣ Is bot ko link bhejo\n"
        "3️⃣ Video download hokar seedha mil jaegi ✅\n\n"
        "⚠️ Sirf *public* share links kaam karte hain",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text.strip()

    if "diskwala.com" not in text and not DISKWALA_PATTERN.search(text):
        await message.reply_text(
            "❌ Yeh DiskWala link nahi lagta!\n"
            "Format: `https://diskwala.com/s/XXXXXX`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    status_msg = await message.reply_text("🔍 Link check ho rahi hai...")
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    async with aiohttp.ClientSession() as session:
        await status_msg.edit_text("📡 Video info fetch ho rahi hai...")
        info = await get_video_info(session, text)

        if "error" in info:
            await status_msg.edit_text(
                f"❌ *Error:* {info['error']}\n\nLink dobara check karein.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        filename = info["filename"]
        size = info["size"]
        dlink = info["dlink"]

        if not dlink:
            await status_msg.edit_text("❌ Download link nahi mila. Link private ho sakta hai.")
            return

        size_str = format_size(size)
        await status_msg.edit_text(
            f"📥 *Downloading...*\n\n"
            f"📄 `{filename}`\n"
            f"💾 {size_str}\n\n"
            f"⏳ Thoda wait karein...",
            parse_mode=ParseMode.MARKDOWN,
        )

        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_VIDEO)

        safe_name = re.sub(r"[^\w\-_\. ]", "_", filename)
        filepath = f"/tmp/{safe_name}"
        success = await download_file(session, dlink, filepath)

        if not success:
            await status_msg.edit_text(
                f"⚠️ Direct upload nahi ho saka.\n\n"
                f"📄 *{filename}* ({size_str})\n\nNeeche se download karein 👇",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 Download Link", url=dlink)]]
                ),
            )
            return

        try:
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if file_size_mb > 50:
                await status_msg.edit_text(
                    f"⚠️ File badi hai ({size_str}) — Telegram 50MB limit.\nDirect link use karein 👇",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔗 Download Link", url=dlink)]]
                    ),
                )
            else:
                caption = f"✅ *{filename}*\n💾 {size_str}"
                with open(filepath, "rb") as vf:
                    if filename.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".webm")):
                        await message.reply_video(video=vf, caption=caption,
                                                  parse_mode=ParseMode.MARKDOWN,
                                                  supports_streaming=True)
                    else:
                        await message.reply_document(document=vf, caption=caption,
                                                     parse_mode=ParseMode.MARKDOWN)
                await status_msg.delete()
        except Exception as e:
            logger.error(f"Send error: {e}")
            await status_msg.edit_text(
                "❌ File send nahi ho saki.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 Download Link", url=dlink)]]
                ),
            )
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


# ─── FLASK ROUTES ─────────────────────────────────────────────────────────────

@flask_app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "bot": "DiskWala Downloader is running ✅"})

@flask_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})

@flask_app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Telegram webhook endpoint"""
    if ptb_app is None:
        return jsonify({"error": "Bot not ready"}), 503
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    asyncio.run(ptb_app.process_update(update))
    return jsonify({"ok": True})


# ─── STARTUP ─────────────────────────────────────────────────────────────────

def create_bot_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    return app


async def setup_webhook(app: Application):
    webhook_endpoint = f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
    await app.bot.set_webhook(url=webhook_endpoint)
    logger.info(f"✅ Webhook set: {webhook_endpoint}")


def main():
    global ptb_app
    ptb_app = create_bot_app()

    # Set webhook if WEBHOOK_URL is configured
    if WEBHOOK_URL:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ptb_app.initialize())
        loop.run_until_complete(setup_webhook(ptb_app))

        # Run Flask (Gunicorn will call this via wsgi)
        flask_app.run(host="0.0.0.0", port=PORT)
    else:
        # Fallback: polling mode (local testing)
        logger.warning("WEBHOOK_URL not set — running in polling mode")
        ptb_app.add_handler(CommandHandler("start", start))
        ptb_app.run_polling(drop_pending_updates=True)


# Gunicorn entry point
def create_app():
    global ptb_app
    ptb_app = create_bot_app()
    if WEBHOOK_URL:
        import threading
        def set_wh():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(ptb_app.initialize())
            loop.run_until_complete(setup_webhook(ptb_app))
        t = threading.Thread(target=set_wh, daemon=True)
        t.start()
        t.join(timeout=10)
    return flask_app


if __name__ == "__main__":
    main()
