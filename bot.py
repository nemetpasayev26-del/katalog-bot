import os
import io
import requests
import google.generativeai as genai
import logging  # <-- Loqlama əlavə edildi
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# --- Loqlama Quraşdırılması ---
# Botun konsolunda hər bir addımı görmək üçün bu mütləqdir.
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- API Açarları (Sizin köhnə kod) ---
TOKEN = os.environ.get("BOT_TOKEN", "")
SEGMIND_API_KEY = os.environ.get("SEGMIND_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_FOLDER = "output"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

genai.configure(api_key=GEMINI_API_KEY)

# --- AI və Şəkil Emalı (Köhnə kod, timeout ilə) ---
def get_ai_product_info(category: str) -> str:
    logger.info(f"AI məlumatı istənilir: {category}")
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
    except Exception as e:
        logger.error(f"AI Xətası: {e}")
        return "• Məhsulun adı: \n• İstifadə sahəsi: \n• Məhsulun çəkisi: \n• İstehsalçı: "

def remove_background(img_bytes: bytes):
    logger.info("Segmind API ilə fon silinməsi istənilir...")
    try:
        # TIMEOUT mütləqdir ki, bot ilişib qalmasın.
        response = requests.post(
            "https://api.segmind.com/v1/bg-removal",
            files={"image": ("image.jpg", img_bytes, "image/jpeg")},
            headers={"x-api-key": SEGMIND_API_KEY},
            timeout=15  # 15 saniyə gözlə, sonra kəs
        )
        if response.status_code == 200:
            logger.info("Fon uğurla silindi.")
            return response.content
        else:
            logger.warning(f"Segmind Xətası: Status {response.status_code}, {response.text}")
    except Exception as e:
        logger.error(f"Segmind API Sorğu Xətası: {e}")
    return None

def enhance_image_quality(img):
    return ImageEnhance.Sharpness(img).enhance(1.5)

# --- Dəyişdirilmiş build_catalog_image (Öncəki addımdakı) ---
def build_catalog_image(images, texts, category, page_num):
    # ... (Mən sizə dünən verdiyim kodun eynisi) ...
    template_path = "template.png"
    if os.path.exists(template_path):
        canvas = Image.open(template_path).convert("RGB")
    else:
        canvas = Image.new("RGB", (1080, 1080), (255, 255, 255))
        logger.error(f"XƏTA: '{template_path}' tapılmadı!")

    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)
    try:
        font_title = ImageFont.truetype("arial.ttf", 28) 
        font_bullet = ImageFont.truetype("arial.ttf", 24) 
        font_footer = ImageFont.truetype("arial.ttf", 28) 
    except:
        font_title = font_bullet = font_footer = ImageFont.load_default()

    title_w = draw.textlength(category, font=font_title)
    draw.text(((W - title_w) / 2, 10), category, fill="white", font=font_title)
    footer_text = f"səhifə {page_num}"
    footer_w = draw.textlength(footer_text, font=font_footer)
    draw.text(((W - footer_w) / 2, 955), footer_text, fill="white", font=font_footer)

    num = len(images)
    col_w = W // num 
    img_top, img_bottom, text_top = 70, 680, 700
    bullet = "• "

    for i, img in enumerate(images):
        max_w, max_h = col_w - 40, (img_bottom - img_top) - 20
        orig_w, orig_h = img.size
        ratio = min(max_w / orig_w, max_h / orig_h)
        new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
        img_r = enhance_image_quality(img.resize((new_w, new_h), Image.Resampling.LANCZOS))
        x = col_w * i + (col_w - new_w) // 2
        y = img_top + ((img_bottom - img_top) - new_h) // 2
        canvas.paste(img_r, (x, y), img_r)

    line_height = 40
    for i, text in enumerate(texts):
        x_start, current_y = col_w * i + 40, text_top
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith("•"):
                draw.text((x_start, current_y), bullet, fill=(0,0,0), font=font_bullet)
                draw.text((x_start + 20, current_y), line[1:].strip(), fill=(0,0,0), font=font_bullet)
            else:
                draw.text((x_start, current_y), line, fill=(0,0,0), font=font_bullet)
            current_y += line_height

    output = io.BytesIO()
    canvas.save(output, format="PNG", quality=95)
    output.seek(0)
    return output

