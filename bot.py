import os
import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)

# Загрузка переменных окружения из .env (с поддержкой как python-dotenv, так и прямого парсинга)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

def parse_id_list(var_name: str, default: list) -> list:
    val = os.getenv(var_name)
    if not val:
        return default
    parsed = []
    for part in val.split(","):
        cleaned = part.strip()
        if cleaned.lstrip("-").isdigit():
            parsed.append(int(cleaned))
    return parsed if parsed else default

# Конфигурация из переменных окружения или значения по умолчанию
BOT_TOKEN = os.getenv("BOT_TOKEN", "8939255575:AAHJtvufWwQ5xjDBd01bn21q7m2B6k3Ak3g").strip()
if not BOT_TOKEN:
    logging.critical("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не указан в .env или переменных окружения!")
    sys.exit(1)

# ID администраторов для выдачи варнов, репортов и спецкоманд
OWNER_ID = int(os.getenv("OWNER_ID", "5115391739"))
REPORT_RECEIVER_IDS = parse_id_list("REPORT_RECEIVER_IDS", [5115391739, 6737858010])
ALLOWED_ADMIN_IDS = parse_id_list("ALLOWED_ADMIN_IDS", [5115391739, 8302063926, 6737858010])
ALL_REPORTS_ADMIN_IDS = parse_id_list("ALL_REPORTS_ADMIN_IDS", [5115391739, 8302063926, 6737858010])

RULES_URL = os.getenv("RULES_URL", "https://t.me/zhiznkoto/19679").strip()
KICK_TIMEOUT = int(os.getenv("KICK_TIMEOUT", "600"))

# Поддержка прокси (если задан PROXY_URL)
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None
session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None

bot = Bot(
    token=BOT_TOKEN,
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
 
# Флаг состояния проверки (включена по умолчанию)
verification_enabled = True
 
# Базы данных
verified_users = set()
reports_db = {}
report_counter = 1
reputation_db = {}
 
# База данных выговоров: {user_id: {"role": "helper"/"sr_admin", "red": 0, "yellow": 0, "green": 0, "name": str}}
warns_db = {}
 
# Лимиты выговоров
ROLE_LIMITS = {
    "helper": {"red": 1, "yellow": 2, "green": 2, "name": "Хелпер"},
    "sr_admin": {"red": 3, "yellow": 4, "green": 5, "name": "Высшая администрация (4 ранг)"}
}
 
RESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False
)
 
ALLOWED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True
)
 
async def kick_user_if_not_verified(chat_id: int, user_id: int, welcome_message_id: int):
    await asyncio.sleep(KICK_TIMEOUT)
    if (chat_id, user_id) not in verified_users:
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            logging.info(f"Пользователь {user_id} не прошёл проверку за {KICK_TIMEOUT}с и был исключён.")
            await bot.delete_message(chat_id=chat_id, message_id=welcome_message_id)
        except Exception as e:
            logging.error(f"Не удалось исключить пользователя {user_id} по таймеру: {e}")
    else:
        verified_users.discard((chat_id, user_id))
 
@dp.message(Command("start", ignore_mention=True))
async def cmd_start(message: Message):
    if message.chat.type == "private":
        await message.answer(
            "<b>Привет! Я бот для защиты, модерации, репортов и варнов в чатах.\n\n"
            "Добавь меня в свою группу и выдай права администратора!</b>"
        )
 
