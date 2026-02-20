import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8080))
COOKIE_DATA = os.getenv('COOKIE_DATA') # Env se cookie text lega
COOKIE_FILE = 'cookies.txt'

# Create cookie file from Env if it doesn't exist
if COOKIE_DATA:
    with open(COOKIE_FILE, 'w') as f:
        f.write(COOKIE_DATA)

app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **THE GREAT MOVIES - Video Downloader**\n\n"
        "Bas YouTube link bhejo aur quality select karo!",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("🎬 Best Video", callback_data=f"vid_best|{url}")],
            [InlineKeyboardButton("🎞️ 720p Video", callback_data=f"vid_720|{url}"),
             InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"aud_mp3|{url}")]
        ]
        await update.message.reply_text("📥 **Quality select karein:**", 
                                       reply_markup=InlineKeyboardMarkup(keyboard), 
                                       parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Bhai, ye YouTube link nahi lag raha.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, url = query.data.split('|')
    
    status_msg = await query.message.reply_text("⏳ **Processing...** Please wait.", parse_mode='Markdown')

    # yt-dlp Options
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if "aud_mp3" in data:
                file_path = os.path.splitext(file_path)[0] + ".mp3"

        await status_msg.edit_text("📤 **Uploading to Telegram...**", parse_mode='Markdown')
        
        with open(file_path, 'rb') as f:
            if "aud_mp3" in data:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, caption=info.get('title'))
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=info.get('title'), supports_streaming=True)
        
        os.remove(file_path) # Delete after upload
        await status_msg.delete()

    except Exception as e:
        await query.message.reply_text(f"❌ **Error:** `{str(e)}`", parse_mode='Markdown')

# Webhook Routes
@app.route(f'/{TOKEN}', methods=['POST'])
async def respond():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    await ptb_app.process_update(update)
    return 'ok', 200

@app.route('/')
def index():
    return 'Bot is Alive!', 200

async def main():
    # Set Webhook
    await ptb_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    # Run Bot via Flask
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    # Initialize PTB app and handlers
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    ptb_app.add_handler(CallbackQueryHandler(button_click))
    
    import asyncio
    asyncio.run(main())
