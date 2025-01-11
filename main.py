import asyncio
import datetime
import logging
from os import getenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from keyboards import keyboard, keyboard_back
from decouple import config
from logics import get_data

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="bot.log",  # Логи будут записываться в этот файл
    filemode="a"  # Открытие файла в режиме добавления
)

logger = logging.getLogger(__name__)


PROJECT_NAME = getenv("PROJECT_NAME", "my_bot")
DOMAIN_NAME = getenv("DOMAIN_NAME", "example.com")
WEBHOOK_PATH = f"/{PROJECT_NAME}"
WEBHOOK_URL = f"https://{DOMAIN_NAME}{WEBHOOK_PATH}"

WEB_SERVER_HOST = "0.0.0.0"  # Подключение ко всем интерфейсам
WEB_SERVER_PORT = int(getenv("PORT", 8080))  


BOT_TOKEN = config("BOT_TOKEN")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class OrderState(StatesGroup):
    order_id = State()

@dp.message(CommandStart())
async def start(message: types.Message):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    await message.answer(
        "Вас приветствует Global Trade Bot! 👋🤖\nЧем я могу вам помочь?", 
        reply_markup=keyboard
    )

@dp.callback_query()
async def handle_callback(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Получен callback: {callback_query.data} от пользователя {callback_query.from_user.id}")
    if callback_query.data == "get_info":
        try:
            with open("desc.html", "r", encoding="utf-8") as file:
                content = file.read()
            await callback_query.message.answer(content)
            await callback_query.message.answer_video("BAACAgIAAxkBAAIBNmd5WL-Z0oCf9dyQXDIaRdAUeRmlAALNWwACEGzRS_p3atO1dX3KNgQ")
        except Exception as e:
            logger.error(f"Ошибка при обработке 'get_info': {e}", exc_info=True)
    elif callback_query.data == "get_data":
        await callback_query.message.answer(
            "Отлично, давайте я посмотрю где находится ваша посылка 🎉\n"
            "Вам нужно просто ввести трек код чтобы получить всю информацию о вашей посылки. ⬇️: "
        )
        await state.set_state(OrderState.order_id)
    elif callback_query.data == "get_start":
        await start(callback_query.message)
    elif callback_query.data == "get_my_id":
        await callback_query.message.answer("<b>Функция получение адреса в китае появиться скоро</b>", reply_markup=keyboard_back)

@dp.message(OrderState.order_id)
async def handle_order_id(message: types.Message, state: FSMContext):
    order_id = message.text
    logger.info(f"Получен трек-код от пользователя {message.from_user.id}: {order_id}")
    await state.clear()
    if order_id:
        loading_message = await message.answer(text="Ваш запрос принят⏳")
        try:
            data = get_data(order_id)
            await loading_message.delete()

            if data["data"]["data"]["wlOrder"] is None:
                await message.answer(
                    "Вы ввели неправильный трек код, это может быть из-за того, что: \n"
                    "1 - Ваша посылка еще не приехала к нам на склад \n"
                    "2 - Вы ввели некоректный трек код «Как посмотреть трек код вашего товара? "
                    "Вы можете посмотреть этот короткий видеоурок⬇️»"
                )
                await message.answer_video("BAACAgIAAxkBAAIBNmd5WL-Z0oCf9dyQXDIaRdAUeRmlAALNWwACEGzRS_p3atO1dX3KNgQ")
                return

            with open('send_data.html', "r", encoding="utf-8") as file:
                content = file.read().format(
                    data["data"]["data"]["wlOrder"]["waybillNumber"],
                    data["data"]["data"]["wlOrder"]["quantity"],
                )
                for dt in data["data"]["data"]["wlMessageList"][::-1]:
                    mess = dt["elsAddress"]
                    date = dt["dateTime"]
                    if "Код склада в Китае" in mess:
                        mess = "Посылка доставлена на наш склад в Китае и сейчас на этапе сортировки."
                    content += f"\n<b>Время: {date}</b>\n<b>Статус:</b> <i>{mess}</i>\n"
            
            await message.answer(text=content, reply_markup=keyboard_back)
        except Exception as e:
            logger.error(f"Ошибка при обработке трек-кода: {e}", exc_info=True)
            await message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")
    else:
        await message.answer(
            "Вы ввели неправильный трек код, это может быть из-за того, что: \n"
            "1 - Ваша посылка еще не приехала к нам на склад \n"
            "2 - Вы ввели некоректный трек код «Как посмотреть трек код вашего товара? "
            "Вы можете посмотреть этот короткий видеоурок⬇️»"
        )
        await message.answer_video("BAACAgIAAxkBAAIBNmd5WL-Z0oCf9dyQXDIaRdAUeRmlAALNWwACEGzRS_p3atO1dX3KNgQ")


async def on_startup(bot: Bot):
    """
    Установка вебхука при старте.
    """
    logger.info("Установка вебхука")
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(bot: Bot):
    """
    Удаление вебхука при остановке.
    """
    logger.info("Удаление вебхука")
    await bot.delete_webhook()


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Настройка приложения aiohttp
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info(f"Сервер запущен на {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)
    

if __name__ == "__main__":
    try:
        logger.info("Запуск бота")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка бота")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
