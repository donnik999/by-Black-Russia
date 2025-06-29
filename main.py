import os
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InputMediaPhoto, InputFile, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters import Text
from aiogram.utils.markdown import hbold

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("7220830808:AAE7R_edzGpvUNboGOthydsT9m81TIfiqzU")
ADMIN_ID = 6712617550  # <-- Замени на свой Telegram user_id!

# === БАЗА ДАННЫХ ===
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

# === КНОПКИ МЕНЮ ===
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton('🛒 Каталог объявлений'))
main_kb.add(KeyboardButton('➕ Добавить объявление'), KeyboardButton('📦 Мои объявления'))
main_kb.add(KeyboardButton('💬 Поддержка'), KeyboardButton('🌟 Спонсоры'))

type_kb = InlineKeyboardMarkup(row_width=2)
type_kb.add(
    InlineKeyboardButton("Продажа", callback_data="type_sell"),
    InlineKeyboardButton("Покупка", callback_data="type_buy")
)

cancel_kb = ReplyKeyboardMarkup(resize_keyboard=True).add('❌ Отмена')

# === СОСТОЯНИЯ ДЛЯ FSM ===
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

storage = MemoryStorage()

class AdForm(StatesGroup):
    type = State()
    title = State()
    description = State()
    photo = State()

# === ИНИЦИАЛИЗАЦИЯ БОТА ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)

# === ХЭЛПЕРЫ ДЛЯ БД ===
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

# === КОМАНДЫ И МЕНЮ ===

@dp.message_handler(commands=['start', 'menu'])
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        "Добро пожаловать в каталог объявлений Black Russia.\n\n"
        "Выберите действие из меню ниже 👇",
        reply_markup=main_kb
    )

@dp.message_handler(lambda m: m.text == '🛒 Каталог объявлений')
async def ads_catalog(message: types.Message):
    ads = get_all_ads()
    if not ads:
        await message.answer("Пока что нет объявлений.\nДобавьте первое!", reply_markup=main_kb)
        return
    for ad in ads[:10]:  # Показываем только 10 последних
        text = f"{hbold('Тип:')} {ad[3].capitalize()}\n{hbold('Заголовок:')} {ad[4]}\n{hbold('Описание:')} {ad[5]}\n{hbold('Автор:')} @{ad[2] if ad[2] else ad[1]}"
        kb = None
        if message.from_user.id == ADMIN_ID:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{ad[0]}"))
        if ad[6]:
            await message.answer_photo(ad[6], caption=text, reply_markup=kb or main_kb)
        else:
            await message.answer(text, reply_markup=kb or main_kb)

@dp.message_handler(lambda m: m.text == '➕ Добавить объявление')
async def add_ad_start(message: types.Message):
    await message.answer("Выберите тип объявления:", reply_markup=type_kb)
    await AdForm.type.set()

@dp.callback_query_handler(lambda c: c.data.startswith("type_"), state=AdForm.type)
async def ad_type_chosen(call: types.CallbackQuery, state: FSMContext):
    ad_type = call.data.replace("type_", "")
    await state.update_data(type=ad_type)
    await call.message.edit_text(f"Тип выбран: {('Покупка' if ad_type == 'buy' else 'Продажа')}\n\nВведите название товара:", reply_markup=None)
    await AdForm.title.set()

@dp.message_handler(state=AdForm.title)
async def ad_title_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("Добавление объявления отменено.", reply_markup=main_kb)
        return
    await state.update_data(title=message.text)
    await message.answer("Введите описание объявления (до 400 символов):", reply_markup=cancel_kb)
    await AdForm.description.set()

@dp.message_handler(state=AdForm.description)
async def ad_description_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("Добавление объявления отменено.", reply_markup=main_kb)
        return
    desc = message.text
    if len(desc) > 400:
        await message.answer("Слишком длинное описание, до 400 символов.")
        return
    await state.update_data(description=desc)
    await message.answer("Прикрепите фото товара (или отправьте '❌ Отмена', если без фото):", reply_markup=cancel_kb)
    await AdForm.photo.set()

@dp.message_handler(content_types=['photo'], state=AdForm.photo)
async def ad_photo_entered(message: types.Message, state: FSMContext):
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
    await state.finish()
    await message.answer("Объявление добавлено с фото! ✅", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == "❌ Отмена", state="*")
async def ad_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Добавление объявления отменено.", reply_markup=main_kb)

@dp.message_handler(content_types=['text'], state=AdForm.photo)
async def ad_no_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("Добавление объявления отменено.", reply_markup=main_kb)
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
    await state.finish()
    await message.answer("Объявление добавлено (без фото) ✅", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == '📦 Мои объявления')
async def my_ads(message: types.Message):
    ads = get_user_ads(message.from_user.id)
    if not ads:
        await message.answer("У вас пока нет объявлений.", reply_markup=main_kb)
        return
    for ad in ads:
        text = f"{hbold('Тип:')} {ad[1].capitalize()}\n{hbold('Заголовок:')} {ad[2]}\n{hbold('Описание:')} {ad[3]}"
        if ad[4]:
            await message.answer_photo(ad[4], caption=text, reply_markup=main_kb)
        else:
            await message.answer(text, reply_markup=main_kb)

# === УДАЛЕНИЕ ОБЪЯВЛЕНИЙ (ТОЛЬКО АДМИН) ===
@dp.callback_query_handler(lambda c: c.data.startswith("delete_"))
async def delete_ad_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Удалять объявления может только администратор.", show_alert=True)
        return
    ad_id = int(call.data.replace("delete_", ""))
    delete_ad(ad_id)
    await call.message.edit_caption("❌ Объявление удалено администратором.", reply_markup=None)
    await call.answer("Удалено.", show_alert=True)

# === ПОДДЕРЖКА, СПОНСОРЫ ===
@dp.message_handler(lambda m: m.text == '💬 Поддержка')
async def support(message: types.Message):
    await message.answer("По вопросам пишите: @bunkoc (замени на свой!)", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == '🌟 Спонсоры')
async def sponsors(message: types.Message):
    await message.answer("Спонсоры:\n1. Не имеются. , reply_markup=main_kb)

# === ОШИБКИ ===
@dp.errors_handler()
async def errors_handler(update, error):
    print(f"Ошибка: {error}")
    return True

# === СТАРТ БОТА ===
if __name__ == '__main__':
    print("Бот запущен!")
    executor.start_polling(dp, skip_updates=True)