@dp.message(Command("gethelp", ignore_mention=True))
async def cmd_help(message: Message):
    help_text = (
        "<b>Данный бот был создан в целях ознакомить новых участников "
        f'с <a href="{RULES_URL}">правилами чата</a>.\n\n'
        f'Ссылка на правила: {RULES_URL}\n'
        "Бот был создан пользователем @allbebacck\n\n"
        f'Если вы не уверены, что до конца знаете правила, можете пройти повторную поверку - <a href="{RULES_URL}">правила</a>\n\n'
        "<b>🚨 Система репортов:</b>\n"
        "• <code>/report</code> (или <code>/rep</code>) — отправить жалобу модерации (ответом на сообщение).\n"
        "• <code>/myreports</code> — просмотреть и управлять своими репортами.\n\n"
        "<b>⭐ Система репутации:</b>\n"
        "• <code>+реп [текст]</code> / <code>-реп [текст]</code> — изменить репутацию (ответом).\n"
        "• <code>/checkrep</code> — проверить репутацию.\n"
        "• <code>/resetrep</code> — обнулить репутацию.\n\n"
        "<b>⚠️ Система выговоров (для админов):</b>\n"
        "• <code>🔴 [текст]</code>, <code>🟡 [текст]</code>, <code>🟢 [текст]</code> — выдать выговор с примечанием (ответом).\n"
        "• <code>/checkwarn</code> — проверить выговоры.\n\n"
        "<b>📞 Связь с разработчиком:</b>\n"
        "• <code>/call [сообщение]</code> — написать разработчику (@allbebacck)."
    )
    await message.answer(help_text, disable_web_page_preview=True)
 
@dp.message(Command("upd", ignore_mention=True))
async def cmd_upd(message: Message):
    upd_text = (
        "⚙️ <b>Версия бота: 2.0</b>\n\n"
        "<b>Изменения:</b>\n"
        "• <b>Добавлены:</b> Полноценная система выговоров для администрации с автоконвертацией, лимитами и автоснятием при превышении красных варнов.\n"
        "• <b>Добавлены:</b> Команда <code>/call [текст]</code> для прямой связи с разработчиком (@allbebacck).\n"
        "• <b>Добавлены:</b> Система репутации участников (<code>+реп</code>/<code>-реп</code> с подписями, <code>/checkrep</code>).\n"
        "• <b>Добавлены:</b> Система репортов <code>/report</code> / <code>/rep</code> с кнопками решений и личным управлением <code>/myreports</code>.\n"
        "• <b>Изменены:</b> Секции помощи и проверки.\n\n"
        "<i>И были внесены мелкие незначительные изменения.</i>\n\n"
        "<b>Если вы хотите предложить какую либо идею касаемо этого бота, пишите в лс - @allbebacck</b>"
    )
    await message.answer(upd_text, disable_web_page_preview=True)
 
