import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
# Render par ham cookie file ka content text format me dalenge
COOKIE_DATA = os.getenv('COOKIE_CONTENT') 

# Cookie file create karna agar content available ho
if COOKIE_DATA:
    with open('cookies.txt', 'w') as f:
        f.write(COOKIE_DATA)

# Download directory
if not os.path.exists('downloads'):
    os.makedirs('downloads')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! YouTube link bhejo, main cookies ka use karke download kar dunga.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [
                InlineKeyboardButton("🎬 Video (1080p/Best)", callback_data=f"vid_best|{url}"),
                InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"aud_mp3|{url}")
            ],
            [InlineKeyboardButton("🎞️ 720p Quality", callback_data=f"vid_720|{url}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Select Quality:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Bhai, valid YouTube link bhejo!")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data, url = query.data.split('|')
    status_msg = await query.edit_message_text("⏳ Processing... Downloading file.")

    ydl_opts = {
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
    }

    if data == "vid_best":
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    elif data == "vid_720":
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best'
    elif data == "aud_mp3":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if data == "aud_mp3":
                file_path = os.path.splitext(file_path)[0] + ".mp3"

        await status_msg.edit_text("📤 Uploading to Telegram...")
        with open(file_path, 'rb') as f:
            if data == "aud_mp3":
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, caption=info['title'])
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, supports_streaming=True, caption=info['title'])
        
        os.remove(file_path)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")

def main():
    if not TOKEN:
        print("Error: BOT_TOKEN nahi mila!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    print("Bot is alive...")
    app.run_polling()

if __name__ == '__main__':
    main()
