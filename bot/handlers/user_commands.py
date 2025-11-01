import logging
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
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

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """Dostępne komendy:
/start - Rozpocznij korzystanie z bota
/info - Informacje o bocie
/kontakt - Dane kontaktowe
/help - Ta pomoc"""
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

    async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot jest nadal aktywny. Użyj /start aby sprawdzić status.")

    async def status_basic(update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = await command_bus.user_manager.get_session_stats()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Status (basic): {stats}")

    # Handler do odbioru wiadomości w trybie admin (gdy admin czeka na input)
    async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.user_data.get('awaiting'):
            return  # Nie czekamy na input
        
        user_id = update.effective_user.id
        owner_ids = getattr(settings, 'owner_users', [])
        admin_ids = getattr(settings, 'admin_users', [])
        
        # Sprawdź czy to admin
        is_admin = (user_id in owner_ids) or (user_id in admin_ids)
        if not is_admin:
            return
            
        awaiting = context.user_data.get('awaiting')
        text_input = update.message.text or ""
        
        try:
            if awaiting == 'groups_add':
                svc = command_bus.services.groups_service
                added, skipped = await svc.add_groups_bulk(text_input.strip())
                await update.effective_chat.send_message(f"Dodano: {added}, Pominięto: {skipped}")
                
            elif awaiting == 'groups_bulk':
                svc = command_bus.services.groups_service
                added, skipped = await svc.add_groups_bulk(text_input)
                await update.effective_chat.send_message(f"Dodano: {added}, Pominięto: {skipped}")
                
            elif awaiting == 'groups_del':
                try:
                    group_id = int(text_input.strip())
                    async with command_bus.database.get_session() as db:
                        await db.execute(text("DELETE FROM groups WHERE id = :id"), {"id": group_id})
                        await db.commit()
                    await update.effective_chat.send_message(f"Usunięto grupę ID={group_id}")
                except Exception as e:
                    await update.effective_chat.send_message(f"Błąd usuwania: {e}")
                    
            elif awaiting == 'set_info':
                async with command_bus.database.get_session() as db:
                    await db.execute(text(
                        """
                        INSERT INTO config (key, value, created_at, updated_at)
                        VALUES ('info_text', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
                        """
                    ), {"val": text_input})
                    await db.commit()
                await update.effective_chat.send_message("Zapisano INFO.")
                
            elif awaiting == 'set_kontakt':
                async with command_bus.database.get_session() as db:
                    await db.execute(text(
                        """
                        INSERT INTO config (key, value, created_at, updated_at)
                        VALUES ('kontakt_text', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
                        """
                    ), {"val": text_input})
                    await db.commit()
                await update.effective_chat.send_message("Zapisano KONTAKT.")
                
            elif awaiting == 'set_time':
                try:
                    minutes = int(text_input.strip())
                    if minutes <= 0:
                        raise ValueError
                    async with command_bus.database.get_session() as db:
                        await db.execute(text(
                            """
                            INSERT INTO config (key, value, created_at, updated_at)
                            VALUES ('global_interval_minutes', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
                            """
                        ), {"val": str(minutes)})
                        await db.commit()
                    await update.effective_chat.send_message(f"Zapisano globalny interwał: {minutes} min")
                except Exception:
                    await update.effective_chat.send_message("Nieprawidłowa liczba. Spróbuj ponownie.")
                    
            elif awaiting == 'set_ex_time':
                try:
                    minutes = int(text_input.strip())
                    if minutes <= 0:
                        raise ValueError
                    async with command_bus.database.get_session() as db:
                        await db.execute(text(
                            """
                            INSERT INTO config (key, value, created_at, updated_at)
                            VALUES ('excluded_interval_minutes', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
                            """
                        ), {"val": str(minutes)})
                        await db.commit()
                    await update.effective_chat.send_message(f"Zapisano Ex-Time: {minutes} min")
                except Exception:
                    await update.effective_chat.send_message("Nieprawidłowa liczba. Spróbuj ponownie.")
                    
        finally:
            # Wyczyść stan oczekiwania
            context.user_data.pop('awaiting', None)

    # Public commands tylko te z 2.2.1
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("kontakt", kontakt))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stop", stop))  # Opcjonalnie, niewidoczne w menu
    app.add_handler(CommandHandler("status", status_basic))  # Ukryte, dla debug
    
    # Handler do odbierania inputów w trybie admin
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input), group=1)
    
    logger.info("User handlers registered: /start, /info, /kontakt, /help, /stop, /status, admin_input_handler")


async def setup_bot_commands(app: Application):
    """Ustaw widoczne komendy zgodnie z punktem 2.2.1"""
    bot_commands = [
        BotCommand("start", "Rozpocznij korzystanie z bota"),
        BotCommand("info", "Informacje o bocie"),
        BotCommand("kontakt", "Dane kontaktowe"),
        BotCommand("help", "Pomoc i lista komend"),
    ]
    await app.bot.set_my_commands(bot_commands)
    logger.info(f"Bot commands set: {[cmd.command for cmd in bot_commands]}")
