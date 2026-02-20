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
COOKIE_FILE = 'cookies.txt'

# Env se cookie file banana
if COOKIE_DATA:
    cookie_text = COOKIE_DATA.strip()
    if not cookie_text.startswith("# Netscape HTTP Cookie File"):
        cookie_text = "# Netscape HTTP Cookie File\n" + cookie_text
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        f.write(cookie_text)

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("THE GREAT MOVIES Downloader chalu hai!\nLink bhejo download start karte hai.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("Video (Best)", callback_data=f"vid_best|{url}")],
            [InlineKeyboardButton("720p Video", callback_data=f"vid_720|{url}"),
             InlineKeyboardButton("MP3 Audio", callback_data=f"aud_mp3|{url}")]
        ]
        await update.message.reply_text("Quality select karo bhai:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Bhai koi valid YouTube link bhejo.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    
    status_msg = await query.message.reply_text("Process kar raha hu, thoda ruko...")

    # YAHAN MAIN BYPASS ADD KIYA HAI
    ydl_opts = {
        'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': False,
        'no_warnings': True,
        # Ye YouTube ko lagega ki request Android phone se aa rahi hai
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
    }

    # Format me '/best' sabme daal diya taaki agar exact format na mile to video fail na ho
    if "vid_720" in data:
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
    elif "vid_best" in data:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
        })

    try:
        await status_msg.edit_text("Downloading chalu ho gayi hai...")
        
        def run_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        
        info = await asyncio.to_thread(run_dl)
        
        if 'requested_downloads' in info:
            file_path = info['requested_downloads'][0]['filepath']
        else:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                file_path = ydl.prepare_filename(info)
        
        if "aud_mp3" in data and not file_path.endswith('.mp3'):
            file_path = os.path.splitext(file_path)[0] + ".mp3"

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 50:
            await status_msg.edit_text(f"File ka size {file_size_mb:.1f} MB hai. Telegram bot 50MB se bada file nahi bhej sakta.")
            os.remove(file_path)
            return

        await status_msg.edit_text("Telegram par upload kar raha hu...")
        
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
        await status_msg.edit_text(f"Error aagya bhai: {str(e)}")

def main():
    if not TOKEN or not WEBHOOK_URL:
        logger.error("Token ya URL missing hai!")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == '__main__':
    main()
