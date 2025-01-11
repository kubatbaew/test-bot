import asyncio
import datetime
import logging
import ssl
import sys
from os import getenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
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

SELF_SSL = False

# Path to webhook route, on which Telegram will send requests
WEBHOOK_PATH = "/" + getenv("PROJECT_NAME")

DOMAIN = getenv("DOMAIN_IP") if SELF_SSL else getenv("DOMAIN_NAME")
EXTERNAL_PORT = 8443

# Base URL for webhook will be used to generate webhook URL for Telegram,
# in this example it is used public DNS with HTTPS support
# BASE_WEBHOOK_URL = "https://aiogram.dev/"
BASE_WEBHOOK_URL = "https://" + DOMAIN + ":" + str(EXTERNAL_PORT)

if SELF_SSL:
    WEB_SERVER_HOST = DOMAIN
    WEB_SERVER_PORT = EXTERNAL_PORT
else:
    # Webserver settings
    # bind localhost only to prevent any external access
    WEB_SERVER_HOST = "127.0.0.1"
    # Port for incoming request from reverse proxy. Should be any available port
    WEB_SERVER_PORT = 8080

# Secret key to validate requests from Telegram (optional)
WEBHOOK_SECRET = "my-secret"

# ========= For self-signed certificate =======
# Path to SSL certificate and private key for self-signed certificate.
# WEBHOOK_SSL_CERT = "/path/to/cert.pem"
# WEBHOOK_SSL_PRIV = "/path/to/private.key"
if SELF_SSL:
    WEBHOOK_SSL_CERT = "../SSL/" + DOMAIN + ".self.crt"
    WEBHOOK_SSL_PRIV = "../SSL/" + DOMAIN + ".self.key"


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


async def on_startup(bot: Bot) -> None:
    if SELF_SSL:
        # In case when you have a self-signed SSL certificate, you need to send the certificate
        # itself to Telegram servers for validation purposes
        # (see https://core.telegram.org/bots/self-signed)
        # But if you have a valid SSL certificate, you SHOULD NOT send it to Telegram servers.
        await bot.set_webhook(
            f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}",
            certificate=FSInputFile(WEBHOOK_SSL_CERT),
            secret_token=WEBHOOK_SECRET,
        )
    else:
        await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}", secret_token=WEBHOOK_SECRET)


# === (Added) Register shutdown hook to initialize webhook ===
async def on_shutdown(bot: Bot) -> None:
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    # Remove webhook.
    await bot.delete_webhook()


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    # Create an instance of request handler,
    # aiogram has few implementations for different cases of usage
    # In this example we use SimpleRequestHandler which is designed to handle simple cases
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    # Register webhook handler on application
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Mount dispatcher startup and shutdown hooks to aiohttp application
    setup_application(app, dp, bot=bot)

    if SELF_SSL:  # ==== For self-signed certificate ====
        # Generate SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

        # And finally start webserver
        web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT, ssl_context=context)
    else:
        # And finally start webserver
        web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)
    

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    main()
