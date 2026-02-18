import os
import re
import asyncio
import shutil
import yt_dlp
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise ValueError("Missing BOT_TOKEN or WEBHOOK_URL")

app = FastAPI()
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ---------------- URL CHECK ----------------
def is_youtube_url(url):
    return re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", url)

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send YouTube link.\nYou can download Video or Audio."
    )

# ---------------- HANDLE LINK ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text

    if not is_youtube_url(url):
        await update.message.reply_text("❌ Invalid YouTube link.")
        return

    context.user_data["url"] = url

    keyboard = [
        [InlineKeyboardButton("🎥 Video", callback_data="video")],
        [InlineKeyboardButton("🎵 Audio (MP3)", callback_data="audio")]
    ]

    await update.message.reply_text(
        "Choose download type:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ---------------- QUALITY MENU ----------------
async def choose_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["type"] = query.data

    if query.data == "video":
        keyboard = [
            [
                InlineKeyboardButton("360p", callback_data="360"),
                InlineKeyboardButton("480p", callback_data="480"),
            ],
            [
                InlineKeyboardButton("720p", callback_data="720"),
                InlineKeyboardButton("1080p", callback_data="1080"),
            ],
        ]
        await query.message.reply_text(
            "🎥 Select quality:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await download_audio(update, context)

# ---------------- VIDEO DOWNLOAD ----------------
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality = query.data
    url = context.user_data.get("url")

    await query.message.reply_text("⬇ Downloading video...")

    ydl_opts = {
        "format": f"best[height<={quality}]",
        "outtmpl": "video.%(ext)s",
        "quiet": False,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if os.path.getsize(filename) > 49 * 1024 * 1024:
            await query.message.reply_text("⚠ File too large (50MB limit).")
            os.remove(filename)
            return

        await query.message.reply_video(video=open(filename, "rb"))
        os.remove(filename)

    except Exception as e:
        await query.message.reply_text(f"❌ Video Error:\n{str(e)}")

# ---------------- AUDIO DOWNLOAD ----------------
async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        msg = query.message
    else:
        msg = update.message

    url = context.user_data.get("url")

    await msg.reply_text("⬇ Downloading audio...")

    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": "audio.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": False,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        if os.path.exists("audio.mp3"):
            await msg.reply_audio(audio=open("audio.mp3", "rb"))
            os.remove("audio.mp3")
        else:
            await msg.reply_text("❌ Audio conversion failed.")

    except Exception as e:
        await msg.reply_text(f"❌ Audio Error:\n{str(e)}")

# ---------------- ROUTE ----------------
@app.post("/")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# ---------------- STARTUP ----------------
@app.on_event("startup")
async def on_startup():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    print("Webhook set.")

# ---------------- HANDLERS ----------------
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(CallbackQueryHandler(choose_quality, pattern="^(video|audio)$"))
telegram_app.add_handler(CallbackQueryHandler(download_video, pattern="^(360|480|720|1080)$"))

# ---------------- RUN ----------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
