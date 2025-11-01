import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from sqlalchemy import text

logger = logging.getLogger(__name__)


def setup_user_handlers(app: Application, command_bus, settings) -> None:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! Bot is running.")

    async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            async with command_bus.database.get_session() as db:
                result = await db.execute(text("SELECT value FROM config WHERE key = 'info_text'"))
                row = result.fetchone()
                info_text = row.value if row else "Brak informacji (ustaw przez admin panel)."
        except Exception:
            info_text = "Info placeholder (config not available)."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=info_text)

    async def kontakt(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            async with command_bus.database.get_session() as db:
                result = await db.execute(text("SELECT value FROM config WHERE key = 'kontakt_text'"))
                row = result.fetchone()
                kontakt_text = row.value if row else "Brak kontaktu (ustaw przez admin panel)."
        except Exception:
            kontakt_text = "Kontakt placeholder (config not available)."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=kontakt_text)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", start))  # placeholder
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("kontakt", kontakt))
    
    logger.info("User handlers registered: /start, /stop, /info, /kontakt")
