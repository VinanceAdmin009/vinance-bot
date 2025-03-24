from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import os
import logging

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("🚀 Vinance AI is working!")

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    
    # Use polling for simplicity (we'll fix conflicts later)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
