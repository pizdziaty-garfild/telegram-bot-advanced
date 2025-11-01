import logging
from typing import Iterable
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

from sqlalchemy import text

from bot.core.enhanced_rbac_manager import EnhancedRBACManager
from config.settings import Settings
from bot.services.groups_service import GroupsService

logger = logging.getLogger(__name__)


def _normalize_id_set(values: Iterable) -> set[int]:
    out: set[int] = set()
    if values is None:
        return out
    if isinstance(values, (str, bytes)):
        raw = str(values)
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    else:
        parts = list(values)
    for p in parts:
        try:
            out.add(int(str(p).strip()))
        except Exception:
            pass
    return out


def setup_admin_handlers(app: Application, command_bus, settings: Settings) -> None:
    admin_cmd = getattr(settings, "admin_command_alias", "pusher")
    owner_ids = _normalize_id_set(getattr(settings, "owner_users", []))
    admin_ids = _normalize_id_set(getattr(settings, "admin_users", []))
    logger.info(f"Registering admin handlers with alias: /{admin_cmd}; owners={owner_ids}, admins={admin_ids}")

    async def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        uid = update.effective_user.id if update.effective_user else None
        if not uid:
            logger.debug("ensure_admin: missing effective_user.id")
            return False
        try:
            allowed = await command_bus.rbac.is_admin(uid)
            logger.debug(f"ensure_admin: rbac.is_admin({uid}) = {allowed}")
            if allowed:
                return True
        except Exception as e:
            logger.debug(f"ensure_admin: rbac failed ({e})")
        env_allow = (uid in owner_ids) or (uid in admin_ids)
        logger.debug(f"ensure_admin: env fallback for {uid} = {env_allow}")
        return env_allow

    async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"admin_panel called by user {update.effective_user.id if update.effective_user else None}")
        if not await ensure_admin(update, context):
            logger.warning("admin_panel: access denied")
            return
        kb = [
            [InlineKeyboardButton("Set Info", callback_data="set_info"), InlineKeyboardButton("Set Kontakt", callback_data="set_kontakt")],
            [InlineKeyboardButton("Time", callback_data="time"), InlineKeyboardButton("Ex-Time", callback_data="ex_time")],
            [InlineKeyboardButton("Groups", callback_data="groups"), InlineKeyboardButton("Status", callback_data="admin_status")],
        ]
        await update.effective_chat.send_message("Admin Panel", reply_markup=InlineKeyboardMarkup(kb))

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"status called by user {update.effective_user.id if update.effective_user else None}")
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
            [InlineKeyboardButton("Back", callback_data="back_to_main")],
        ]
        await update.effective_chat.send_message("Groups Menu", reply_markup=InlineKeyboardMarkup(kb))

    async def groups_list_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return
        svc = GroupsService(command_bus.database)
        page = await svc.list_groups(page=1, per_page=50)
        if not page.groups:
            await update.effective_chat.send_message("Brak grup w bazie.")
            return
        lines = [f"{g.telegram_id}: {g.title}" for g in page.groups]
        await update.effective_chat.send_message("Lista grup:\n" + "\n".join(lines))

    async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await ensure_admin(update, context):
            return
        query = update.callback_query
        data = query.data if query else ""
        logger.debug(f"Admin callback received: {data}")
        await query.answer()
        
        if data == "groups":
            await on_groups_menu(update, context)
        elif data == "groups_list":
            await groups_list_action(update, context)
        elif data == "groups_add":
            context.user_data['awaiting'] = 'groups_add'
            await update.effective_chat.send_message("Podaj identyfikator grupy (chat_id lub @username)")
        elif data == "groups_bulk":
            context.user_data['awaiting'] = 'groups_bulk'
            await update.effective_chat.send_message("Wklej listę grup (każda linia = chat_id lub @username)")
        elif data == "groups_del":
            context.user_data['awaiting'] = 'groups_del'
            await update.effective_chat.send_message("Podaj ID (z listy) do usunięcia (liczba)")
        elif data == "set_info":
            context.user_data['awaiting'] = 'set_info'
            await update.effective_chat.send_message("Wklej treść INFO (zastąpi obecną)")
        elif data == "set_kontakt":
            context.user_data['awaiting'] = 'set_kontakt'
            await update.effective_chat.send_message("Wklej treść KONTAKT (zastąpi obecną)")
        elif data == "time":
            context.user_data['awaiting'] = 'set_time'
            await update.effective_chat.send_message("Podaj globalny interwał w minutach (liczba > 0)")
        elif data == "ex_time":
            context.user_data['awaiting'] = 'set_ex_time'
            await update.effective_chat.send_message("Podaj interwał Ex-Time (minuty > 0)")
        elif data == "admin_status":
            await status(update, context)
        elif data == "back_to_main":
            await admin_panel(update, context)
        else:
            await update.effective_chat.send_message(f"Nieznana akcja: {data}")

    # Register handlers: callback first, then commands
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(CommandHandler(admin_cmd, admin_panel))
    app.add_handler(CommandHandler("status", status))

    logger.info(f"Admin handlers registered: /{admin_cmd}, /status, callbacks (simplified flow)")