# Команда /call для связи с разработчиком
@dp.message(Command("call", ignore_mention=True))
async def cmd_call(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("⚠️ <b>Использование:</b> <code>/call [ваш текст]</code>")
        return
 
    text_to_dev = (
        "📞 <b>НОВОЕ ОБРАЩЕНИЕ ЧЕРЕЗ /call</b>\n\n"
        f"<b>От:</b> {message.from_user.full_name} (@{message.from_user.username or 'нет_юзернейма'}, ID: <code>{message.from_user.id}</code>)\n"
        f"<b>Чат:</b> {message.chat.title or 'Личные сообщения'}\n\n"
        f"<b>Сообщение:</b>\n{command.args}"
    )
 
    try:
        await bot.send_message(chat_id=OWNER_ID, text=text_to_dev)
        await message.reply("✅ <b>Ваше сообщение успешно отправлено разработчику (@allbebacck)!</b>")
    except Exception as e:
        logging.error(f"Не удалось отправить сообщение через /call: {e}")
        await message.reply("❌ Ошибка при отправке сообщения разработчику.")
 
# Команды управления проверкой (/on и /off)
@dp.message(Command("on", ignore_mention=True))
async def cmd_on(message: Message):
    global verification_enabled
    if message.from_user.id in ALLOWED_ADMIN_IDS:
        if verification_enabled:
            await message.answer("<b>Бот уже работает!</b>")
        else:
            verification_enabled = True
            await message.answer("✅ <b>Проверка правил при входе успешно ВКЛЮЧЕНА!</b>")
    else:
        await message.answer("❌ У вас нет прав для использования этой команды.")
 
@dp.message(Command("off", ignore_mention=True))
async def cmd_off(message: Message):
    global verification_enabled
    if message.from_user.id in ALLOWED_ADMIN_IDS:
        if not verification_enabled:
            await message.answer("<b>Бот уже выключен!</b>")
        else:
            verification_enabled = False
            await message.answer("⛔ <b>Проверка правил при входе успешно ОТКЛЮЧЕНА!</b>")
    else:
        await message.answer("❌ У вас нет прав для использования этой команды.")
 
# СИСТЕМА ВЫГОВОРОВ ДЛЯ АДМИНИСТРАЦИИ (🔴, 🟡, 🟢 с текстом)
@dp.message(F.text.regexp(r"^(🔴|🟡|🟢)\s*(.+)"))
async def handle_warns(message: Message):
    if message.from_user.id not in ALLOWED_ADMIN_IDS:
        return
 
    if not message.reply_to_message:
        await message.reply("⚠️ <b>Ответьте на сообщение администратора, чтобы выдать выговор!</b>")
        return
 
    target_user = message.reply_to_message.from_user
    target_id = target_user.id
    target_name = target_user.full_name
 
    text = message.text.strip()
    color_symbol = text[0]
    comment = text[1:].strip()
 
    if not comment:
        await message.reply("⚠️ <b>Текст выговора обязателен!</b> Пример: <code>🔴 - плохо себя ведет</code>")
        return
 
    color_map = {"🔴": "red", "🟡": "yellow", "🟢": "green"}
    color_key = color_map[color_symbol]
 
    if target_id not in warns_db:
        # По умолчанию определяем как helper (если не настроено иное), можно расширить при необходимости
        warns_db[target_id] = {"role": "helper", "red": 0, "yellow": 0, "green": 0, "name": target_name}
 
    user_data = warns_db[target_id]
    role = user_data["role"]
    limits = ROLE_LIMITS[role]
 
    # Добавляем варн
    user_data[color_key] += 1
    conversion_msg = ""
 
    # Конвертация зелёных в жёлтый
    if user_data["green"] >= limits["green"]:
        user_data["green"] = 0
        user_data["yellow"] += 1
        conversion_msg += "\n🔄 <b>Достигнут лимит зелёных выговоров! Конвертировано в 1 🟡 Жёлтый.</b>"
 
    # Конвертация жёлтых в красный
    if user_data["yellow"] >= limits["yellow"]:
        user_data["yellow"] = 0
        user_data["red"] += 1
        conversion_msg += "\n🔄 <b>Достигнут лимит жёлтых выговоров! Конвертировано в 1 🔴 Красный.</b>"
 
    # Проверка превышения красных лимитов (Снятие)
    is_fired = False
    if user_data["red"] > limits["red"]:
        is_fired = True
        conversion_msg += f"\n\n🚨 <b>Превышен лимит красных выговоров ({user_data['red']}/{limits['red']})!</b>\n⛔ <b>Автоматическое снятие с должности!</b>"
 
    reply_text = (
        f"⚠️ Администратор <b>{message.from_user.full_name}</b> выдал выговор {color_symbol} администратору <b>{target_name}</b>!\n"
        f"💬 <b>Причина:</b> {comment}\n\n"
        f"📊 <b>Текущие варны:</b>\n"
        f"🔴 Красные: {user_data['red']}/{limits['red']}\n"
        f"🟡 Жёлтые: {user_data['yellow']}/{limits['yellow']}\n"
        f"🟢 Зелёные: {user_data['green']}/{limits['green']}"
        f"{conversion_msg}"
    )
 
    await message.reply(reply_text)
 
    # Если хелпер получил больше лимита красных — кикаем из чата (авто-снятие)
    if is_fired and message.chat.type in ["group", "supergroup"]:
        try:
            await bot.ban_chat_member(chat_id=message.chat.id, user_id=target_id)
            await bot.unban_chat_member(chat_id=message.chat.id, user_id=target_id)
        except Exception as e:
            logging.error(f"Не удалось автоматически исключить снятого админа: {e}")
 
# Команда /checkwarn (только для админов)
@dp.message(Command("checkwarn", ignore_mention=True))
async def cmd_checkwarn(message: Message):
    if message.from_user.id not in ALLOWED_ADMIN_IDS:
        await message.reply("❌ <b>Эта команда доступна только администрации!</b>")
        return
 
    if not message.reply_to_message:
        await message.reply("⚠️ <b>Ответьте на сообщение администратора командой /checkwarn!</b>")
        return
 
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.full_name
 
    if target_id not in warns_db:
        await message.reply(f"🛡️ У администратора <b>{target_name}</b> нет активных выговоров.")
        return
 
    data = warns_db[target_id]
    limits = ROLE_LIMITS[data["role"]]
 
    text = (
        f"📊 <b>Выговоры администратора {target_name}:</b>\n"
        f"Должность: <b>{limits['name']}</b>\n\n"
        f"🔴 Красные: <b>{data['red']}</b> из {limits['red']}\n"
        f"🟡 Жёлтые: <b>{data['yellow']}</b> из {limits['yellow']}\n"
        f"🟢 Зелёные: <b>{data['green']}</b> из {limits['green']}"
    )
    await message.reply(text)
 
# Работа с репортами (/report и /rep)
@dp.message(Command("report", "rep", ignore_mention=True))
async def cmd_report(message: Message, command: CommandObject):
    global report_counter
 
    if not message.reply_to_message:
        await message.reply("⚠️ <b>Ответьте на сообщение нарушителя командой /report!</b>")
        return
 
    reason = command.args or "Без описания"
    reported_user = message.reply_to_message.from_user.full_name
    reported_text = message.reply_to_message.text or '[Медиафайл / Иное]'
 
    rep_text = f"Жалоба на {reported_user}. Причина: {reason}\nТекст сообщения: {reported_text}"
 
    rep_id = report_counter
    report_counter += 1
 
    reports_db[rep_id] = {
        "user_id": message.from_user.id,
        "user_name": message.from_user.full_name,
        "text": rep_text,
        "chat_title": message.chat.title or "ЛС",
        "status": "В обработке"
    }
 
    await message.reply("<b>Репорт доставлен модерации!</b>")
 
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принять ✅", callback_data=f"rep_accept_{rep_id}"),
            InlineKeyboardButton(text="Отклонить ❌", callback_data=f"rep_reject_{rep_id}")
        ]
    ])
 
    report_msg = (
        f"<b>🚨 НОВЫЙ РЕПОРТ #{rep_id}</b>\n"
        f"<b>От:</b> {message.from_user.full_name} (@{message.from_user.username})\n"
        f"<b>Чат:</b> {message.chat.title}\n\n"
        f"<b>Содержание:</b>\n{rep_text}"
    )
 
    for admin_id in REPORT_RECEIVER_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=report_msg, reply_markup=kb)
        except Exception as e:
            logging.error(f"Не удалось отправить репорт админу {admin_id}: {e}")
 
