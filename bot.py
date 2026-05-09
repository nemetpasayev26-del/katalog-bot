import os
import io
import requests
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

TOKEN = os.environ.get("BOT_TOKEN", "")
SEGMIND_API_KEY = os.environ.get("SEGMIND_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_FOLDER = "output"
WATERMARK_TEXT = "sehrli_bazar"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

genai.configure(api_key=GEMINI_API_KEY)

def get_ai_product_info(category: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            f"Sən kataloq assistentisən. '{category}' kateqoriyasına aid tipik bir məhsul üçün "
            f"aşağıdakı formatda qısa məlumat yaz (Azərbaycan dilində):\n\n"
            f"• Məhsulun adı: ...\n"
            f"• İstifadə sahəsi: ...\n"
            f"• Məhsulun çəkisi: ...\n"
            f"• İstehsalçı: ...\n\n"
            f"Yalnız bu formatda yaz, əlavə mətn yazma."
        )
        return response.text.strip()
    except Exception:
        return (
            "• Məhsulun adı: \n"
            "• İstifadə sahəsi: \n"
            "• Məhsulun çəkisi: \n"
            "• İstehsalçı: "
        )

def remove_background(img_bytes: bytes):
    try:
        response = requests.post(
            "https://api.segmind.com/v1/bg-removal",
            files={"image": ("image.jpg", img_bytes, "image/jpeg")},
            headers={"x-api-key": SEGMIND_API_KEY},
            timeout=30
        )
        if response.status_code == 200:
            return response.content
    except Exception:
        pass
    return None

def enhance_image_quality(img):
    return ImageEnhance.Sharpness(img).enhance(1.5)

def build_catalog_image(images, texts, category, page_num):
    W, H = 1200, 1200
    canvas = Image.new("RGBA", (W, H), (245, 248, 252, 255))
    draw = ImageDraw.Draw(canvas)

    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_title = ImageFont.truetype(font_path, 52)
        font_header = ImageFont.truetype(font_path, 30)
        font_text = ImageFont.truetype(font_reg_path, 28)
        font_footer = ImageFont.truetype(font_path, 44)
        font_watermark = ImageFont.truetype(font_path, 90)
    except:
        font_title = font_header = font_text = font_footer = font_watermark = ImageFont.load_default()

    # Yuxarı başlıq
    draw.rectangle([(0, 0), (W, 85)], fill=(30, 60, 114))
    title_bbox = draw.textbbox((0, 0), category, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((W - title_w) / 2, 18), category, fill="white", font=font_title)

    # Watermark
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_layer)
    wm_bbox = wm_draw.textbbox((0, 0), WATERMARK_TEXT, font=font_watermark)
    wm_w = wm_bbox[2] - wm_bbox[0]
    wm_h = wm_bbox[3] - wm_bbox[1]
    wm_draw.text(((W - wm_w) / 2, (H - wm_h) / 2 - 60), WATERMARK_TEXT,
                 fill=(180, 200, 230, 55), font=font_watermark)
    canvas = Image.alpha_composite(canvas, wm_layer)
    draw = ImageDraw.Draw(canvas)

    # Şəkillər
    num = len(images)
    img_area_top = 95
    img_area_bottom = 620
    img_h = img_area_bottom - img_area_top
    col_w = W // num

    for i, img in enumerate(images):
        ratio = img_h / img.size[1]
        new_w = int(img.size[0] * ratio)
        if new_w > col_w - 20:
            new_w = col_w - 20
            ratio = new_w / img.size[0]
        new_h = int(img.size[1] * ratio)
        img_r = enhance_image_quality(img.resize((new_w, new_h), Image.Resampling.LANCZOS))
        x = col_w * i + (col_w - new_w) // 2
        y = img_area_top + (img_h - new_h) // 2
        canvas.p
