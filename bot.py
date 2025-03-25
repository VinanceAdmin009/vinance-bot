import os
import logging
import atexit
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        [InlineKeyboardButton("✅ Approve Users", callback_data="approve_list")]
    ])

# ===== CORE FUNCTIONS =====
async def start(update: Update, context: CallbackContext):
    if update.message.chat.id in ADMIN_CHAT_IDS:
        await show_admin_panel(update)
    else:
        await update.message.reply_text(
            WELCOME_MSG,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔓 Activate AI", callback_data="activate")]
            ]),
            parse_mode="Markdown"
        )

async def show_admin_panel(update: Update):
    stats = {
        "active_users": len(db.active),
        "pending_users": len(db.pending),
        "banned_users": 0
    }
    await update.message.reply_text(
        ADMIN_DASHBOARD.format(**stats),
        reply_markup=build_admin_menu(),
        parse_mode="Markdown"
    )

async def start_registration(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Please enter your Vinance username:")
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
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🆕 *New Registration*\n\n"
                     f"• Name: {user_data['name']}\n"
                     f"• Username: {user_data['username']}\n"
                     f"• Email: {user_data['email']}\n\n"
                     f"Approve with: /approve_{user_data['id']}",
                parse_mode="Markdown"
            )
        
        await update.message.reply_text("✅ Registration complete! Admin will contact you soon.")
    else:
        await update.message.reply_text("⚠️ You're already registered! Admin will contact you soon.")
    
    return ConversationHandler.END

async def approve_user(update: Update, context: CallbackContext):
    try:
        user_id = int(context.args[0])
        user = db.approve_user(user_id)
        
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 *Your Vinance AI access has been approved!*\n\n"
                 "Start trading with /start",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Approved {user['name']}")
    except ValueError as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    except:
        await update.message.reply_text("Usage: /approve_USERID")

async def start_broadcast(update: Update, context: CallbackContext):
    if update.message.chat.id not in ADMIN_CHAT_IDS:
        return
    
    context.user_data['broadcast_mode'] = True
    await update.message.reply_text("📢 Enter broadcast message (text or photo with caption):")

async def start_user_message(update: Update, context: CallbackContext):
    if update.message.chat.id not in ADMIN_CHAT_IDS:
        return
    
    context.user_data['user_message_mode'] = True
    await update.message.reply_text("📩 Enter user ID to message:")

async def handle_admin_message(update: Update, context: CallbackContext):
    if 'user_message_mode' in context.user_data:
        try:
            user_id = int(update.message.text)
            context.user_data['target_user'] = user_id
            await update.message.reply_text("✍️ Now enter your message:")
            context.user_data.pop('user_message_mode')
            context.user_data['send_to_user'] = True
        except:
            await update.message.reply_text("❌ Invalid user ID")
    
    elif 'send_to_user' in context.user_data:
        user_id = context.user_data['target_user']
        try:
            if update.message.photo:
                await update.message.copy(chat_id=user_id)
            else:
                await context.bot.send_message(chat_id=user_id, text=update.message.text)
            await update.message.reply_text(f"✅ Message sent to user {user_id}")
        except:
            await update.message.reply_text("❌ Failed to send message")
        context.user_data.pop('send_to_user')
    
    elif 'broadcast_mode' in context.user_data:
        sent = 0
        for user in db.active:
            try:
                if update.message.photo:
                    await update.message.copy(chat_id=user['id'])
                else:
                    await context.bot.send_message(chat_id=user['id'], text=update.message.text)
                sent += 1
            except:
                continue
        await update.message.reply_text(f"📢 Broadcast sent to {sent}/{len(db.active)} users")
        context.user_data.pop('broadcast_mode')

async def error_handler(update: Update, context: CallbackContext):
    error = str(context.error)
    logging.error(f"🚨 Error: {error}")
    
    if "Conflict" in error and "getUpdates" in error:
        logging.critical("💥 CRITICAL: Multiple bot instances detected!")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_IDS[0],
                text="🚨 MULTIPLE INSTANCE ALERT!\n\n"
                     "Another bot instance was detected and this instance will shutdown.",
                parse_mode="Markdown"
            )
        except:
            pass
        os._exit(1)

async def post_init(application: Application):
    await application.bot.set_my_commands([
        ("start", "Start the bot"),
        ("admin", "Admin panel")
    ])

def main():
    if not BOT_TOKEN:
        logging.error("❌ Missing BOT_TOKEN in config.py!")
        return

    try:
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
        
        application.add_error_handler(error_handler)
        
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_registration, pattern='^activate$')],
            states={
                GET_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
                GET_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)]
            },
            fallbacks=[]
        )
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("admin", show_admin_panel))
        application.add_handler(CommandHandler("approve_", approve_user))
        application.add_handler(CommandHandler("broadcast", start_broadcast))
        application.add_handler(CommandHandler("message", start_user_message))
        application.add_handler(MessageHandler(
            filters.TEXT | filters.PHOTO,
            handle_admin_message
        ))
        
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