@dp.callback_query(F.data.startswith("rep_"))
async def process_report_decision(callback: CallbackQuery):
    parts = callback.data.split("_")
    action = parts[1]
    rep_id = int(parts[2])
 
    if rep_id not in reports_db:
        await callback.answer("Репорт не найден или уже обработан!", show_alert=True)
        return
 
    rep_data = reports_db[rep_id]
 
    if action == "accept":
        verdict_text = "Ваш репорт был принят! ✅"
        rep_data["status"] = "Принят ✅"
        await callback.message.edit_text(callback.message.text + "\n\n<b>ВЕРДИКТ: ПРИНЯТО ✅</b>")
    else:
        verdict_text = "Ваш репорт был отклонен! ❌"
        rep_data["status"] = "Отклонен ❌"
        await callback.message.edit_text(callback.message.text + "\n\n<b>ВЕРДИКТ: ОТКЛОНЕН ❌</b>")
 
    try:
        await bot.send_message(chat_id=rep_data["user_id"], text=f"<b>{verdict_text}</b>")
    except Exception as e:
        logging.error(f"Не удалось отправить статус репорта пользователю: {e}")
 
    await callback.answer("Решение отправлено пользователю!")
 
# Команда /myreports
@dp.message(Command("myreports", ignore_mention=True))
async def cmd_myreports(message: Message):
    user_id = message.from_user.id
    user_reps = {r_id: data for r_id, data in reports_db.items() if data["user_id"] == user_id}
 
    if not user_reps:
        await message.answer("<b>У вас нет активных или сохраненных репортов.</b>")
        return
 
    text = "<b>📋 Ваши репорты:</b>\n\n"
    buttons = []
 
    for r_id, data in user_reps.items():
        text += f"<b>Репорт #{r_id}</b> [{data['status']}]\nДетали: {data['text'][:50]}...\n\n"
        buttons.append([InlineKeyboardButton(text=f"🗑 Удалить репорт #{r_id}", callback_data=f"delrep_{r_id}")])
 
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb)
 
