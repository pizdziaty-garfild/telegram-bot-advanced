from telegram.ext import Application, CommandHandler


def setup_user_handlers(app: Application, command_bus, settings) -> None:
    async def start(update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! Bot is running.")

    async def info(update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Info placeholder (will read from Config).")

    async def kontakt(update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Kontakt placeholder (will read from Config).")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", start))  # placeholder
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("kontakt", kontakt))
