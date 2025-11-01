from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters

from bot.core.enhanced_rbac_manager import EnhancedRBACManager

ASK_BULK_GROUPS = 1001


def setup_admin_handlers(app: Application, command_bus, settings) -> None:
    admin_cmd = getattr(settings, "admin_command_alias", "pusher")

    async def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        uid = update.effective_user.id if update.effective_user else None
        if not uid:
            return False
        return await command_bus.rbac.is_admin(uid)

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
        added, skipped = await command_bus.database.initialize() or (0, 0)  # placeholder to satisfy linter
        # use GroupsService via command_bus.scheduler or create one off
        from bot.services.groups_service import GroupsService
        svc = GroupsService(command_bus.database)
        added, skipped = await svc.add_groups_bulk(text_blob)
        await update.effective_chat.send_message(f"Dodano: {added}, Pominieto: {skipped}")
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
            # start conversation
            await on_groups_bulk_start(update, context)
        elif data == "status":
            await status(update, context)
        else:
            await update.effective_chat.send_message("TODO: implement menu action")

    # Commands
    app.add_handler(CommandHandler(admin_cmd, admin_panel))
    app.add_handler(CommandHandler("status", status))
    # Callback handler for inline menu
    app.add_handler(CallbackQueryHandler(on_callback))

    # Conversation for Bulk Add
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_groups_bulk_start, pattern="^groups_bulk$")],
        states={
            ASK_BULK_GROUPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_groups_bulk_receive)],
        },
        fallbacks=[CommandHandler(admin_cmd, admin_panel)],
    )
    app.add_handler(conv)
