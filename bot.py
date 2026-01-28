import os
import json
import random
import asyncio
import threading
from pathlib import Path
from datetime import datetime, date

from dotenv import load_dotenv
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

# ----------------- ENV -----------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DEV_ID = os.getenv("DEV_ID")

# ----------------- CONSTANTS -----------------
EMOJIS = ["🍒", "🍋", "🍇", "🍉", "⭐", "🔔", "💎", "🍀", "7️⃣"]

START_BONUS = 200
DAILY_LIMIT = 10
COOLDOWN_SECONDS = 3600  # 1 час

# ----------------- FILES -----------------
BASE = Path(".")
BALANCES_FILE = BASE / "balances.json"
DEV_BALANCES_FILE = BASE / "dev_balances.json"
LIMITS_FILE = BASE / "limits.json"
SETTINGS_FILE = BASE / "settings.json"

# ----------------- JSON HELPERS -----------------
def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

# ----------------- DEV / LOCK -----------------
def is_dev(update: Update) -> bool:
    return DEV_ID and str(update.effective_user.id) == str(DEV_ID)

def settings():
    return load_json(SETTINGS_FILE, {"locked": False, "dev_mode": False})

def save_settings(data):
    save_json(SETTINGS_FILE, data)

def bot_locked():
    return settings().get("locked", False)

def dev_mode():
    return settings().get("dev_mode", False)

# ----------------- BALANCE -----------------
def get_balance(user_id: str, dev=False):
    file = DEV_BALANCES_FILE if dev else BALANCES_FILE
    return load_json(file, {}).get(user_id, 0)

def set_balance(user_id: str, value: int, dev=False):
    file = DEV_BALANCES_FILE if dev else BALANCES_FILE
    data = load_json(file, {})
    data[user_id] = value
    save_json(file, data)

# ----------------- LIMITS -----------------
def spins_left_today(user_id: str):
    limits = load_json(LIMITS_FILE, {})
    info = limits.get(user_id, {"date": str(date.today()), "count": 0})

    if info["date"] != str(date.today()):
        return DAILY_LIMIT

    return max(0, DAILY_LIMIT - info["count"])

# ----------------- COMMANDS -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    balances = load_json(BALANCES_FILE, {})

    if user not in balances:
        balances[user] = START_BONUS
        save_json(BALANCES_FILE, balances)

    await update.message.reply_text(
        "🎰 Добро пожаловать в Casino Roll Bot!\n"
        "Используй /roll чтобы крутить 🎲"
    )

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    dev = dev_mode() and is_dev(update)

    bal = get_balance(user, dev)
    text = f"💰 Баланс: <b>{bal}</b>"

    if not dev:
        text += f"\n🎟 Осталось круток сегодня: {spins_left_today(user)}"
    else:
        text += "\n🛠 DEV MODE"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)

    if bot_locked() and not is_dev(update):
        await update.message.reply_text("⛔ Бот временно выключен.")
        return

    dev = dev_mode() and is_dev(update)

    # лимиты только не для dev
    if not dev:
        if spins_left_today(user) <= 0:
            await update.message.reply_text("⏳ Крутки на сегодня закончились.")
            return

    bal = get_balance(user, dev)

    # ставка: /roll -> 10, /roll 25 -> 25
if context.args:
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ставка должна быть числом. Пример: /roll 25")
        return
else:
    bet = 10

if bet < 10 or bet > 100:
    await update.message.reply_text("❌ Ставка должна быть от 10 до 100")
    return


    a, b, c = random.choices(EMOJIS, k=3)

    if a == b == c:
        profit = bet * 5
        text = f"💥 <b>ДЖЕКПОТ СОРВАН!</b> {a}{b}{c}\n+{profit} Coin"
    elif a == b or a == c or b == c:
        profit = bet * 2
        text = f"😉 <b>Почти джекпот!</b> {a}{b}{c}\n+{profit} Coin"
    else:
        profit = -bet
        text = f"😢 <b>Не повезло:</b> {a}{b}{c}\n{profit} Coin"

    bal += profit
    set_balance(user, bal, dev)

    if not dev:
        limits = load_json(LIMITS_FILE, {})
        info = limits.get(user, {"date": str(date.today()), "count": 0})
        info["date"] = str(date.today())
        info["count"] += 1
        limits[user] = info
        save_json(LIMITS_FILE, limits)
        text += f"\n🎟 Осталось: {spins_left_today(user)}"

    text += f"\nБаланс: <b>{bal}</b>"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ----------------- DEV COMMANDS -----------------
async def dev_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_dev(update):
        await update.message.reply_text("❌ Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Используй /dev on или /dev off")
        return

    s = settings()
    if context.args[0] == "on":
        s["dev_mode"] = True
        save_settings(s)
        await update.message.reply_text("🛠 DEV MODE ВКЛЮЧЁН")
    elif context.args[0] == "off":
        s["dev_mode"] = False
        save_settings(s)
        await update.message.reply_text("🔒 DEV MODE ВЫКЛЮЧЕН")

async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_dev(update):
        await update.message.reply_text("❌ Нет доступа.")
        return
    s = settings()
    s["locked"] = True
    save_settings(s)
    await update.message.reply_text("🔒 Бот выключен.")

async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_dev(update):
        await update.message.reply_text("❌ Нет доступа.")
        return
    s = settings()
    s["locked"] = False
    save_settings(s)
    await update.message.reply_text("✅ Бот включён.")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Твой ID: {update.effective_user.id}")

# ----------------- WEB (Render) -----------------
web = Flask(__name__)

@web.get("/")
def home():
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

# ----------------- MAIN -----------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("dev", dev_cmd))
    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("unlock", unlock_cmd))
    app.add_handler(CommandHandler("myid", myid))

    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    main()