@dp.callback_query(F.data.startswith("delrep_"))
async def process_del_report(callback: CallbackQuery):
    rep_id = int(callback.data.split("_")[1])
    if rep_id in reports_db:
        del reports_db[rep_id]
        await callback.answer("Репорт успешно удален!", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("Репорт уже не существует.", show_alert=True)
 
# Команда /allreports
@dp.message(Command("allreports", ignore_mention=True))
async def cmd_allreports(message: Message):
    if message.from_user.id not in ALL_REPORTS_ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
 
    if not reports_db:
        await message.answer("<b>База репортов пуста!</b>")
        return
 
    text = "<b>🌐 Все репорты в системе:</b>\n\n"
    for r_id, data in reports_db.items():
        text += (
            f"<b># {r_id}</b> | От: {data['user_name']} | Чат: {data['chat_title']}\n"
            f"Статус: {data['status']}\n"
            f"Суть: {data['text']}\n"
            f"------------------------\n"
        )
 
    await message.answer(text)
 
# СИСТЕМА РЕПУТАЦИИ (+реп / -реп)
@dp.message(F.text.lower().startswith(("+реп", "-реп")))
async def handle_reputation(message: Message):
    if message.from_user.id not in ALLOWED_ADMIN_IDS:
        return
 
    if not message.reply_to_message:
        await message.reply("⚠️ <b>Ответьте на сообщение участника, чтобы изменить репутацию!</b>")
        return
 
    target_user = message.reply_to_message.from_user
    target_id = target_user.id
    target_name = target_user.full_name
 
    text_lower = message.text.lower()
    is_positive = text_lower.startswith("+реп")
 
    parts = message.text.split(maxsplit=1)
    comment = parts[1] if len(parts) > 1 else ""
 
    if target_id not in reputation_db:
        reputation_db[target_id] = {"score": 0, "name": target_name}
 
    if is_positive:
        reputation_db[target_id]["score"] += 1
        action_text = "повысил репутацию 🟢"
    else:
        reputation_db[target_id]["score"] -= 1
        action_text = "понизил репутацию 🔴"
 
    current_score = reputation_db[target_id]["score"]
 
    reply_msg = (
        f"⭐ Администратор <b>{message.from_user.full_name}</b> {action_text} участнику <b>{target_name}</b>!\n"
        f"📊 Текущая репутация: <b>{current_score}</b>"
    )
    if comment:
        reply_msg += f"\n💬 Примечание: <i>{comment}</i>"
 
    await message.reply(reply_msg)
 
# Проверка репутации (/checkrep)
@dp.message(Command("checkrep", ignore_mention=True))
async def cmd_checkrep(message: Message, command: CommandObject):
    target_user = message.from_user
 
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
 
    target_id = target_user.id
    score = reputation_db.get(target_id, {}).get("score", 0)
 
    await message.reply(f"📊 Репутация пользователя <b>{target_user.full_name}</b>: <b>{score}</b> ⭐")
 
# Обнуление репутации (/resetrep)
@dp.message(Command("resetrep", ignore_mention=True))
async def cmd_resetrep(message: Message):
    if message.from_user.id not in ALLOWED_ADMIN_IDS:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
 
    if not message.reply_to_message:
        await message.reply("⚠️ <b>Ответьте на сообщение участника, чтобы обнулить его репутацию!</b>")
        return
 
    target_user = message.reply_to_message.from_user
    target_id = target_user.id
 
    if target_id in reputation_db:
        reputation_db[target_id]["score"] = 0
 
    await message.reply(f"🔄 Репутация участника <b>{target_user.full_name}</b> успешно обнулена до <b>0</b>!")
 
@dp.message(Command("cstart", ignore_mention=True))
async def cmd_cstart(message: Message):
    if not verification_enabled:
        await message.answer("<b>Проверка правил сейчас отключена администрацией.</b>")
        return
 
    user = message.from_user
    if message.chat.type in ["group", "supergroup"]:
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                permissions=RESTRICTED_PERMISSIONS
            )
        except Exception as e:
            logging.error(f"Ошибка при тесте мута: {e}")
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я ознакомился(ась) с правилами ✅", callback_data=f"verify_{user.id}")]
    ])
 
    welcome_text = (
        f'<b>Привет, <a href="tg://user?id={user.id}">{user.full_name}</a>!\n\n'
        f'Пожалуйста, ознакомься <a href="{RULES_URL}">с правилами чата</a> и нажми на кнопку ниже, '
        f'чтобы получить возможность писать в чат.</b>'
    )
 
    sent_msg = await message.answer(welcome_text, reply_markup=keyboard, disable_web_page_preview=True)
    asyncio.create_task(kick_user_if_not_verified(message.chat.id, user.id, sent_msg.message_id))
 
