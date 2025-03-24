# ===== SECURITY NOTE =====
# Never commit real tokens to git! Use environment variables in production
import os

# ===== CORE CONFIGURATION =====
BOT_TOKEN = os.getenv('BOT_TOKEN', "7758916476:AAFNNxSZQ56ni1mtjeEQnOCFQc9oPzHa26U")  # Fallback token
ADMIN_CHAT_IDS = [int(id) for id in os.getenv('ADMIN_CHAT_IDS', "5295843924").split(",")]  # Comma-separated IDs
LOGO_URL = os.getenv('LOGO_URL', "https://vinance.pro/assets/images/logo_icon/logo.png")

# ===== MESSAGE TEMPLATES =====
WELCOME_MSG = """✨ *Welcome to Vinance Trade AI V2.01* ✨

🚀 Automated trading with up to 95% trade accuracy, thereby ensuring maximized profit margin up to 50% per trade session.
💰 0% usage fees/charges for employees and early users for up to 3 months"""

ADMIN_DASHBOARD = """👑 *Admin Panel*

▸ Active Users: {active_users}
▸ Pending Approvals: {pending_users}
▸ Banned Users: {banned_users}"""  # Added missing banned_users placeholder

# ===== VALIDATION SETTINGS =====
EMAIL_DOMAINS = os.getenv(
    'EMAIL_DOMAINS', 
    "gmail.com,yahoo.com,outlook.com,mail.com"
).split(",")

# ===== PERFORMANCE SETTINGS =====
POLL_INTERVAL = float(os.getenv('POLL_INTERVAL', 0.5))  # Seconds between updates
