import os
import logging
import atexit
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackContext,
    MessageHandler, Filters, ConversationHandler,
    CallbackQueryHandler
)
from config import *
from tendo.singleton import SingleInstance

# ===== INITIALIZATION =====
try:
    me = SingleInstance(flavor_id="vinance-bot-prod")
except:
    logging.critical("🚨 Another bot instance is already running! Exiting...")
    exit(1)

# Cleanup lock file on exit
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
    query.answer()
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
    
    if db.add_user(user_data):
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
    else:
        update.message.reply_text("⚠️ You're already registered! Admin will contact you soon.")
    
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
    except ValueError as e:
        update.message.reply_text(f"❌ Error: {str(e)}")
    except:
        update.message.reply_text("Usage: /approve_USERID")

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
        except:
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
            except:
                continue
        update.message.reply_text(f"📢 Broadcast sent to {sent}/{len(db.active)} users")
        context.user_data.pop('broadcast_mode')

def error_handler(update: Update, context: CallbackContext):
    error = str(context.error)
    logging.error(f"🚨 Error: {error}")
    
    if "Conflict" in error and "getUpdates" in error:
        logging.critical("💥 CRITICAL: Multiple bot instances detected!")
        try:
            context.bot.send_message(
                chat_id=ADMIN_CHAT_IDS[0],
                text="🚨 MULTIPLE INSTANCE ALERT!\n\n"
                     "Another bot instance was detected and this instance will shutdown.",
                parse_mode="Markdown"
            )
        except:
            pass
        os._exit(1)

def main():
    if not BOT_TOKEN:
        logging.error("❌ Missing BOT_TOKEN in config.py!")
        return

    try:
        updater = Updater(
            BOT_TOKEN,
            use_context=True,
            request_kwargs={
                'read_timeout': 30,
                'connect_timeout': 30,
                'pool_timeout': 30
            }
        )
        dp = updater.dispatcher
        
        dp.add_error_handler(error_handler)
        
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_registration, pattern='^activate$')],
            states={
                GET_USERNAME: [MessageHandler(Filters.text & ~Filters.command, get_username)],
                GET_EMAIL: [MessageHandler(Filters.text & ~Filters.command, get_email)]
            },
            fallbacks=[]
        )
        
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(conv_handler)
        dp.add_handler(CommandHandler("admin", show_admin_panel))
        dp.add_handler(CommandHandler("approve_", approve_user))
        dp.add_handler(CommandHandler("broadcast", start_broadcast))
        dp.add_handler(CommandHandler("message", start_user_message))
        dp.add_handler(MessageHandler(
            Filters.text | Filters.photo, 
            handle_admin_message,
            pass_user_data=True
        ))
        
        updater.start_polling(
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
        
        logging.info("🌈 Bot started successfully!")
        updater.idle()
        
    except Exception as e:
        logging.critical(f"💥 FATAL STARTUP ERROR: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main()
