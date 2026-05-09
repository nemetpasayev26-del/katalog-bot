import os
import io
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

TOKEN = os.environ.get("BOT_TOKEN", "8601872497:AAGpW9QFiogUjQzrr_jSdWTMixgOgS5fL9Y")
SEGMIND_API_KEY = os.environ.get("SEGMIND_API_KEY", "")
OUTPUT_FOLDER = "output"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def remove_background(img_bytes):
    try:
        response = requests.post(
            "https://api.segmind.com/v1/bg-removal",
            files={"image": ("image.jpg", img_bytes, "image/jpeg")},
            headers={"x-api-key": SEGMIND_API_KEY},
            timeout=30
        )
        if response.status_code == 200:
            return response.content
        else:
            return None
    except Exception:
        return None

def enhance_image_quality(img):
    enhancer = ImageEnhance.Sharpness(img)
    return enhancer.enhance(1.5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['images'] = []
    context.user_data['text_info'] = ""
    await update.message.reply_text(
        "Salam! Kataloq botuna xoş gəldiniz.\n\n"
        "Zəhmət olmasa məhsulun şəklini göndərin."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'images' not in context.user_data:
        context.user_data['images'] = []

    msg = await update.message.reply_text("⏳ Şəkil emal edilir, zəhmət olmasa gözləyin...")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytearray = await file.download_as_bytearray()

        # Segmind ilə arxa fon silmə
        result = remove_background(bytes(img_bytearray))

        if result:
            product_img = Image.open(io.BytesIO(result)).convert("RGBA")
        else:
            # Segmind işləməsə sadə üsulla davam et
            product_img = Image.open(io.BytesIO(img_bytearray)).convert("RGBA")
            data = product_img.getdata()
            new_data = []
            for item in data:
                r, g, b, a = item
                if r > 200 and g > 200 and b > 200:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            product_img.putdata(new_data)

        # Boşluqların kəsilməsi
        bbox = product_img.getbbox()
        if bbox:
            product_img = product_img.crop(bbox)

        context.user_data['images'].append(product_img)

        shablon = (
            "Məhsul adi: \n"
            "istifade sahesi: \n"
            "Ölçü: \n"
            "Rəng: "
        )

        keyboard = [["✅ Kataloqu hazırla"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await msg.delete()
        await update.message.reply_text(
            f"📥 {len(context.user_data['images'])}-ci şəkil qəbul edildi.\n\n"
