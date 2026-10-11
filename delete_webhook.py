import asyncio
import logging
from bot import bot

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.info("Проверка статуса вебхука в Telegram...")
    try:
        info = await bot.get_webhook_info()
        logging.info(f"Текущий URL вебхука: '{info.url}'")
        logging.info(f"Ожидающих обновлений: {info.pending_update_count}")
        if info.last_error_message:
            logging.info(f"Последняя ошибка вебхука: {info.last_error_message}")
    except Exception as e:
        logging.error(f"Не удалось получить информацию о вебхуке: {e}")

    logging.info("Сброс вебхука (deleteWebhook)...")
    try:
        result = await bot.delete_webhook(drop_pending_updates=True)
        logging.info(f"Результат сброса вебхука: {result}")
        if result:
            logging.info("✅ Вебхук успешно удален! Теперь бот может запускаться в режиме polling.")
    except Exception as e:
        logging.error(f"Ошибка при сбросе вебхука: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
