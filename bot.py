import logging
import asyncio
import os
import aiohttp

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, Update
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI, Request
from dotenv import load_dotenv

# 🔐 загружаем .env
load_dotenv()

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SELF_PING_URL = os.getenv("SELF_PING_URL")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
app = FastAPI()


# =========================
# 🧠 ПИЛИНГОВКА (антисон)
# =========================
async def self_ping():
    await asyncio.sleep(10)  # ждём запуск

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SELF_PING_URL) as resp:
                    logging.info(f"PING: {resp.status}")
        except Exception as e:
            logging.error(f"PING ERROR: {e}")

        await asyncio.sleep(300)  # каждые 5 минут


# =========================
# 📦 ВСПОМОГАТЕЛЬНОЕ
# =========================
def extract_media(msg: Message):
    if msg.photo:
        return "photo", msg.photo[-1].file_id
    if msg.video:
        return "video", msg.video.file_id
    if msg.document:
        return "document", msg.document.file_id
    if msg.voice:
        return "voice", msg.voice.file_id
    if msg.audio:
        return "audio", msg.audio.file_id
    if msg.animation:
        return "animation", msg.animation.file_id
    if msg.sticker:
        return "sticker", msg.sticker.file_id
    return None, None


# =========================
# 🤖 ЛОГИКА БОТА
# =========================
@dp.message()
async def catch_replies(message: Message):

    if not message.reply_to_message:
        return

    original_msg = message.reply_to_message
    author = original_msg.from_user
    replier = message.from_user

    if author.id == replier.id:
        return

    chat_id = message.chat.id
    msg_id = message.message_id

    fixed_chat_id = str(chat_id)[4:]
    link = f"https://t.me/c/{fixed_chat_id}/{msg_id}"

    orig_media_type, orig_file_id = extract_media(original_msg)
    reply_media_type, reply_file_id = extract_media(message)

    orig_text = original_msg.text or original_msg.caption
    reply_text = message.text or message.caption

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Перейти к ответу", url=link)]
        ]
    )

    try:
        header = "🔔 <b>Вам ответили в группе!</b>\n\n"
        await bot.send_message(author.id, header)

        if orig_media_type:
            await getattr(bot, f"send_{orig_media_type}")(
                author.id,
                orig_file_id,
                caption="📌 <b>Ваше сообщение:</b>" if orig_media_type != "sticker" else None
            )
        elif orig_text:
            await bot.send_message(author.id, f"📌 <b>Ваше сообщение:</b>\n{orig_text}")

        if reply_media_type:
            await getattr(bot, f"send_{reply_media_type}")(
                author.id,
                reply_file_id,
                caption=f"💬 <b>Ответ от:</b> {replier.full_name}" if reply_media_type != "sticker" else None
            )

        if reply_text:
            await bot.send_message(
                author.id,
                f"💬 <b>Ответ от:</b> {replier.full_name}\n{reply_text}",
                reply_markup=keyboard
            )
        else:
            await bot.send_message(author.id, "👇", reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")


# =========================
# 🌐 WEBHOOK
# =========================
@app.post("/")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/ping")
async def ping():
    return {"status": "alive 🚀"}


# =========================
# 🚀 СТАРТ
# =========================
@app.on_event("startup")
async def on_startup():
    logging.info("Запуск бота...")

    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info(f"Webhook установлен: {WEBHOOK_URL}")

    # 🔥 запускаем пилинговку
    asyncio.create_task(self_ping())


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
