import os
import re
import datetime
from collections import defaultdict
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = [5513230302]
# =========================================

# Per-group state
listening_chats = set()
sales_data = defaultdict(list)
invalid_format = defaultdict(bool)
confirmed = defaultdict(bool)


# --------- HELPERS ---------
def parse_caption(caption: str):
    if not caption:
        return None

    # Accept identifiers
    link_match = re.search(r"https://onlyfans\.com/\S+", caption)
    user_match = re.search(r"@\w+", caption)
    deleted_match = re.search(r"\bDELETED USER\b", caption, re.IGNORECASE)

    tip_match = re.search(r"\$(\d+(?:\.\d{2})?)\s*TIP", caption, re.IGNORECASE)
    ppv_match = re.search(r"\$(\d+(?:\.\d{2})?)\s*PPV", caption, re.IGNORECASE)

    # Must have TIP or PPV
    if not tip_match and not ppv_match:
        return None

    if link_match:
        identifier = link_match.group(0)
    elif user_match:
        identifier = user_match.group(0)
    elif deleted_match:
        identifier = "DELETED USER"
    else:
        return None

    return {
        "link": identifier,
        "tip": float(tip_match.group(1)) if tip_match else 0.0,
        "ppv": float(ppv_match.group(1)) if ppv_match else 0.0,
    }


# --------- COMMANDS ---------
async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Your Telegram ID:\n"
        f"ID: `{user.id}`\n"
        f"Username: @{user.username}\n"
        f"Name: {user.full_name}",
        parse_mode="Markdown",
    )


async def start_listening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    if user.id not in ALLOWED_USERS:
        await update.message.reply_text(
            "❌ You are not authorized yet.\nUse /id and send your ID to admin."
        )
        return

    listening_chats.add(chat_id)
    sales_data[chat_id].clear()
    invalid_format[chat_id] = False
    confirmed[chat_id] = False

    await update.message.reply_text("✅ Bot is now listening. Send your sales.")


async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if invalid_format[chat_id]:
        await update.message.reply_text(
            "❌ Wrong format detected.\nFix the sales and send them again.\nUse /start to reset."
        )
        return

    if not sales_data[chat_id]:
        await update.message.reply_text("No sales data yet.")
        return

    # First /done = confirmation
    if not confirmed[chat_id]:
        confirmed[chat_id] = True
        await update.message.reply_text(
            "✅ All sales recorded. Done computing.\nSend /done again to generate the summary."
        )
        return

    listening_chats.discard(chat_id)

    today = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=8)
    date_str = today.strftime("%m/%d/%Y")

    tips = [s for s in sales_data[chat_id] if s["tip"] > 0]
    ppvs = [s for s in sales_data[chat_id] if s["ppv"] > 0]

    total = sum(s["tip"] + s["ppv"] for s in sales_data[chat_id])
    net = total * 0.8

    tips_lines = [f"${s['tip']:.2f} TIP from {s['link']}" for s in tips]
    ppv_lines = [f"${s['ppv']:.2f} PPV from {s['link']}" for s in ppvs]

    summary = (
        f"Summary of Tips and VIPs for: Name\n"
        f"{date_str}\n"
        f"5PM to 1AM PST\n"
        f"Shift: (8 hours)\n"
        f"Creator: Page\n"
        f"VIP/Tips:\n" + "\n".join(tips_lines) +
        "\nPPVs:\n" + "\n".join(ppv_lines) +
        f"\n\nTOTAL GROSS SALE: ${total:.2f}"
        f"\nTOTAL NET SALE: ${net:.2f}"
    )

    await update.message.reply_text(summary)

    sales_data[chat_id].clear()
    invalid_format[chat_id] = False
    confirmed[chat_id] = False


# --------- MESSAGE HANDLER ---------
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in listening_chats:
        return

    msg = update.message
    if msg and msg.caption:
        parsed = parse_caption(msg.caption)
        if not parsed:
            invalid_format[chat_id] = True
        else:
            sales_data[chat_id].append(parsed)


# --------- MAIN ---------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("start", start_listening))
    app.add_handler(CommandHandler("done", send_summary))
    app.add_handler(MessageHandler(filters.ALL, handle_messages))

    print("🤖 Auto-confirm sales bot running...")
    app.run_polling()




















