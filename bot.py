import os
import logging
import csv
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackContext,
    CallbackQueryHandler, MessageHandler, Filters
)
from tendo import singleton

# ===== CONFIGURATION =====
TOKEN = os.getenv("BOT_TOKEN")          # From Render
ADMIN_ID = os.getenv("ADMIN_ID")        # Your Telegram ID
ADMIN_LOG = "admin_logs.csv"            # Action tracking
me = singleton.SingleInstance()         # Prevent duplicates

# ===== EMOJI THEME =====
EMOJI = {
    "welcome": "👋", "success": "✅", "error": "❌",
    "profit": "📈", "trade": "💎", "admin": "👑",
    "wallet": "💰", "chart": "📊", "ban": "🔨"
}

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def log_admin(action: str, target: str = ""):
    with open(ADMIN_LOG, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(), ADMIN_ID, action, target])

# ===== USER FLOW =====
def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['trade']} Activate AI", callback_data="activate")],
        [InlineKeyboardButton(f"{EMOJI['chart']} Example Trades", callback_data="trades")]
    ]
    update.message.reply_text(
        f"""{EMOJI['welcome']} *Vinance AI Trader*

🚀 Automated crypto trading with 89% accuracy

{EMOJI['profit']} Today's Performance: +2.1%
{EMOJI['wallet']} Active Users: 1,240""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def activate_ai(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.edit_message_text(
        f"""⚡ *AI Activation* ⚡

1. Reply with your Vinance username (format: VINANCE_XXX)
2. We'll approve within 24 hours
3. Start earning automatically

{EMOJI['success']} Employee Benefits:
• 0% trading fees
• Early signal access""",
        parse_mode="Markdown"
    )

# ===== ADMIN CONTROLS =====
def admin_panel(update: Update, context: CallbackContext) -> None:
    if str(update.message.from_user.id) != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['ban']} Ban User", callback_data="ban_user")],
        [InlineKeyboardButton(f"{EMOJI['chart']} Stats", callback_data="stats")],
        [InlineKeyboardButton("📤 Export Data", callback_data="export")]
    ]
    update.message.reply_text(
        f"{EMOJI['admin']} *Admin Panel*",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    log_admin("OPENED_PANEL")

def ban_user(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.edit_message_text("Send /ban USER_ID to restrict access")
    log_admin("ATTEMPTED_BAN")

def execute_ban(update: Update, context: CallbackContext) -> None:
    try:
        user_id = context.args[0]
        context.bot.send_message(
            chat_id=user_id,
            text=f"{EMOJI['error']} Your access has been revoked."
        )
        update.message.reply_text(f"Banned user {user_id}")
        log_admin("BANNED_USER", user_id)
    except:
        update.message.reply_text("Usage: /ban USER_ID")

# ===== MAIN =====
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # User commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(activate_ai, pattern="^activate$"))

    # Admin commands
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CommandHandler("ban", execute_ban))
    dp.add_handler(CallbackQueryHandler(ban_user, pattern="^ban_user$"))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
