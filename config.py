import os

# ─── DiskWala Bot Configuration ───────────────────────────────────────────────
# Render par Environment Variables se values aati hain
# Khud kuch change karne ki zaroorat NAHI — sirf Render dashboard mein set karo

# Telegram Bot Token (Render > Environment > BOT_TOKEN)
BOT_TOKEN = os.environ.get("8970476953:AAE82b_R4vrmRxV2WL5HeTOFTxW9UgrzWeI")

# TeraBox/DiskWala Cookie (optional, Render > Environment > COOKIE)
COOKIE = os.environ.get("COOKIE", "")

# Render apna PORT khud set karta hai — mat badlo
PORT = int(os.environ.get("PORT", 8080))

# Render deploy hone ke baad aapka URL (Render > Settings > URL)
# Example: "https://diskwala-bot.onrender.com"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
