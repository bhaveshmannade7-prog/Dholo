import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# --- CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL') # Example: https://your-app.onrender.com
PORT = int(os.getenv('PORT', 8080))
COOKIE_FILE = 'cookies.txt'

# Flask App for Webhook
app = Flask(__name__)

# Build Bot Application
ptb_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ **YouTube Downloader Bot**\n\nBas link bhejo aur quality select karo!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best)", callback_data=f"vid_best|{url}")],
            [InlineKeyboardButton("🎞️ 720p", callback_data=f"vid_720|{url}"),
             InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"aud_mp3|{url}")]
        ]
        await update.message.reply_text("Quality select karein:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    
    status_msg = await query.message.reply_text("⏳ Download shuru ho raha hai...")

    ydl_opts = {
        'cookiefile': COOKIE_FILE,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
    }

    if "vid_720" in data: ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best'
    elif "vid_best" in data: ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else: 
        ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if "aud_mp3" in data: file_path = os.path.splitext(file_path)[0] + ".mp3"

        await status_msg.edit_text("📤 Telegram par upload ho raha hai...")
        with open(file_path, 'rb') as f:
            if "aud_mp3" in data:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, supports_streaming=True)
        
        os.remove(file_path)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")

# Webhook Route
@app.route(f'/{TOKEN}', methods=['POST'])
async def webhook(request):
    update = Update.de_json(await request.get_json(), ptb_app.bot)
    await ptb_app.process_update(update)
    return 'OK', 200

@app.route('/')
def index(): return "Bot is Alive!", 200

# Main logic to run Webhook
if __name__ == '__main__':
    # Webhook setup
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ptb_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}"))
    
    # Run Flask with Gunicorn or direct (for Termux)
    app.run(host='0.0.0.0', port=PORT)
