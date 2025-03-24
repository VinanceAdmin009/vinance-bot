import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackContext,
    MessageHandler, Filters, ConversationHandler,
    CallbackQueryHandler
)
from config import *
from tendo.singleton import SingleInstance

# ===== SINGLETON LOCK =====
lockfile = "vinance-bot.lock"
me = SingleInstance(lockfile=lockfile)  # Stronger file locking

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== DATABASE =====
class UserDB:
    def __init__(self):
        self.active = []
        self.pending = []
    
    def add_user(self, user_data: dict):
        self.pending.append(user_data)
    
    def approve_user(self, user_id: int):
        user = next(u for u in self.pending if u['id'] == user_id)
        self.active.append(user)
        self.pending.remove(user)
        return user

db = UserDB()

# ===== CONVERSATION STATES =====
GET_USERNAME, GET_EMAIL = range(2)

# ===== UI COMPONENTS =====
def build_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("📩 Message User", callback_data="message_user")],
        [InlineKeyboardButton("✅ Approve Users", callback_data="approve_list")]
    ])

# ===== CORE FUNCTIONS =====
def start(update: Update, context: CallbackContext):
    if update.message.chat.id in ADMIN_CHAT_IDS:
        show_admin_panel(update)
    else:
        update.message.reply_text(
            WELCOME_MSG,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔓 Activate AI", callback_data="activate")]
            ]),
            parse_mode="Markdown"
        )

def show_admin_panel(update: Update):
    stats = {
        "active_users": len(db.active),
        "pending_users": len(db.pending),
        "banned_users": 0
    }
    update.message.reply_text(
        ADMIN_DASHBOARD.format(**stats),
        reply_markup=build_admin_menu(),
        parse_mode="Markdown"
    )

def start_registration(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()  # Important to acknowledge callback
    query.edit_message_text("📝 Please enter your Vinance username:")
    return GET_USERNAME

def get_username(update: Update, context: CallbackContext):
    context.user_data['username'] = update.message.text
    update.message.reply_text("📧 Now enter your email address:")
    return GET_EMAIL

def get_email(update: Update, context: CallbackContext):
    email = update.message.text
    if not any(domain in email for domain in EMAIL_DOMAINS):
        update.message.reply_text(f"❌ Invalid email domain. Allowed: {', '.join(EMAIL_DOMAINS)}")
        return GET_EMAIL
    
    user_data = {
        'id': update.message.from_user.id,
        'username': context.user_data['username'],
        'email': email,
        'name': update.message.from_user.full_name
    }
    db.add_user(user_data)
    
    for admin_id in ADMIN_CHAT_IDS:
        context.bot.send_message(
            chat_id=admin_id,
            text=f"🆕 *New Registration*\n\n"
                 f"• Name: {user_data['name']}\n"
                 f"• Username: {user_data['username']}\n"
                 f"• Email: {user_data['email']}\n\n"
                 f"Approve with: /approve_{user_data['id']}",
            parse_mode="Markdown"
        )
    
    update.message.reply_text("✅ Registration complete! Admin will contact you soon.")
    return ConversationHandler.END

def approve_user(update: Update, context: CallbackContext):
    try:
        user_id = int(context.args[0])
        user = db.approve_user(user_id)
        
        context.bot.send_message(
            chat_id=user_id,
            text="🎉 *Your Vinance AI access has been approved!*\n\n"
                 "Start trading with /start",
            parse_mode="Markdown"
        )
        update.message.reply_text(f"✅ Approved {user['name']}")
    except Exception as e:
        logger.error(f"Approval error: {e}")
        update.message.reply_text("Usage: /approve_USERID")

# ===== ADMIN MESSAGING =====
def start_broadcast(update: Update, context: CallbackContext):
    if update.message.chat.id not in ADMIN_CHAT_IDS:
        return
    
    context.user_data['broadcast_mode'] = True
    update.message.reply_text("📢 Enter broadcast message (text or photo with caption):")

def start_user_message(update: Update, context: CallbackContext):
    if update.message.chat.id not in ADMIN_CHAT_IDS:
        return
    
    context.user_data['user_message_mode'] = True
    update.message.reply_text("📩 Enter user ID to message:")

def handle_admin_message(update: Update, context: CallbackContext):
    if 'user_message_mode' in context.user_data:
        try:
            user_id = int(update.message.text)
            context.user_data['target_user'] = user_id
            update.message.reply_text("✍️ Now enter your message:")
            context.user_data.pop('user_message_mode')
            context.user_data['send_to_user'] = True
        except:
            update.message.reply_text("❌ Invalid user ID")
    
    elif 'send_to_user' in context.user_data:
        user_id = context.user_data['target_user']
        try:
            if update.message.photo:
                update.message.copy(chat_id=user_id)
            else:
                context.bot.send_message(chat_id=user_id, text=update.message.text)
            update.message.reply_text(f"✅ Message sent to user {user_id}")
        except Exception as e:
            logger.error(f"Message send error: {e}")
            update.message.reply_text("❌ Failed to send message")
        context.user_data.pop('send_to_user')
    
    elif 'broadcast_mode' in context.user_data:
        sent = 0
        for user in db.active:
            try:
                if update.message.photo:
                    update.message.copy(chat_id=user['id'])
                else:
                    context.bot.send_message(chat_id=user['id'], text=update.message.text)
                sent += 1
            except Exception as e:
                logger.error(f"Broadcast error to {user['id']}: {e}")
        update.message.reply_text(f"📢 Broadcast sent to {sent}/{len(db.active)} users")
        context.user_data.pop('broadcast_mode')

# ===== ERROR HANDLER =====
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error: {context.error}")
    if update.callback_query:
        update.callback_query.answer("⚠️ An error occurred, please try again")

# ===== MAIN =====
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Add error handler
    dp.add_error_handler(error_handler)
    
    # Registration flow with explicit per_message=True
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_registration, pattern='^activate$', per_message=True)
        ],
        states={
            GET_USERNAME: [MessageHandler(Filters.text & ~Filters.command, get_username)],
            GET_EMAIL: [MessageHandler(Filters.text & ~Filters.command, get_email)]
        },
        fallbacks=[]
    )
    
    # User commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv_handler)
    
    # Admin commands
    dp.add_handler(CommandHandler("admin", show_admin_panel))
    dp.add_handler(CommandHandler("approve_", approve_user))
    dp.add_handler(CommandHandler("broadcast", start_broadcast))
    dp.add_handler(CommandHandler("message", start_user_message))
    
    # Message handlers
    dp.add_handler(MessageHandler(
        Filters.text | Filters.photo, 
        handle_admin_message,
        pass_user_data=True
    ))
    
    # Check for existing updates to prevent conflict
    updater.bot.get_updates(offset=-1)
    
    updater.start_polling(drop_pending_updates=True)
    logger.info("Bot started successfully")
    updater.idle()

if __name__ == '__main__':
    main()
