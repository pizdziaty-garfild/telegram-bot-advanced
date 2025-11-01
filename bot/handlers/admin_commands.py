from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters

from bot.core.enhanced_rbac_manager import EnhancedRBACManager
from config.settings import Settings
from bot.services.groups_service import GroupsService
from bot.services.config_service import ConfigService

ASK_BULK_GROUPS = 1001
ASK_SET_INFO = 1002
ASK_SET_KONTAKT = 1003
ASK_SET_TIME = 1004
ASK_SET_EX_TIME = 1005


def setup_admin_handlers(app: Application, command_bus, settings: Settings) -> None:
    admin_cmd = getattr(settings, "admin_command_alias", "pusher")

    async def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        uid = update.effective_user.id if update.effective_user else None
        if not uid:
            return False
        # Fallback: jeśli DB nie gotowe, sprawdź Settings
        try:
            allowed = await command_bus.rbac.is_admin(uid)
        except Exception:
            allowed = (uid in settings.owner_users) or (uid in settings.admin_users)
        return allowed

    async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return
        kb = [
            [InlineKeyboardButton("Set Info", callback_data="set_info"), InlineKeyboardButton("Set Kontakt", callback_data="set_kontakt")],
            [InlineKeyboardButton("Time", callback_data="time"), InlineKeyboardButton("Ex-Time", callback_data="ex_time")],
            [InlineKeyboardButton("Groups", callback_data="groups"), InlineKeyboardButton("Status", callback_data="status")],
        ]
        await update.effective_chat.send_message("Admin Panel", reply_markup=InlineKeyboardMarkup(kb))

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return
        stats = await command_bus.user_manager.get_session_stats()
        await update.effective_chat.send_message(f"Status: {stats}")

    async def on_groups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return
        kb = [
            [InlineKeyboardButton("Add", callback_data="groups_add"), InlineKeyboardButton("Delete", callback_data="groups_del")],
            [InlineKeyboardButton("List", callback_data="groups_list"), InlineKeyboardButton("Bulk Add", callback_data="groups_bulk")],
            [InlineKeyboardButton("Back", callback_data="back")],
        ]
        await update.effective_chat.send_message("Groups Menu", reply_markup=InlineKeyboardMarkup(kb))

    async def on_groups_bulk_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        await update.effective_chat.send_message("Wklej listę grup (każda linia = chat_id lub @username)")
        return ASK_BULK_GROUPS

    async def on_groups_bulk_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        text_blob = update.message.text or ""
        svc = GroupsService(command_bus.database)
        added, skipped = await svc.add_groups_bulk(text_blob)
        await update.effective_chat.send_message(f"Dodano: {added}, Pominieto: {skipped}")
        return ConversationHandler.END

    async def on_set_info_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        await update.effective_chat.send_message("Wklej treść INFO (zastąpi obecną)")
        return ASK_SET_INFO

    async def on_set_info_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        text_val = update.message.text or ""
        async with command_bus.database.get_session() as db:
            await db.execute(text("""
                INSERT INTO config (key, value, created_at, updated_at)
                VALUES ('info_text', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
            """), {"val": text_val})
            await db.commit()
        await update.effective_chat.send_message("Zapisano INFO.")
        return ConversationHandler.END

    async def on_set_kontakt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        await update.effective_chat.send_message("Wklej treść KONTAKT (zastąpi obecną)")
        return ASK_SET_KONTAKT

    async def on_set_kontakt_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        text_val = update.message.text or ""
        async with command_bus.database.get_session() as db:
            await db.execute(text("""
                INSERT INTO config (key, value, created_at, updated_at)
                VALUES ('kontakt_text', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
            """), {"val": text_val})
            await db.commit()
        await update.effective_chat.send_message("Zapisano KONTAKT.")
        return ConversationHandler.END

    async def on_set_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        await update.effective_chat.send_message("Podaj globalny interwał w minutach (liczba > 0)")
        return ASK_SET_TIME

    async def on_set_time_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        try:
            minutes = int((update.message.text or "").strip())
            if minutes <= 0:
                raise ValueError
        except Exception:
            await update.effective_chat.send_message("Nieprawidłowa liczba. Spróbuj ponownie.")
            return ConversationHandler.END
        async with command_bus.database.get_session() as db:
            await db.execute(text("""
                INSERT INTO config (key, value, created_at, updated_at)
                VALUES ('global_interval_minutes', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
            """), {"val": str(minutes)})
            await db.commit()
        await update.effective_chat.send_message(f"Zapisano globalny interwał: {minutes} min")
        return ConversationHandler.END

    async def on_set_ex_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        await update.effective_chat.send_message("Podaj interwał Ex-Time (minuty > 0)")
        return ASK_SET_EX_TIME

    async def on_set_ex_time_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return ConversationHandler.END
        try:
            minutes = int((update.message.text or "").strip())
            if minutes <= 0:
                raise ValueError
        except Exception:
            await update.effective_chat.send_message("Nieprawidłowa liczba. Spróbuj ponownie.")
            return ConversationHandler.END
        async with command_bus.database.get_session() as db:
            await db.execute(text("""
                INSERT INTO config (key, value, created_at, updated_at)
                VALUES ('excluded_interval_minutes', :val, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=:val, updated_at=CURRENT_TIMESTAMP
            """), {"val": str(minutes)})
            await db.commit()
        await update.effective_chat.send_message(f"Zapisano Ex-Time: {minutes} min")
        return ConversationHandler.END

    async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return
        query = update.callback_query
        data = query.data if query else ""
        await query.answer()
        if data == "groups":
            await on_groups_menu(update, context)
        elif data == "groups_bulk":
            await on_groups_bulk_start(update, context)
        elif data == "set_info":
            await on_set_info_start(update, context)
        elif data == "set_kontakt":
            await on_set_kontakt_start(update, context)
        elif data == "time":
            await on_set_time_start(update, context)
        elif data == "ex_time":
            await on_set_ex_time_start(update, context)
        elif data == "status":
            await status(update, context)
        else:
            await update.effective_chat.send_message("TODO: implement menu action")

    # Commands
    app.add_handler(CommandHandler(admin_cmd, admin_panel))
    app.add_handler(CommandHandler("status", status))

    # Callback handler for inline menu
    app.add_handler(CallbackQueryHandler(on_callback))

    # Conversations
    conv_bulk = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_groups_bulk_start, pattern="^groups_bulk$")],
        states={ASK_BULK_GROUPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_groups_bulk_receive)]},
        fallbacks=[CommandHandler(admin_cmd, admin_panel)],
        per_message=False,
    )
    conv_info = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_set_info_start, pattern="^set_info$")],
        states={ASK_SET_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_set_info_receive)]},
        fallbacks=[CommandHandler(admin_cmd, admin_panel)],
        per_message=False,
    )
    conv_kontakt = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_set_kontakt_start, pattern="^set_kontakt$")],
        states={ASK_SET_KONTAKT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_set_kontakt_receive)]},
        fallbacks=[CommandHandler(admin_cmd, admin_panel)],
        per_message=False,
    )
    conv_time = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_set_time_start, pattern="^time$")],
        states={ASK_SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_set_time_receive)]},
        fallbacks=[CommandHandler(admin_cmd, admin_panel)],
        per_message=False,
    )
    conv_ex_time = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_set_ex_time_start, pattern="^ex_time$")],
        states={ASK_SET_EX_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_set_ex_time_receive)]},
        fallbacks=[CommandHandler(admin_cmd, admin_panel)],
        per_message=False,
    )

    app.add_handler(conv_bulk)
    app.add_handler(conv_info)
    app.add_handler(conv_kontakt)
    app.add_handler(conv_time)
    app.add_handler(conv_ex_time)
