import os
import logging
import atexit
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommandScopeChat
from telegram.ext import (
    Application, CommandHandler, CallbackContext,
    MessageHandler, ConversationHandler,
    CallbackQueryHandler,
    filters
)
from config import *
from tendo.singleton import SingleInstance

# ===== INITIALIZATION =====
try:
    me = SingleInstance(flavor_id="vinance-bot-prod")
except:
    logging.critical("🚨 Another bot instance is already running! Exiting...")
    exit(1)

def cleanup():
    lock_file = f'/tmp/vinance-bot-prod.lock'
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass
atexit.register(cleanup)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ===== ENHANCED DATABASE =====
class UserDB:
    def __init__(self):
        self.active = []
        self.pending = []
        self.user_portfolios = {}  # Track user trading portfolios
    
    def add_user(self, user_data: dict):
        if not any(u['id'] == user_data['id'] for u in self.pending + self.active):
            self.pending.append(user_data)
            self.user_portfolios[user_data['id']] = {
                'balance': 0.0,
                'positions': {},
                'trading_enabled': False
            }
            return True
        return False
    
    def approve_user(self, user_id: int):
        try:
            user = next(u for u in self.pending if u['id'] == user_id)
            self.active.append(user)
            self.pending.remove(user)
            self.user_portfolios[user_id]['trading_enabled'] = True
            return user
        except StopIteration:
            raise ValueError(f"User {user_id} not found in pending list")

db = UserDB()

# ===== CONVERSATION STATES =====
(
    GET_USERNAME, GET_EMAIL, 
    SELECT_USER_TO_MESSAGE, COMPOSE_USER_MESSAGE,
    SELECT_BROADCAST_RECIPIENTS, COMPOSE_BROADCAST,
    MANUAL_TRADE_SYMBOL, MANUAL_TRADE_AMOUNT
) = range(8)

# ===== UI COMPONENTS =====
def build_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 Broadcast", callback_data="broadcast_menu")],
        [InlineKeyboardButton("📩 Message User", callback_data="message_user_menu")],
        [InlineKeyboardButton("✅ Approve Users", callback_data="approve_users")],
        [InlineKeyboardButton("💱 Manual Trade", callback_data="manual_trade")],
        [InlineKeyboardButton("📊 User Stats", callback_data="user_stats")]
    ])

def build_user_list(action_prefix):
    keyboard = []
    for user in db.active:
        keyboard.append([
            InlineKeyboardButton(
                f"{user['name']} (@{user['username']})",
                callback_data=f"{action_prefix}_{user['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(keyboard)

def build_pending_users_menu():
    keyboard = []
    for user in db.pending:
        keyboard.append([
            InlineKeyboardButton(
                f"{user['name']} (@{user['username']})",
                callback_data=f"approve_{user['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(keyboard)

# ===== ADMIN FUNCTIONS =====
async def start_admin_panel(update: Update, context: CallbackContext):
    stats = {
        "active_users": len(db.active),
        "pending_users": len(db.pending),
        "total_balance": sum(u['balance'] for u in db.user_portfolios.values())
    }
    await update.message.reply_text(
        text=ADMIN_DASHBOARD.format(**stats),
        reply_markup=build_admin_menu(),
        parse_mode="Markdown"
    )

async def message_user_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Select user to message:",
        reply_markup=build_user_list("message")
    )
    return SELECT_USER_TO_MESSAGE

async def select_user_to_message(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_admin":
        await show_admin_panel(update, context)
        return ConversationHandler.END
    
    user_id = int(query.data.split('_')[1])
    context.user_data['message_target'] = user_id
    await query.edit_message_text("✍️ Enter your message for this user:")
    return COMPOSE_USER_MESSAGE

async def compose_user_message(update: Update, context: CallbackContext):
    user_id = context.user_data['message_target']
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=update.message.text
        )
        await update.message.reply_text("✅ Message sent successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message: {str(e)}")
    
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def broadcast_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Select recipients for broadcast:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("All Active Users", callback_data="broadcast_all")],
            [InlineKeyboardButton("Select Specific Users", callback_data="broadcast_select")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
        ])
    )
    return SELECT_BROADCAST_RECIPIENTS

async def manual_trade_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Enter trading pair (e.g. BTC/USDT):"
    )
    return MANUAL_TRADE_SYMBOL

# ===== USER FUNCTIONS =====
async def start_user_panel(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    portfolio = db.user_portfolios.get(user_id, {})
    
    await update.message.reply_text(
        text=f"💰 Your Portfolio\n\n"
             f"Balance: ${portfolio.get('balance', 0):.2f}\n"
             f"Trading Status: {'✅ Active' if portfolio.get('trading_enabled', False) else '❌ Pending Approval'}\n\n"
             f"Available Commands:\n"
             f"/balance - Check your balance\n"
             f"/trade - Start a new trade\n"
             f"/positions - View your open positions",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 Activate AI", callback_data="activate")]
        ])
    )