# ==============================================================================
# --- GÜCLƏNDİRİLMİŞ handle_photo funksiyası ---
# ==============================================================================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Mövcud vəziyyəti yoxla
    current_state = context.user_data.get('state')
    logger.info(f"Şəkil alındı. Mövcud vəziyyət: {current_state}")

    if current_state != 'wait_photo':
        logger.warning("Bot şəkil gözləmir, lakin şəkil göndərildi.")
        return

    idx = context.user_data.get('current_index', 0)
    total = context.user_data.get('total_count', 1)
    logger.info(f"Məhsul {idx + 1}/{total} emal olunur...")

    # İstifadəçiyə "gözlə" mesajı göndər
    msg = await update.message.reply_text(f"⏳ {idx + 1}-ci məhsulun şəkli emal edilir (fon silinir, keyfiyyət artırılır)...")

    product_img = None  # Emal olunacaq şəkil obyekti

    try:
        # 1. Şəkli Telegram-dan yüklə
        logger.info("Telegram-dan şəkil yüklənir...")
        photo = update.message.photo[-1]  # Ən böyük ölçülü şəkil
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        logger.info(f"Şəkil yükləndi ({len(img_bytes)} bayt).")

        # 2. Fonu Silməyə Çalış (Segmind API)
        result_bytes = remove_background(bytes(img_bytes))
        
        if result_bytes:
            logger.info("API ilə fon silindi, şəkil açılır...")
            product_img = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
        else:
            logger.warning("Fon silinmədi. Sadə ağ fon silmə metodu istifadə olunur...")
            # Əgər API xəta verərsə, sadə metodla davam et (bot dayanmasın)
            product_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            data = product_img.getdata()
            new_data = []
            for item in data:
                r, g, b, a = item
                # Sadə ağ fonu sil (r,g,b > 220)
                if r > 220 and g > 220 and b > 220:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            product_img.putdata(new_data)

        # 3. Şəkli Kəs (crop) - Boşluqları təmizlə
        bbox = product_img.getbbox()
        if bbox:
            product_img = product_img.crop(bbox)
            logger.info("Şəkil uğurla kəsildi.")

        # 4. Yaddaşa Yaz və Vəziyyəti Dəyiş
        context.user_data['images'].append(product_img)
        context.user_data['current_index'] = idx + 1
        
        # MÜTLƏQ: Vəziyyəti 'wait_ai_confirm' elə
        context.user_data['state'] = 'wait_ai_confirm'
        logger.info(f"Vəziyyət dəyişdirildi: {context.user_data['state']}")

        # "Gözlə" mesajını sil
        await msg.delete()

        # 5. AI-dan Məlumat İste
        category = context.user_data.get('category', 'Kataloq')
        ai_text = get_ai_product_info(category)
        context.user_data['ai_text'] = ai_text

        # Düymələri göstər
        keyboard = [["✅ Təsdiqlə", "✏️ Özüm yazacağam"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            f"📸 {idx + 1}-ci şəkil qəbul edildi!\n\n"
            f"🤖 AI-ın təklif etdiyi məlumat:\n\n"
            f"`{ai_text}`\n\n"
            f"Bu məlumatı təsdiqləyin və ya özünüz yazın:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    except Exception as e:
        # Hər hansı bir xəta baş verərsə, loqla və istifadəçiyə bildir
        logger.critical(f"HANDLE_PHOTO-DA KRİTİK XƏTA: {e}")
        if 'msg' in locals(): await msg.delete() # Mesajı silməyə çalış
        
        await update.message.reply_text(
            f"❌ Şəkil emal edilərkən xəta baş verdi.\n"
            f"Xəta: `{str(e)}`\n"
            f"Zəhmət olmasa yenidən yoxlayın və ya botu /start ilə müraciət edin.",
            parse_mode="Markdown"
        )
        # Xəta baş verdikdə vəziyyəti sıfırlamaq olar
        context.user_data['state'] = 'wait_photo' 

# ==================== Bot Məntiqi (Öncəki kodla eyni) ====================

async def next_photo_or_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data.get('current_index', 0)
    total = context.user_data.get('total_count', 1)
    if idx < total:
        context.user_data['state'] = 'wait_photo'
        await update.message.reply_text(f"📸 {idx + 1}-ci məhsulun şəklini göndərin:", reply_markup=ReplyKeyboardRemove())
    else:
        context.user_data['state'] = 'building'
        await update.message.reply_text("🎨 Kataloq yaradılır...", reply_markup=ReplyKeyboardRemove())
        try:
            output = build_catalog_image(context.user_data['images'], context.user_data['texts'], context.user_data.get('category', 'Kataloq'), context.user_data.get('page', '1'))
            await update.message.reply_photo(photo=output, caption="✅ Kataloqunuz hazırdır!")
        except Exception as e:
            await update.message.reply_text(f"❌ Kataloq xətası: {e}")
            logger.error(f"Build Xətası: {e}")
        finally:
            context.user_data.clear()

# ... (start və handle_text funksiyaları sizin köhnə kodla eynidir) ...
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['state'] = 'wait_category'
    await update.message.reply_text("🗂 Kataloq botuna xoş gəldiniz!\n\nKateqoriya adını yazın:", reply_markup=ReplyKeyboardRemove())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', '')
    text = update.message.text.strip()
    if state == 'wait_category':
        context.user_data['category'] = text
        context.user_data['state'] = 'wait_page'
        await update.message.reply_text(f"✅ Kateqoriya: *{text}*\n\nSəhifə nömrəsini yazın:", parse_mode="Markdown")
    elif state == 'wait_page':
        context.user_data['page'] = text
        context.user_data['state'] = 'wait_count'
        keyboard = [["2", "3", "4"]]
        await update.message.reply_text(f"✅ Səhifə: *{text}*\n\nNeçə məhsul olacaq?", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    elif state == 'wait_count':
        try:
            count = int(text)
            if count < 1 or count > 6: raise ValueError
        except ValueError:
            await update.message.reply_text("❌ 1-6 arasında rəqəm yazın.")
            return
        context.user_data['total_count'] = count
        context.user_data['images'], context.user_data['texts'], context.user_data['current_index'] = [], [], 0
        context.user_data['state'] = 'wait_photo'
        await update.message.reply_text(f"✅ {count} məhsul olacaq.\n\n📸 1-ci məhsulun şəklini göndərin:", reply_markup=ReplyKeyboardRemove())
    elif state == 'wait_ai_confirm':
        if text == "✅ Təsdiqlə":
            ai_text = context.user_data.get('ai_text', '')
            context.user_data['texts'].append(ai_text)
            await next_photo_or_build(update, context)
        elif text == "✏️ Özüm yazacağam":
            context.user_data['state'] = 'wait_manual_text'
            await update.message.reply_text("📝 Məhsul məlumatını yazın:", reply_markup=ReplyKeyboardRemove())
        else:
            context.user_data['texts'].append(text)
            await next_photo_or_build(update, context)
    elif state == 'wait_manual_text':
        context.user_data['texts'].append(text)
        await next_photo_or_build(update, context)

# ==================== MAIN ====================
if __name__ == '__main__':
    if not TOKEN:
        print("XƏTA: BOT_TOKEN tapılmadı!")
        exit(1)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot işə düşdü...")
    app.run_polling()
