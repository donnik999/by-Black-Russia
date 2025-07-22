import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import ReplyKeyboardBuilder

API_TOKEN = "8103024260:AAGPQ2IM_2R07URDGzRRiva59yCllGFCAM8"
ADMIN_ID = 8139725273  # <-- сюда ваш Telegram user id

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

STORAGE_PATH = "info_media"
os.makedirs(STORAGE_PATH, exist_ok=True)

info_data = {
    "photos": [],  # list of file paths
    "text": ""
}
user_cooldowns = {}  # user_id: timestamp, когда можно снова получить информацию
COOLDOWN_SECONDS = 300  # 5 минут

def get_keyboard(is_admin=False):
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Получить информацию"))
    if is_admin:
        kb.add(KeyboardButton(text="Загрузить информацию"))
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    is_admin = message.from_user.id == ADMIN_ID
    text = (
        "Добро пожаловать, этот бот создан для получения информации о пользователе @adceu (Yanx), "
        "нажмите кнопку ниже для получения информации"
    )
    await message.answer(text, reply_markup=get_keyboard(is_admin))

@dp.message(F.text == "Загрузить информацию")
async def upload_info(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта функция только для администратора.")
        return
    info_data["photos"].clear()
    info_data["text"] = ""
    await message.answer("Отправьте фотографии (по одной или сразу несколько, альбомом), затем напишите текст. Когда завершите — отправьте текст, он будет сохранён как описание. Для отмены отправьте /cancel.")

    # Ждём медиа и текст
    @dp.message(F.photo)
    async def save_photo(msg: types.Message):
        # Сохраняем все фото из сообщения (альбом или одиночное)
        for photo in msg.photo[-1:]:  # самое большое фото
            file = await bot.get_file(photo.file_id)
            ext = ".jpg"
            filename = f"{STORAGE_PATH}/{photo.file_unique_id}{ext}"
            await bot.download_file(file.file_path, filename)
            info_data["photos"].append(filename)
        await msg.answer("Фото добавлено. Добавьте ещё или отправьте текст.")

    @dp.message(F.media_group_id)
    async def save_album(msg: types.Message):
        # Обработка альбома (несколько фото в одном медиа-группе)
        for photo in msg.photo:
            file = await bot.get_file(photo.file_id)
            ext = ".jpg"
            filename = f"{STORAGE_PATH}/{photo.file_unique_id}{ext}"
            await bot.download_file(file.file_path, filename)
            info_data["photos"].append(filename)
        # Сообщение одно на всю группу не отправляем

    @dp.message(F.text & ~F.text.lower().startswith("/"))
    async def save_text(msg: types.Message):
        info_data["text"] = msg.text
        await msg.answer("Информация (фото и текст) успешно обновлена.", reply_markup=get_keyboard(True))
        dp.message.unregister(save_photo)
        dp.message.unregister(save_album)
        dp.message.unregister(save_text)

@dp.message(F.text == "Получить информацию")
async def get_info(message: types.Message):
    user_id = message.from_user.id
    now = asyncio.get_event_loop().time()
    allowed_time = user_cooldowns.get(user_id, 0)
    if now < allowed_time:
        remaining = int(allowed_time - now)
        await message.answer(f"Пожалуйста, подождите {remaining} сек. перед повторным запросом.")
        return
    if not info_data["text"] and not info_data["photos"]:
        await message.answer("Информация пока не загружена.")
        return

    media = []
    for img_path in info_data["photos"]:
        if os.path.exists(img_path):
            media.append(InputMediaPhoto(media=open(img_path, "rb")))
    sent_msgs = []

    if media:
        if info_data["text"]:
            media[0].caption = info_data["text"]
        # Отправляем как альбом
        msgs = await bot.send_media_group(chat_id=message.chat.id, media=media)
        sent_msgs.extend(msgs)
    elif info_data["text"]:
        msg = await message.answer(info_data["text"])
        sent_msgs.append(msg)

    user_cooldowns[user_id] = now + COOLDOWN_SECONDS

    async def delete_msgs(msgs):
        await asyncio.sleep(COOLDOWN_SECONDS)
        for msg in msgs:
            try:
                await bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
            except Exception:
                pass

    asyncio.create_task(delete_msgs(sent_msgs))

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
