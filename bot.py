import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SMART CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '').rstrip('/')
PORT = int(os.getenv('PORT', 10000))
PROXY_URL = os.getenv('PROXY_URL') # Agar proxy ho toh env me daalein
COOKIE_DATA = os.getenv('COOKIE_DATA')
COOKIE_FILE = 'cookies.txt'

# Smart Cookie Fixer
if COOKIE_DATA:
    cookie_text = COOKIE_DATA.replace('\\n', '\n').strip()
    if not cookie_text.startswith("# Netscape HTTP Cookie File"):
        cookie_text = "# Netscape HTTP Cookie File\n" + cookie_text
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        f.write(cookie_text)

os.makedirs('downloads', exist_ok=True)

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 **Welcome to THE GREAT MOVIES Bot!**\n\nNaye Smart Engine ke sath. Kripya apna YouTube link bhejein.", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("🎬 Download Best Video", callback_data=f"vid_best|{url}")],
            [InlineKeyboardButton("🎵 Download MP3 Audio", callback_data=f"aud_mp3|{url}")]
        ]
        await update.message.reply_text("📥 **Aapko kya download karna hai?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Kripya valid YouTube link bhejein.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    
    status_msg = await query.message.reply_text("⏳ **Link ko analyze kiya ja raha hai...**", parse_mode='Markdown')

    ydl_opts = {
        'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': False,
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}},
    }

    # Agar Render ka IP block bypass karna ho (via Proxy)
    if PROXY_URL:
        ydl_opts['proxy'] = PROXY_URL
        logger.info("Using Proxy to bypass IP block!")

    # Format strict but safe
    if "vid_best" in data:
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
        })

    try:
        await status_msg.edit_text("📥 **Downloading start ho chuki hai (Badi files me time lag sakta hai)...**", parse_mode='Markdown')
        
        def run_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        
        info = await asyncio.to_thread(run_dl)
        
        # Filepath properly resolve karna
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            actual_file_path = ydl.prepare_filename(info)
            if "aud_mp3" in data:
                actual_file_path = os.path.splitext(actual_file_path)[0] + ".mp3"

        if os.path.exists(actual_file_path):
            file_size_mb = os.path.getsize(actual_file_path) / (1024 * 1024)
            if file_size_mb > 50:
                await status_msg.edit_text(f"❌ **Error:** File ka size **{file_size_mb:.1f} MB** hai. Telegram ki limit 50MB hai.", parse_mode='Markdown')
                os.remove(actual_file_path)
                return

        await status_msg.edit_text("📤 **Telegram par upload ho raha hai...**", parse_mode='Markdown')
        
        with open(actual_file_path, 'rb') as f:
            if "aud_mp3" in data:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, caption=info.get('title'))
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=info.get('title'), supports_streaming=True)
        
        os.remove(actual_file_path)
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Download Error: {e}")
        error_str = str(e)
        if "Requested format is not available" in error_str:
            await status_msg.edit_text("❌ **YouTube IP Blocked!**\n\nRender ka IP block ho chuka hai. Kripya is bot ko apne phone (Termux) me run karein ya Env me `PROXY_URL` daalein.", parse_mode='Markdown')
        else:
            await status_msg.edit_text(f"❌ **Error:** `{error_str}`", parse_mode='Markdown')

# --- SMART ENVIRONMENT DETECTOR ---
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN is missing!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))

    # Yahan magic hota hai: Render vs Termux Detection
    if WEBHOOK_URL:
        logger.info(f"Running in WEBHOOK mode on port {PORT} (Render/Cloud)")
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        logger.info("Running in POLLING mode (Termux/Local)")
        app.run_polling()

if __name__ == '__main__':
    main()
