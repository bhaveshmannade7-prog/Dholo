import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL') # https://dholo.onrender.com
PORT = int(os.getenv('PORT', 10000))
COOKIE_DATA = os.getenv('COOKIE_DATA')
COOKIE_FILE = 'cookies.txt'

# Cookie setup
if COOKIE_DATA:
    with open(COOKIE_FILE, 'w') as f:
        f.write(COOKIE_DATA)

# Initialize Flask
app = Flask(__name__)

# Initialize Application
ptb_app = Application.builder().token(TOKEN).build()

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ **Bot Active Hai!**\nYouTube link bhejein download karne ke liye.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best)", callback_data=f"vid_best|{url}")],
            [InlineKeyboardButton("🎞️ 720p", callback_data=f"vid_720|{url}"),
             InlineKeyboardButton("🎵 MP3", callback_data=f"aud_mp3|{url}")]
        ]
        await update.message.reply_text("📥 Quality select karein:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    
    msg = await query.message.reply_text("⏳ Processing...")

    ydl_opts = {
        'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
    }

    if "vid_720" in data: ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best'
    elif "vid_best" in data: ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else: ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            if "aud_mp3" in data: path = os.path.splitext(path)[0] + ".mp3"

        await msg.edit_text("📤 Uploading...")
        with open(path, 'rb') as f:
            if "aud_mp3" in data:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, supports_streaming=True)
        os.remove(path)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")

# --- WEBHOOK LOGIC ---
@app.route(f'/{TOKEN}', methods=['POST'])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), ptb_app.bot)
        await ptb_app.update_queue.put(update) # Naye version ke liye zaroori
        return "OK", 200

@app.route('/')
def index():
    return "Bot is running", 200

async def setup():
    # Handlers add karein
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    ptb_app.add_handler(CallbackQueryHandler(button_click))
    
    # Bot start karein (lekin polling nahi)
    await ptb_app.initialize()
    await ptb_app.start()
    
    # Webhook set karein
    webhook_path = f"{WEBHOOK_URL}/{TOKEN}"
    await ptb_app.bot.set_webhook(url=webhook_path)
    logger.info(f"Webhook set to: {webhook_path}")

if __name__ == '__main__':
    # Background mein Telegram application setup karein
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup())
    
    # Flask ko run karein
    app.run(host='0.0.0.0', port=PORT)
