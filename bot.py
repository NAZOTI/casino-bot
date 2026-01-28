import os
import json
import random
import asyncio
from pathlib import Path
from datetime import datetime, date

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler
from telegram.constants import ParseMode

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DEV_ID = os.getenv("DEV_ID")  # твой id (для теста без таймера)

EMOJIS = ["🍒", "🍋", "🍇", "🍉", "⭐️", "🔔", "💎", "🍀", "7️⃣"]

BALANCES_FILE = Path("balances.json")
LIMITS_FILE = Path("limits.json")

START_BONUS = 200
COOLDOWN_SECONDS = 3600      # 1 час
DAILY_LIMIT = 50             # спинов в день


# ---------- helpers ----------

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


def uid(update):
    return str(update.effective_user.id)


def is_dev(update) -> bool:
    return DEV_ID is not None and uid(update) == str(DEV_ID)


def fmt_minutes_left(seconds_left: float) -> int:
    return int(seconds_left // 60) + 1


def random_triplet():
    return random.choice(EMOJIS), random.choice(EMOJIS), random.choice(EMOJIS)

async def animate_spin(msg, final_triplet):
    final_a, final_b, final_c = final_triplet

    delays = [0.18, 0.22, 0.28, 0.40]

    for d in delays[:2]:
        await asyncio.sleep(d)
        a, b, c = random_triplet()
        await msg.edit_text(f"{a} {b} {c}\n<b>Крутим…</b>", parse_mode=ParseMode.HTML)

    await asyncio.sleep(delays[2])

    make_near = random.random() < 0.80
    if make_near:
        if final_a == final_b == final_c:
            t = final_a
        elif final_a == final_b or final_a == final_c:
            t = final_a
        elif final_b == final_c:
            t = final_b
        else:
            t = random.choice(EMOJIS)

        near = (t, t, random.choice([e for e in EMOJIS if e != t]))
        variants = [near, (near[0], near[2], near[1]), (near[2], near[0], near[1])]
        a, b, c = random.choice(variants)
    else:
        a, b, c = random_triplet()

    await msg.edit_text(f"{a} {b} {c}\n<b>Ещё чуть-чуть…</b>", parse_mode=ParseMode.HTML)

    await asyncio.sleep(delays[3])
    await msg.edit_text(
        f"{final_a} {final_b} {final_c}\n<b>Готово</b>",
        parse_mode=ParseMode.HTML
    )



# ---------- commands ----------

async def myid(update, context):
    await update.message.reply_text(f"🆔 Твой ID: {uid(update)}")


async def start(update, context):
    balances = load_json(BALANCES_FILE, {})
    user = uid(update)

    bonus_line = ""
    if user not in balances:
        balances[user] = START_BONUS
        save_json(BALANCES_FILE, balances)
        bonus_line = f"\n🎁 Бонус за вход: {START_BONUS}"

    # Команды с описанием (без правил)
    await update.message.reply_text(
        "🎰 Казино-бот\n\n"
        "Команды:\n"
        "— /balance — показать баланс\n"
        "— /roll — ставка 10\n"
        "— /roll 50 — ставка от 10 до 100\n"
        "— /myid — узнать свой ID"
        + bonus_line
    )


async def balance_cmd(update, context):
    balances = load_json(BALANCES_FILE, {})
    bal = balances.get(uid(update), 0)
    await update.message.reply_text(f"💰 Баланс: {bal}")

async def roll(update, context):
    # ставка
    if context.args:
        try:
            bet = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Ставка должна быть числом")
            return
    else:
        bet = 10

    if bet < 10 or bet > 100:
        await update.message.reply_text("❌ Ставка должна быть от 10 до 100")
        return

    balances = load_json(BALANCES_FILE, {})
    limits = load_json(LIMITS_FILE, {})
    user = uid(update)

    bal = balances.get(user, 0)
    if bal < bet:
        await update.message.reply_text(f"❌ Недостаточно средств. Баланс: {bal}")
        return

    # лимиты (для дева игнорируются)
    if not is_dev(update):
        now = datetime.utcnow()
        today = str(date.today())

        info = limits.get(user, {
            "last_spin": 0,
            "date": today,
            "count": 0
        })

        if info["date"] != today:
            info["date"] = today
            info["count"] = 0

        elapsed = now.timestamp() - info["last_spin"]
        if elapsed < COOLDOWN_SECONDS:
            minutes = int((COOLDOWN_SECONDS - elapsed) // 60) + 1
            await update.message.reply_text(
                f"⏳ Крутить пока нельзя\nПопробуй снова через {minutes} мин"
            )
            return

        if info["count"] >= DAILY_LIMIT:
            await update.message.reply_text(
                "🚫 Лимит спинов на сегодня исчерпан\nВозвращайся завтра"
            )
            return
    else:
        now = datetime.utcnow()
        info = limits.get(user, {
            "last_spin": 0,
            "date": str(date.today()),
            "count": 0
        })

    # ---------- шанс ----------
    def spin_final():
        r = random.random()
        if r < 0.05:
            x = random.choice(EMOJIS)
            return x, x, x
        if r < 0.40:
            x = random.choice(EMOJIS)
            y = random.choice([e for e in EMOJIS if e != x])
            return random.choice([(x, x, y), (x, y, x), (y, x, x)])
        a = random.choice(EMOJIS)
        b = random.choice([e for e in EMOJIS if e != a])
        c = random.choice([e for e in EMOJIS if e != a and e != b])
        return a, b, c

    final_a, final_b, final_c = spin_final()

    msg = await update.message.reply_text("🎰")
    await animate_spin(msg, (final_a, final_b, final_c))

    a, b, c = final_a, final_b, final_c

        # ---------- результат ----------
    if a == b == c:
        profit = bet * 5
    elif a == b or a == c or b == c:
        profit = bet * 2
    else:
        profit = -bet

    # обновляем баланс
    balances[user] = bal + profit
    save_json(BALANCES_FILE, balances)

    # оформляем текст результата
    if a == b == c:
        text = (
            f"💥 <b>ДЖЕКПОТ СОРВАН!</b> {a}{b}{c}\n"
            f"<b>+{profit} Coin!</b>\n"
            f"Твой баланс: <b>{balances[user]}</b>"
        )
    elif a == b or a == c or b == c:
        text = (
            f"😉 <b>Почти джекпот!</b> {a}{b}{c}\n"
            f"<b>+{profit} Coin</b>\n"
            f"Баланс: <b>{balances[user]}</b>"
        )
    else:
        text = (
            f"😢 <b>Не повезло:</b> {a}{b}{c}\n"
            f"<b>{profit} Coin</b>\n"
            f"Баланс: <b>{balances[user]}</b>"
        )

    # сохраняем лимиты
    info["last_spin"] = now.timestamp()
    info["date"] = str(date.today())
    info["count"] += 1
    limits[user] = info
    save_json(LIMITS_FILE, limits)

    await msg.edit_text(text, parse_mode=ParseMode.HTML)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("myid", myid))
    print("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
