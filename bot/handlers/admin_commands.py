from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


def setup_admin_handlers(app: Application, command_bus, settings) -> None:
    admin_cmd = getattr(settings, "admin_command_alias", "pusher")

    async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Admin panel placeholder. Use /{admin_cmd} for future menu."
        )

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = await command_bus.user_manager.get_session_stats()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Status: {stats}")

    # alias command
    app.add_handler(CommandHandler(admin_cmd, admin_panel))
    app.add_handler(CommandHandler("status", status))
