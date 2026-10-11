import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)

BOT_TOKEN = '8939255575:AAHJtvufWwQ5xjDBd01bn21q7m2B6k3Ak3g'

# ID главного владельца для получения репортов в ЛС (@allbebacck)
OWNER_ID = 5115391739

# Список ID для команд /on и /off (@allbebacck и @allbebback)
ALLOWED_ADMIN_IDS = [5115391739, 8302063926]

# Список ID для команды /allreports (@allbebacck, @allbebback, @celerong4)
ALL_REPORTS_ADMIN_IDS = [5115391739, 8302063926, 6737858010]

# Прокси удален по запросу
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

RULES_URL = "https://t.me"
KICK_TIMEOUT = 600  # 10 минут

# Флаг состояния проверки (включена по умолчанию)
verification_enabled = True

# Хранилище данных
verified_users = set()
# База данных репортов: {report_id: {"user_id": int, "user_name": str, "text": str, "chat_title": str, "status": str}}
reports_db = {}
report_counter = 1

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
            "<b>Привет! Я бот для защиты, модерации и репортов в чатах.\n\n"
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
        "• <code>/report</code> (или <code>/rep</code>) — отправить жалобу модерации (строго ответом на сообщение нарушителя!).\n"
        "• <code>/myreports</code> — просмотреть и управлять своими репортами.</b>"
    )
    await message.answer(help_text, disable_web_page_preview=True)

@dp.message(Command("upd", ignore_mention=True))
async def cmd_upd(message: Message):
    upd_text = (
        "⚙️ <b>Версия бота: 1.5</b>\n\n"
        "<b>Изменения:</b>\n"
        "• <b>Добавлены:</b> Полноценная система репортов <code>/report</code> (и синоним <code>/rep</code>) с отправкой администрации, кнопками вердикта и личным меню <code>/myreports</code>.\n"
        "• <b>Добавлены:</b> Команды <code>/on</code> и <code>/off</code> для включения/выключения системы приветствия и проверки правил администрацией.\n"
        "• <b>Добавлены:</b> Команда <code>/allreports</code> для просмотра абсолютно всех активных жалоб авторизованными админами.\n"
        "• <b>Изменены:</b> Секция помощи <code>/gethelp</code> пополнена инструкциями по жалобе.\n\n"
        "<i>И были внесены мелкие незначительные изменения.</i>\n\n"
        "<b>Если вы хотите предложить какую либо идею касаемо этого бота, пишите в лс - @allbebacck</b>"
    )
    await message.answer(upd_text, disable_web_page_preview=True)

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

# Работа с репортами (/report и /rep)
@dp.message(Command("report", "rep", ignore_mention=True))
async def cmd_report(message: Message, command: CommandObject):
    global report_counter
    
    # Проверяем, ответил ли пользователь на сообщение нарушителя
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

    # Отправка администратору в ЛС
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принять ✅", callback_data=f"rep_accept_{rep_id}"),
            InlineKeyboardButton(text="Отклонить ❌", callback_data=f"rep_reject_{rep_id}")
        ]
    ])
    
    try:
        await bot.send_message(
            chat_id=OWNER_ID,
            text=f"<b>🚨 НОВЫЙ РЕПОРТ #{rep_id}</b>\n"
                 f"<b>От:</b> {message.from_user.full_name} (@{message.from_user.username})\n"
                 f"<b>Чат:</b> {message.chat.title}\n\n"
                 f"<b>Содержание:</b>\n{rep_text}",
            reply_markup=kb
        )
    except Exception as e:
        logging.error(f"Не удалось отправить репорт администратору в ЛС: {e}")

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

    # Уведомляем пользователя
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

async def main():
    print(">>> БОТ ВЕРСИИ 1.5 УСПЕШНО ЗАПУЩЕН И ГОТОВ К РАБОТЕ <<<")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())