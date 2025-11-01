import logging
from telegram.ext import Application, CommandHandler

logger = logging.getLogger(__name__)


def setup_user_handlers(app: Application, command_bus, settings) -> None:
    async def start(update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! Bot is running.")

    async def info(update, context):
        from sqlalchemy import text
        try:
            async with command_bus.database.get_session() as db:
                result = await db.execute(text("SELECT value FROM config WHERE key = 'info_text'"))
                row = result.fetchone()
                info_text = row.value if row else "Brak informacji (ustaw przez admin panel)."
        except Exception:
            info_text = "Info placeholder (config not available)."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=info_text)

    async def kontakt(update, context):
        from sqlalchemy import text
        try:
            async with command_bus.database.get_session() as db:
                result = await db.execute(text("SELECT value FROM config WHERE key = 'kontakt_text'"))
                row = result.fetchone()
                kontakt_text = row.value if row else "Brak kontaktu (ustaw przez admin panel)."
        except Exception:
            kontakt_text = "Kontakt placeholder (config not available)."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=kontakt_text)

    async def test(update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="TEST działa!")

    # Tymczasowy diagnostyczny alias admin panelu bez RBAC
    async def pusher_basic(update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Admin Menu (basic). Jeśli to widzisz, admin_commands.py się nie podpiął.")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("kontakt", kontakt))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("pusher", pusher_basic))

    logger.info("User handlers registered: /start, /info, /kontakt, /test, /pusher (basic)")
