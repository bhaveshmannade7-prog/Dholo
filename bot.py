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
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '').rstrip('/')
PORT = int(os.getenv('PORT', 10000))
COOKIE_DATA = os.getenv('COOKIE_DATA')
COOKIE_FILE = os.path.join(os.getcwd(), 'cookies.txt')

# Env se cookie file banana (Render newline fix ke sath)
if COOKIE_DATA:
    cookie_text = COOKIE_DATA.replace('\\n', '\n').strip()
    if not cookie_text.startswith("# Netscape HTTP Cookie File"):
        cookie_text = "# Netscape HTTP Cookie File\n" + cookie_text
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        f.write(cookie_text)

os.makedirs('downloads', exist_ok=True)

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **THE GREAT MOVIES Downloader**\n\nBhai link bhejo, is baar pakka download hoga!", parse_mode='Markdown')

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
    
    status_msg = await query.message.reply_text("⏳ **YouTube ki security bypass kar raha hu...**", parse_mode='Markdown')

    # ---> YAHAN HAI ASLI JADUI FIX <---
    ydl_opts = {
        'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': False, 
        'no_warnings': True,
        # 1. Force IPv4 (Cloud IPv6 Block ko todne ke liye)
        'source_address': '0.0.0.0',
        # 2. Smart TV & Mobile Bypass
        'extractor_args': {'youtube': {'player_client': ['tv', 'android', 'ios', 'web']}},
        # 3. Fake User-Agent taaki bot na lage
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
    }

    # Bulletproof Formats
    if "vid_720" in data:
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
    elif "vid_best" in data:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else:
        # Audio ke liye sabse best fallback
        ydl_opts.update({
            'format': 'm4a/bestaudio/best', 
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
        })

    try:
        await status_msg.edit_text("📥 **Downloading start ho gayi hai...**", parse_mode='Markdown')
        
        def run_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        
        info = await asyncio.to_thread(run_dl)
        
        if 'requested_downloads' in info:
            file_path = info['requested_downloads'][0]['filepath']
        else:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                file_path = ydl.prepare_filename(info)
        
        # Extension fix for audio
        if "aud_mp3" in data and not file_path.endswith('.mp3'):
            file_path = os.path.splitext(file_path)[0] + ".mp3"

        if os.path.exists(file_path):
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > 50:
                await status_msg.edit_text(f"❌ **Error:** File ka size **{file_size_mb:.1f} MB** hai. Telegram Bots 50MB se badi file nahi bhej sakte.", parse_mode='Markdown')
                os.remove(file_path)
                return

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

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))

    logger.info(f"Starting webhook on port {PORT}")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == '__main__':
    main()
