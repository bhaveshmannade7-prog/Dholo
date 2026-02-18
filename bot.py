import os
import re
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")
# ---------------------------
# Start Command
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a YouTube link.\nI will ask you to choose quality."
    )

# ---------------------------
# URL Validation
# ---------------------------
def is_youtube_url(url):
    pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/"
    return re.match(pattern, url)

# ---------------------------
# Receive Link
# ---------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text

    if not is_youtube_url(url):
        await update.message.reply_text("❌ Please send a valid YouTube link.")
        return

    context.user_data["url"] = url

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

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎥 Select video quality:",
        reply_markup=reply_markup,
    )

# ---------------------------
# Download Function
# ---------------------------
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality = query.data
    url = context.user_data.get("url")

    if not url:
        await query.message.reply_text("Session expired. Send link again.")
        return

    await query.message.reply_text("⬇ Downloading... Please wait.")

    ydl_opts = {
        "format": f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]",
        "merge_output_format": "mp4",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # Telegram limit safety (50MB normal bots)
        if os.path.getsize(filename) > 49 * 1024 * 1024:
            await query.message.reply_text(
                "⚠ File too large for Telegram (50MB limit). Try lower quality."
            )
            os.remove(filename)
            return

        await query.message.reply_video(video=open(filename, "rb"))

        os.remove(filename)

    except Exception as e:
        await query.message.reply_text("❌ Error occurred.")
        print(e)

# ---------------------------
# Main
# ---------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_video))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
