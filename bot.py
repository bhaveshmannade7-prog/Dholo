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
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 10000))
COOKIE_DATA = os.getenv('COOKIE_DATA')
COOKIE_FILE = 'cookies.txt'

# Cookie setup from Env
if COOKIE_DATA:
    with open(COOKIE_FILE, 'w') as f:
        f.write(COOKIE_DATA)

# Initialize Application
ptb_app = Application.builder().token(TOKEN).build()
app = Flask(__name__)

# --- DOWNLOAD PROGRESS HANDLER ---
def progress_hook(d, status_msg, loop, context, chat_id):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%')
        # Har 2 second me update karne ki koshish (Rate limit se bachne ke liye)
        logger.info(f"Downloading: {p}")

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **THE GREAT MOVIES Downloader**\n\nLink bhejein aur quality chunien!", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best)", callback_data=f"vid_best|{url}")],
            [InlineKeyboardButton("🎞️ 720p", callback_data=f"vid_720|{url}"),
             InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"aud_mp3|{url}")]
        ]
        await update.message.reply_text("📥 **Quality Select Karein:**", 
                                       reply_markup=InlineKeyboardMarkup(keyboard), 
                                       parse_mode='Markdown')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    
    status_msg = await query.message.reply_text("⏳ **Processing link...**", parse_mode='Markdown')

    ydl_opts = {
        'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    if "vid_720" in data:
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best'
    elif "vid_best" in data:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
        })

    try:
        await status_msg.edit_text("📥 **Downloading started...**", parse_mode='Markdown')
        
        # Run yt-dlp in a thread to keep bot responsive
        loop = asyncio.get_running_loop()
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        
        info = await loop.run_in_executor(None, download)
        file_path = info['requested_downloads'][0]['filepath']
        
        # Audio fix
        if "aud_mp3" in data and not file_path.endswith('.mp3'):
            file_path = os.path.splitext(file_path)[0] + ".mp3"

        await status_msg.edit_text("📤 **Uploading to Telegram...**", parse_mode='Markdown')
        
        with open(file_path, 'rb') as f:
            if "aud_mp3" in data:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, caption=info.get('title'))
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=info.get('title'), supports_streaming=True)
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`", parse_mode='Markdown')

# --- WEBHOOK ROUTES ---
@app.route(f'/{TOKEN}', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    await ptb_app.process_update(update)
    return 'ok', 200

@app.route('/')
def index():
    return 'Bot is Alive!', 200

# --- MAIN RUNNER ---
async def main():
    # Setup Handlers
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    ptb_app.add_handler(CallbackQueryHandler(button_click))

    # Initialize and Start
    await ptb_app.initialize()
    await ptb_app.start()
    
    # Set Webhook
    await ptb_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    
    # Run Flask in the same loop
    from werkzeug.serving import make_server
    server = make_server('0.0.0.0', PORT, app)
    logger.info(f"Server starting on port {PORT}")
    
    # This keeps the server running until the loop is closed
    await loop.run_in_executor(None, server.serve_forever)

if __name__ == '__main__':
    try:
        # Python 3.7+ approach
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