# ===== MAIN HANDLERS =====
async def start(update: Update, context: CallbackContext):
    if update.message.chat.id in ADMIN_CHAT_IDS:
        await start_admin_panel(update, context)
    else:
        await start_user_panel(update, context)

async def show_admin_panel(update: Update, context: CallbackContext):
    if hasattr(update, 'callback_query'):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text="👑 Admin Panel",
            reply_markup=build_admin_menu()
        )
    else:
        await update.message.reply_text(
            text="👑 Admin Panel",
            reply_markup=build_admin_menu()
        )

# [Previous conversation handlers for registration remain the same...]

async def error_handler(update: Update, context: CallbackContext):
    error = str(context.error)
    logging.error(f"🚨 Error: {error}")
    if update:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_IDS[0],
            text=f"⚠️ Error occurred:\n{error}"
        )

async def post_init(application: Application):
    # Set commands for all users
    await application.bot.set_my_commands([
        ("start", "Start the bot"),
        ("balance", "Check your balance"),
        ("trade", "Start a new trade"),
        ("positions", "View your positions")
    ])
    
    # Set admin commands
    if ADMIN_CHAT_IDS:
        await application.bot.set_my_commands(
            commands=[
                ("start", "Start the bot"),
                ("admin", "Admin panel"),
                ("broadcast", "Send broadcast"),
                ("approve", "Approve users"),
                ("manualtrade", "Execute manual trade")
            ],
            scope=BotCommandScopeChat(ADMIN_CHAT_IDS[0])
        )

def main():
    if not BOT_TOKEN:
        logging.error("❌ Missing BOT_TOKEN in config.py!")
        return

    try:
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
        
        application.add_error_handler(error_handler)
        
        # Registration conversation handler (same as before)
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_registration, pattern='^activate$')],
            states={
                GET_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
                GET_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)]
            },
            fallbacks=[],
            per_message=False,
            per_user=True,
            per_chat=True
        )
        
        # Admin message conversation handler
        msg_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(message_user_menu, pattern='^message_user_menu$')],
            states={
                SELECT_USER_TO_MESSAGE: [CallbackQueryHandler(select_user_to_message)],
                COMPOSE_USER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, compose_user_message)]
            },
            fallbacks=[]
        )
        
        # Broadcast conversation handler
        broadcast_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(broadcast_menu, pattern='^broadcast_menu$')],
            states={
                SELECT_BROADCAST_RECIPIENTS: [CallbackQueryHandler(select_broadcast_recipients)],
                COMPOSE_BROADCAST: [MessageHandler(filters.TEXT | filters.PHOTO, send_broadcast)]
            },
            fallbacks=[]
        )
        
        # Manual trade conversation handler
        trade_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(manual_trade_menu, pattern='^manual_trade$')],
            states={
                MANUAL_TRADE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_trade_symbol)],
                MANUAL_TRADE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, execute_trade)]
            },
            fallbacks=[]
        )
        
        # Add all handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("admin", start_admin_panel))
        application.add_handler(conv_handler)
        application.add_handler(msg_handler)
        application.add_handler(broadcast_handler)
        application.add_handler(trade_handler)
        
        # Add other callback handlers
        application.add_handler(CallbackQueryHandler(approve_user_callback, pattern='^approve_'))
        application.add_handler(CallbackQueryHandler(show_pending_users, pattern='^approve_users$'))
        application.add_handler(CallbackQueryHandler(show_admin_panel, pattern='^back_to_admin$'))
        
        application.run_polling(
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=30,
            allowed_updates=[
                'message',
                'callback_query',
                'chat_member',
                'my_chat_member'
            ]
        )
        
    except Exception as e:
        logging.critical(f"💥 FATAL STARTUP ERROR: {str(e)}")
        exit(1)

if __name__ == '__main__':
    print("""
    ██╗   ██╗██╗███╗   ██╗ █████╗ ███╗   ██╗ ██████╗███████╗
    ██║   ██║██║████╗  ██║██╔══██╗████╗  ██║██╔════╝██╔════╝
    ██║   ██║██║██╔██╗ ██║███████║██╔██╗ ██║██║     █████╗  
    ╚██╗ ██╔╝██║██║╚██╗██║██╔══██║██║╚██╗██║██║     ██╔══╝  
     ╚████╔╝ ██║██║ ╚████║██║  ██║██║ ╚████║╚██████╗███████╗
      ╚═══╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝
    """)
    main()
