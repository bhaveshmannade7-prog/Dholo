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

# Env se cookie file banana (Render ka Newline Issue Fix kiya gaya hai)
if COOKIE_DATA:
    # Render string me '\n' ko literal text bana deta hai, isse fix karna zaroori hai
    cookie_text = COOKIE_DATA.replace('\\n', '\n').strip()
    
    if not cookie_text.startswith("# Netscape HTTP Cookie File"):
        cookie_text = "# Netscape HTTP Cookie File\n" + cookie_text
        
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        f.write(cookie_text)
    logger.info("Cookie file successfully create ho gayi hai.")

# Download folder pehle se bana kar rakhein
os.makedirs('downloads', exist_ok=True)

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **THE GREAT MOVIES Downloader**\n\nYouTube link bhejein aur download shuru karein!", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best)", callback_data=f"vid_best|{url}")],
            [InlineKeyboardButton("🎞️ 720p (Agar available ho)", callback_data=f"vid_720|{url}"),
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
        'quiet': False, # Logs dekhne ke liye True hata diya
        'no_warnings': True,
    }

    # Sabse Powerful Fallback Format (Shorts + Normal videos sabke liye)
    if "vid_720" in data:
        # 720p video+audio, nahi mila toh 720p merged, nahi mila toh simple best
        ydl_opts['format'] = 'bv*[height<=720]+ba/b[height<=720]/b'
    elif "vid_best" in data:
        ydl_opts['format'] = 'bv*+ba/b'
    else:
        ydl_opts.update({
            'format': 'ba/b',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
        })

    try:
        await status_msg.edit_text("📥 **Downloading start ho gayi hai... (Thoda wait karein)**", parse_mode='Markdown')
        
        def run_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        
        info = await asyncio.to_thread(run_dl)
        
        # File path properly nikalna
        if 'requested_downloads' in info:
            file_path = info['requested_downloads'][0]['filepath']
        else:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                file_path = ydl.prepare_filename(info)
        
        if "aud_mp3" in data and not file_path.endswith('.mp3'):
            file_path = os.path.splitext(file_path)[0] + ".mp3"

        # Telegram size limit check (50MB)
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
        error_msg = str(e)
        if "Sign in" in error_msg:
            await status_msg.edit_text("❌ **Error:** YouTube Cookie kaam nahi kar raha ya IP Block hai. Nayi Cookie try karein.", parse_mode='Markdown')
        else:
            await status_msg.edit_text(f"❌ **Error:** `{error_msg}`", parse_mode='Markdown')

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
