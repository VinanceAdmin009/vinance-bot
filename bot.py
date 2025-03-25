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

# ===== DATABASE =====
class UserDB:
    def __init__(self):
        self.active = []
        self.pending = []
    
    def add_user(self, user_data: dict):
        if not any(u['id'] == user_data['id'] for u in self.pending + self.active):
            self.pending.append(user_data)
            return True
        return False
    
    def approve_user(self, user_id: int):
        try:
            user = next(u for u in self.pending if u['id'] == user_id)
            self.active.append(user)
            self.pending.remove(user)
            return user
        except StopIteration:
            raise ValueError(f"User {user_id} not found in pending list")

db = UserDB()

# ===== CONVERSATION STATES =====
GET_USERNAME, GET_EMAIL = range(2)

# ===== UI COMPONENTS =====
def build_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("📩 Message User", callback_data="message_user")],
        [InlineKeyboardButton("✅ Approve Users", callback_data="approve_users")]
    ])

def build_approve_menu():
    keyboard = []
    for user in db.pending:
        keyboard.append([
            InlineKeyboardButton(
                f"Approve {user['name']} ({user['id']})",
                callback_data=f"approve_{user['id']}"
            )
        ])
    return InlineKeyboardMarkup(keyboard)

# ===== ADMIN CHECK DECORATOR =====
def admin_only(func):
    async def wrapper(update: Update, context: CallbackContext):
        if update.effective_chat.id not in ADMIN_CHAT_IDS:
            if hasattr(update, 'callback_query'):
                await update.callback_query.answer("❌ Admin access required!")
            else:
                await update.message.reply_text("❌ Admin access required!")
            return
        return await func(update, context)
    return wrapper

# ===== CORE FUNCTIONS =====
async def start(update: Update, context: CallbackContext):
    if update.effective_chat.id in ADMIN_CHAT_IDS:
        await show_admin_panel(update, context)
    else:
        await update.message.reply_photo(
            photo=LOGO_URL,
            caption=WELCOME_MSG,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔓 Activate AI", callback_data="activate")]
            ]),
            parse_mode="Markdown"
        )

@admin_only
async def admin_command(update: Update, context: CallbackContext):
    await show_admin_panel(update, context)

async def show_admin_panel(update: Update, context: CallbackContext):
    stats = {
        "active_users": len(db.active),
        "pending_users": len(db.pending),
        "banned_users": 0
    }
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=LOGO_URL,
        caption=ADMIN_DASHBOARD.format(**stats),
        reply_markup=build_admin_menu(),
        parse_mode="Markdown"
    )

async def start_registration(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    # Store the message info in context
    context.user_data['original_message'] = {
        'chat_id': query.message.chat_id,
        'message_id': query.message.message_id
    }
    
    # Send a new message instead of editing to avoid issues
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="📝 Please enter your Vinance username:"
    )
    return GET_USERNAME

async def get_username(update: Update, context: CallbackContext):
    context.user_data['username'] = update.message.text
    await update.message.reply_text("📧 Now enter your email address:")
    return GET_EMAIL

async def get_email(update: Update, context: CallbackContext):
    email = update.message.text
    if not any(domain in email for domain in EMAIL_DOMAINS):
        await update.message.reply_text(f"❌ Invalid email domain. Allowed: {', '.join(EMAIL_DOMAINS)}")
        return GET_EMAIL
    
    user_data = {
        'id': update.message.from_user.id,
        'username': context.user_data['username'],
        'email': email,
        'name': update.message.from_user.full_name
    }
    
    if db.add_user(user_data):
        for admin_id in ADMIN_CHAT_IDS:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=LOGO_URL,
                caption=f"🆕 *New Registration*\n\n"
                     f"• Name: {user_data['name']}\n"
                     f"• Username: @{user_data['username']}\n"
                     f"• Email: {user_data['email']}\n"
                     f"• User ID: `{user_data['id']}`\n\n"
                     f"Approve with: /approve_{user_data['id']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_data['id']}")]
                ])
            )
        
        await update.message.reply_text("✅ Registration complete! Admin will contact you soon.")
    else:
        await update.message.reply_text("⚠️ You're already registered! Admin will contact you soon.")
    
    return ConversationHandler.END

# [Rest of your handlers remain the same...]

def main():
    if not BOT_TOKEN:
        logging.error("❌ Missing BOT_TOKEN in config.py!")
        return

    try:
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
        
        application.add_error_handler(error_handler)
        
        # Modified ConversationHandler setup
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
        
        # [Rest of your handler setup remains the same...]
        
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
    main()
