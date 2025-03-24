from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler
import os

TOKEN = os.getenv("BOT_TOKEN")  # We'll set this later
ADMIN_ID = "5295843924"   # Get from @userinfobot

def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("✨ Activate AI Trading", callback_data="activate")],
        [InlineKeyboardButton("📊 View Example Trades", callback_data="examples")]
    ]
    update.message.reply_text(
        "🤖 *Welcome to Vinance AI*\n\n"
        "Our AI trading system delivers:\n"
        "• 87-92% win rate\n• 1-3% daily returns\n\n"
        "Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if query.data == "activate":
        query.edit_message_text(
            "📝 *Activation Steps*\n\n"
            "1. Send your Vinance username\n"
            "2. We'll manually approve within 24h\n\n"
            "Need help? Contact @YourSupportBot",
            parse_mode="Markdown"
        )

def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button_click))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()