# 🎬 DiskWala Bot — Render Deployment Guide

## 📁 Files
```
bot.py           ← main bot code
config.py        ← settings (env vars se)
requirements.txt ← dependencies
render.yaml      ← Render config
```

---

## 🚀 Render Par Deploy Karne Ke Steps

### Step 1 — GitHub par upload karo
1. [github.com](https://github.com) par naya **private repo** banao
2. In 4 files ko repo mein upload karo

### Step 2 — Render account banao
1. [render.com](https://render.com) par sign up karo (free)
2. **New +** → **Web Service**
3. Apna GitHub repo connect karo

### Step 3 — Settings fill karo
| Field | Value |
|-------|-------|
| **Name** | `diskwala-bot` (kuch bhi) |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --workers 1 --threads 4 --timeout 120 "bot:create_app()"` |
| **Instance Type** | `Free` |

### Step 4 — Environment Variables add karo
Render Dashboard → **Environment** tab → Add:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | `123456:ABCdef...` (BotFather se) |
| `WEBHOOK_URL` | Abhi blank chhodo |
| `COOKIE` | Optional (TeraBox cookie) |

### Step 5 — Pehli baar deploy karo
**Deploy** button dabao — 2-3 minute wait karo ✅

### Step 6 — WEBHOOK_URL set karo ⭐ (Important!)
1. Deploy hone ke baad Render aapko ek URL dega
   → Example: `https://diskwala-bot-xxxx.onrender.com`
2. Is URL ko copy karo
3. Environment Variables mein `WEBHOOK_URL` mein paste karo
4. **Save** → Bot automatically redeploy hoga

### Step 7 — Test karo 🎉
Apne bot ko Telegram mein dhundho → `/start` bhejo!

---

## 🍪 Cookie Kaise Milega

1. Chrome mein **diskwala.com** kholo → Login karo
2. `F12` press karo → **Network** tab
3. Page refresh karo → koi bhi request click karo
4. **Request Headers** section mein `Cookie:` dhundho
5. Pura cookie value copy karo
6. Render → Environment → `COOKIE` mein paste karo

---

## ❓ FAQ

**Bot respond nahi kar raha?**
→ WEBHOOK_URL sahi set hai? Render URL copy karke WEBHOOK_URL mein daalo

**"Free" plan ka bot slow hai?**
→ Render free plan 15 min inactivity ke baad sleep karta hai
→ Pehli message pe 30 sec lag sakti hai — normal hai

**Errors logs kahan dekhein?**
→ Render Dashboard → **Logs** tab

---

## ⚠️ Important Notes
- Telegram Bot API: **50MB** file limit
- Sirf **public** DiskWala links kaam karte hain
- Personal use ke liye hai
