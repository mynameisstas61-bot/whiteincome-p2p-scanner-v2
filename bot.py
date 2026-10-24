import os
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo, Update
from telegram.ext import Application, CommandHandler, ContextTypes
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not WEBAPP_URL or "YOUR-USERNAME" in WEBAPP_URL:
        await update.message.reply_text(
            "WHITEINCOME Scanner запущен, но WEBAPP_URL ещё не настроен. "
            "Укажи URL опубликованного Mini App в переменной WEBAPP_URL."
        )
        return
    keyboard = [[InlineKeyboardButton("🚀 Открыть WHITEINCOME Scanner",
                                      web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        "WHITEINCOME Scanner\\n\\n"
        "Выбирай депозит, активы и порог спреда в Mini App. "
        "Сигналы предварительные: переводы и сделки бот не выполняет.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def set_menu(app: Application):
    if WEBAPP_URL and "YOUR-USERNAME" not in WEBAPP_URL:
        try:
            await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text="Открыть сканер", web_app=WebAppInfo(url=WEBAPP_URL)
            ))
        except Exception as exc:
            print(f"Menu button was not set automatically: {exc}")

def main():
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")
    application = Application.builder().token(TOKEN).post_init(set_menu).build()
    application.add_handler(CommandHandler("start", start))
    print("WHITEINCOME Telegram bot is running.")
    application.run_polling()

if __name__ == "__main__":
    main()