@dp.message(F.new_chat_members)
async def new_chat_member(message: Message):
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Не удалось удалить системное сообщение: {e}")
 
    if not verification_enabled:
        return
 
    for member in message.new_chat_members:
        if member.is_bot:
            continue
 
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=member.id,
                permissions=RESTRICTED_PERMISSIONS
            )
        except Exception as e:
            logging.error(f"Ошибка при ограничении пользователя: {e}")
 
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я ознакомился(ась) с правилами ✅", callback_data=f"verify_{member.id}")]
        ])
 
        welcome_text = (
            f'<b>Привет, <a href="tg://user?id={member.id}">{member.full_name}</a>!\n\n'
            f'Пожалуйста, ознакомься <a href="{RULES_URL}">с правилами чата</a> и нажми на кнопку ниже, '
            f'чтобы получить возможность писать в чат.</b>'
        )
 
        sent_msg = await message.answer(welcome_text, reply_markup=keyboard, disable_web_page_preview=True)
        asyncio.create_task(kick_user_if_not_verified(message.chat.id, member.id, sent_msg.message_id))
 
@dp.callback_query(F.data.startswith("verify_"))
async def process_verify(callback: CallbackQuery):
    target_user_id = int(callback.data.split("_")[1])
 
    if callback.from_user.id != target_user_id:
        await callback.answer("Эта кнопка предназначена для нового участника!", show_alert=True)
        return
 
    try:
        if callback.message.chat.type in ["group", "supergroup"]:
            await bot.restrict_chat_member(
                chat_id=callback.message.chat.id,
                user_id=callback.from_user.id,
                permissions=ALLOWED_PERMISSIONS
            )
            verified_users.add((callback.message.chat.id, callback.from_user.id))
 
        await callback.answer("Права на отправку сообщений предоставлены!", show_alert=True)
        await callback.message.delete()
 
    except Exception as e:
        logging.error(f"Ошибка при снятии ограничений: {e}")
        await callback.answer("Не удалось снять ограничения. Проверь права бота!", show_alert=True)
 
async def start_health_check_server():
    """
    Запуск простого веб-сервера для health-check, если хостинг требует привязки к PORT (Render, Railway, Heroku и др.).
    Если переменная PORT не задана (VPS, обычный сервер), веб-сервер не запускается.
    """
    port_str = os.getenv("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
    except ValueError:
        return

    from aiohttp import web

    app = web.Application()

    async def health_handler(request):
        return web.Response(text="Bot is running!")

    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Health-check HTTP сервер запущен на порту {port}")

async def main():
    logging.info(">>> Инициализация и запуск бота версии 2.0... <<<")
    await start_health_check_server()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info(">>> БОТ ВЕРСИИ 2.0 УСПЕШНО ЗАПУЩЕН И ГОТОВ К РАБОТЕ <<<")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
