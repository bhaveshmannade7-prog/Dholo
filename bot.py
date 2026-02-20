import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL') # https://dholo.onrender.com
COOKIE_DATA = os.getenv('COOKIE_DATA')
COOKIE_FILE = 'cookies.txt'

if COOKIE_DATA:
    with open(COOKIE_FILE, 'w') as f:
        f.write(COOKIE_DATA)

# Init Flask and Bot
app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Bot Active Hai! YouTube link bhejo.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [[InlineKeyboardButton("🎬 Best Video", callback_data=f"vid_best|{url}")]]
        await update.message.reply_text("Quality choose karein:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    msg = await query.message.reply_text("⏳ Processing...")
    
    ydl_opts = {'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None, 'outtmpl': 'downloads/%(title)s.%(ext)s'}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        
        await context.bot.send_video(chat_id=query.message.chat_id, video=open(file_path, 'rb'), supports_streaming=True)
        os.remove(file_path)
    except Exception as e:
        await query.message.reply_text(f"Error: {e}")

# Registration
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
ptb_app.add_handler(CallbackQueryHandler(button_click))

# Webhook Route
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), ptb_app.bot)
        # We need to run this in the event loop
        asyncio.run(ptb_app.process_update(update))
        return 'ok', 200

@app.route('/')
def index():
    return "Bot is running!", 200

# Function for Gunicorn to set webhook at start
def set_webhook_sync():
    import requests
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/{TOKEN}"
    requests.get(url)

set_webhook_sync()

if __name__ == '__main__':
    # Local testing ke liye
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
