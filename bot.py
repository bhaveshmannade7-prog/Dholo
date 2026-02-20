import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN')
# rstrip('/') isliye lagaya taaki agar aapne galti se last me '/' laga diya ho to double slash na bane
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '').rstrip('/')
PORT = int(os.getenv('PORT', 10000))
COOKIE_DATA = os.getenv('COOKIE_DATA')
COOKIE_FILE = 'cookies.txt'

# Env se cookie file banana
if COOKIE_DATA:
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        f.write(COOKIE_DATA)

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **THE GREAT MOVIES Downloader**\n\nYouTube link bhejein aur download shuru karein!", parse_mode='Markdown')

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
    else:
        await update.message.reply_text("❌ Kripya valid YouTube link bhejein.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    
    status_msg = await query.message.reply_text("⏳ **Link process ho raha hai...**", parse_mode='Markdown')

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
        await status_msg.edit_text("📥 **Downloading start ho gayi hai...**", parse_mode='Markdown')
        
        # Download task ko alag thread me bhejna zaroori hai warna bot response dena band kar dega
        def run_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        
        info = await asyncio.to_thread(run_dl)
        file_path = info['requested_downloads'][0]['filepath']
        
        if "aud_mp3" in data and not file_path.endswith('.mp3'):
            file_path = os.path.splitext(file_path)[0] + ".mp3"

        await status_msg.edit_text("📤 **Telegram par upload ho raha hai...**", parse_mode='Markdown')
        
        with open(file_path, 'rb') as f:
            if "aud_mp3" in data:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, caption=info.get('title'))
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=info.get('title'), supports_streaming=True)
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Download Error: {e}")
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`", parse_mode='Markdown')

# --- MAIN RUNNER ---
def main():
    if not TOKEN or not WEBHOOK_URL:
        logger.error("BOT_TOKEN ya WEBHOOK_URL environment variable missing hai!")
        return

    # Application Build
    app = Application.builder().token(TOKEN).build()

    # Handlers Add Karna
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))

    # PTB ka Inbuilt Webhook Server chalana (Flask ki zaroorat nahi)
    logger.info(f"Starting webhook on port {PORT}")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == '__main__':
    main()
