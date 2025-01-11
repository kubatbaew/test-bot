from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Как пользоваться ботом?", callback_data="get_info")],
        [InlineKeyboardButton(text="Узнать где мой товар", callback_data="get_data")],
        [InlineKeyboardButton(text="Адрес склада в Китае (скоро)", callback_data="get_my_id")]
    ]
)


keyboard_back = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="get_start")]
    ]
)