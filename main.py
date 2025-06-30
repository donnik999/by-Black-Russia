import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.bot import DefaultBotProperties

# === ВСТАВЬ СЮДА СВОЙ ТОКЕН и TELEGRAM ID ===
BOT_TOKEN = "7220830808:AAE7R_edzGpvUNboGOthydsT9m81TIfiqzU"
ADMIN_ID = 6712617550  # <-- Твой Telegram user_id

DB_NAME = "br_catalog.db"

def db_init():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            type TEXT,
            title TEXT,
            description TEXT,
            photo_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

db_init()

class AdForm(StatesGroup):
    type = State()
    title = State()
    description = State()
    photo = State()

def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🛒 Каталог объявлений')],
            [KeyboardButton(text='➕ Добавить объявление')],
            [KeyboardButton(text='📦 Мои объявления')],
            [KeyboardButton(text='💬 Поддержка')],
            [KeyboardButton(text='🌟 Спонсоры')]
        ],
        resize_keyboard=True
    )

def get_cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='❌ Отмена')]],
        resize_keyboard=True
    )

def get_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продажа", callback_data="type_sell"),
         InlineKeyboardButton(text="Покупка", callback_data="type_buy")]
    ])

def get_delete_kb(ad_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{ad_id}")]
    ])

def add_ad(user_id, username, ad_type, title, desc, photo_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO ads (user_id, username, type, title, description, photo_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, ad_type, title, desc, photo_id))
    conn.commit()
    conn.close()

def get_all_ads():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, user_id, username, type, title, description, photo_id, created_at FROM ads ORDER BY id DESC')
    ads = c.fetchall()
    conn.close()
    return ads

def get_user_ads(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, type, title, description, photo_id, created_at FROM ads WHERE user_id=? ORDER BY id DESC', (user_id,))
    ads = c.fetchall()
    conn.close()
    return ads

def delete_ad(ad_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM ads WHERE id=?', (ad_id,))
    conn.commit()
    conn.close()

def get_ad(ad_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, user_id, username, type, title, description, photo_id, created_at FROM ads WHERE id=?', (ad_id,))
    ad = c.fetchone()
    conn.close()
    return ad

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        "Добро пожаловать в каталог объявлений Black Russia.\n\n"
        "Выберите действие из меню ниже 👇",
        reply_markup=get_main_kb()
    )

@dp.message(F.text == "🛒 Каталог объявлений")
async def ads_catalog(message: Message):
    ads = get_all_ads()
    if not ads:
        await message.answer("Пока что нет объявлений.\nДобавьте первое!", reply_markup=get_main_kb())
        return
    for ad in ads[:10]:
        text = f"<b>Тип:</b> {ad[3].capitalize()}\n<b>Заголовок:</b> {ad[4]}\n<b>Описание:</b> {ad[5]}\n<b>Автор:</b> @{ad[2] if ad[2] else ad[1]}"
        kb = None
        if message.from_user.id == ADMIN_ID:
            kb = get_delete_kb(ad[0])
        if ad[6]:
            await message.answer_photo(ad[6], caption=text, reply_markup=kb or get_main_kb())
        else:
            await message.answer(text, reply_markup=kb or get_main_kb())

@dp.message(F.text == "➕ Добавить объявление")
async def add_ad_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите тип объявления:", reply_markup=get_type_kb())
    await state.set_state(AdForm.type)

@dp.callback_query(F.data.startswith("type_"), StateFilter(AdForm.type))
async def ad_type_chosen(call: CallbackQuery, state: FSMContext):
    ad_type = call.data.replace("type_", "")
    await state.update_data(type=ad_type)
    await call.message.edit_text(f"Тип выбран: {'Покупка' if ad_type == 'buy' else 'Продажа'}\n\nВведите название товара:")
    await state.set_state(AdForm.title)

@dp.message(StateFilter(AdForm.title))
async def ad_title_entered(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление объявления отменено.", reply_markup=get_main_kb())
        return
    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления (до 400 символов):", reply_markup=get_cancel_kb())
    await state.set_state(AdForm.description)

@dp.message(StateFilter(AdForm.description))
async def ad_description_entered(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление объявления отменено.", reply_markup=get_main_kb())
        return
    desc = message.text
    if len(desc) > 400:
        await message.answer("Слишком длинное описание, до 400 символов.")
        return
    await state.update_data(description=desc)
    await message.answer("Прикрепите фото товара (или отправьте '❌ Отмена', если без фото):", reply_markup=get_cancel_kb())
    await state.set_state(AdForm.photo)

@dp.message(StateFilter(AdForm.photo), F.photo)
async def ad_photo_entered(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    add_ad(
        user_id=message.from_user.id,
        username=message.from_user.username,
        ad_type=data['type'],
        title=data['title'],
        desc=data['description'],
        photo_id=photo_id
    )
    await state.clear()
    await message.answer("Объявление добавлено с фото! ✅", reply_markup=get_main_kb())

@dp.message(StateFilter(AdForm.photo), F.text)
async def ad_no_photo(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление объявления отменено.", reply_markup=get_main_kb())
        return
    data = await state.get_data()
    add_ad(
        user_id=message.from_user.id,
        username=message.from_user.username,
        ad_type=data['type'],
        title=data['title'],
        desc=data['description'],
        photo_id=None
    )
    await state.clear()
    await message.answer("Объявление добавлено (без фото) ✅", reply_markup=get_main_kb())

@dp.message(F.text == "📦 Мои объявления")
async def my_ads(message: Message):
    ads = get_user_ads(message.from_user.id)
    if not ads:
        await message.answer("У вас пока нет объявлений.", reply_markup=get_main_kb())
        return
    for ad in ads:
        text = f"<b>Тип:</b> {ad[1].capitalize()}\n<b>Заголовок:</b> {ad[2]}\n<b>Описание:</b> {ad[3]}"
        if ad[4]:
            await message.answer_photo(ad[4], caption=text, reply_markup=get_main_kb())
        else:
            await message.answer(text, reply_markup=get_main_kb())

@dp.callback_query(F.data.startswith("delete_"))
async def delete_ad_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Удалять объявления может только администратор.", show_alert=True)
        return
    ad_id = int(call.data.replace("delete_", ""))
    delete_ad(ad_id)
    try:
        await call.message.edit_caption("❌ Объявление удалено администратором.", reply_markup=None)
    except:
        await call.message.edit_text("❌ Объявление удалено администратором.", reply_markup=None)
    await call.answer("Удалено.", show_alert=True)

@dp.message(F.text == "💬 Поддержка")
async def support(message: Message):
    await message.answer("По вопросам пишите: @YourSupportUsername (замени на свой!)", reply_markup=get_main_kb())

@dp.message(F.text == "🌟 Спонсоры")
async def sponsors(message: Message):
    await message.answer("Спонсоры:\n1. Amvera Hosting — https://amvera.io\n2. Ваш ник/группа здесь!", reply_markup=get_main_kb())

@dp.message(StateFilter("*"), F.text == "❌ Отмена")
async def ad_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Добавление объявления отменено.", reply_markup=get_main_kb())

@dp.message()
async def fallback(message: Message):
    await message.answer("Пожалуйста, используйте кнопки для управления ботом.", reply_markup=get_main_kb())

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
