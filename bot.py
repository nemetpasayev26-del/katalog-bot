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

import os
import io
import requests
import google.generativeai as genai
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# ... (Kodu digər hissələri: logging, API keys, AI funksiyaları eyni qalır) ...

# ==============================================================================
# --- TƏKMİLLƏŞDİRİLMİŞ FUNKSİYA: build_catalog_image ---
# ==============================================================================
def build_catalog_image(images, texts, category, page_num):
    """
    Hazır 'template.png' şablonunu yükləyir, şəkilləri avtomatik nizamlayıb
    bosluqlara mərkəzə yerləşdirir və mətnləri yazır.
    """
    logger.info("build_catalog_image başladı...")
    template_path = "template.png"
    
    # 1. Şablonu RGB rejimində yükləyirik
    if os.path.exists(template_path):
        canvas = Image.open(template_path).convert("RGB")
        logger.info("template.png yükləndi.")
    else:
        # Şablon tapılmasa, xəta verməmək üçün ağ fon yaradırıq (keçid variantı)
        canvas = Image.new("RGB", (1080, 1080), (255, 255, 255))
        logger.error(f"XƏTA: '{template_path}' tapılmadı! Ağ fon istifadə olunur.")

    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)

    # 2. Şriftləri yükləyirik (Sizin köhnə kodla eyni məntiq)
    # Şrift yollarını öz sisteminizə uyğun tənzimləyin:
    # Məs: "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font_path = "arial.ttf"  # Sisteminizdəki Azərbaycan şrifti yolu (.ttf)
        font_title = ImageFont.truetype(font_path, 28) 
        font_bullet = ImageFont.truetype(font_path, 24) 
        font_footer = ImageFont.truetype(font_path, 28) 
    except Exception as e:
        logger.error(f"Şrift yükləmə xətası: {e}. Standart şrift istifadə olunur.")
        font_title = font_bullet = font_footer = ImageFont.load_default()

    # --- Daimi Mətnlər (Köhnə kodla eyni) ---
    white = (255, 255, 255)
    
    # Kateqoriya Başlığı (Mərkəzə, Göy başlıq zolağına)
    title_w = draw.textlength(category, font=font_title)
    draw.text(((W - title_w) / 2, 10), category, fill=white, font=font_title)

    # Səhifə nömrəsi (Mərkəzə, Aşağı göy zolağa)
    footer_text = f"səhifə {page_num}"
    footer_w = draw.textlength(footer_text, font=font_footer)
    draw.text(((W - footer_w) / 2, 955), footer_text, fill=white, font=font_footer)

    # ==========================================================================
    # --- ŞƏKİLLƏRİN YERLƏŞDİRİLMƏSİ (Dəyişdirilmiş hissə) ---
    # ==========================================================================
    
    num_products = len(images)
    col_width = W // num_products
    
    # 3. Şablon üzərindəki məhsul şəkillərinin yerləşməli olduğu ağ boşluğun koordinatlarını təyin edirik
    # template.png-də şəkillər yuxarı göy başlıqdan sonra və 
    # aşağı mətn boşluğundan əvvəl yerləşməlidir.
    AREA_TOP = 70      # Yuxarı göy zolaqdan sonra
    AREA_BOTTOM = 680  # Aşağı mətn sahəsinə qədər
    AREA_HEIGHT = AREA_BOTTOM - AREA_TOP

    for i, img in enumerate(images):
        logger.info(f"Məhsul {i+1} şəkli nizamlanır...")
        
        # 4. Hər bir məhsul üçün sütun daxilində ağ boşluğun (rectangle) ölçüsünü tapırığ
        # Sütunun kənarlarından boşluq qoyuruq (padding), çərçivəyə yapışmasın.
        padding_x = 40 
        padding_y = 20
        
        # Boşluğun koordinatları (x1, y1, x2, y2)
        box_x1 = col_width * i + padding_x
        box_y1 = AREA_TOP + padding_y
        box_x2 = col_width * (i + 1) - padding_x
        box_y2 = AREA_BOTTOM - padding_y
        
        # Boşluğun daxili ölçüləri (bu ölçülərə sığışdırmalıyıq)
        max_box_w = box_x2 - box_x1
        max_box_h = box_y2 - box_y1
        
        orig_w, orig_h = img.size
        
        # 5. Şəklin ölçüsünü mütənasib şəkildə dəyişirik
        # Pillow-nun thumbnail() funksiyası nisbəti qoruyur və şəkli sığışdırır.
        
        img_copy = img.copy() # Orijinal şəkli qorumaq üçün kopya edirik
        img_copy.thumbnail((max_box_w, max_box_h), Image.Resampling.LANCZOS)
        
        # Nizamlanmış şəklin yeni ölçüləri
        new_w, new_h = img_copy.size
        logger.info(f"Orijinal: {orig_w}x{orig_h} -> Nizamlanmış: {new_w}x{new_h}")

        # 6. Nizamlanmış şəkli boşluğun tam mərkəzinə düzmək üçün koordinatları hesablayırıq
        # Şaquli və üfüqi mərkəz
        paste_x = box_x1 + (max_box_w - new_w) // 2
        paste_y = box_y1 + (max_box_h - new_h) // 2
        
        # Keyfiyyəti artırırıq (Sharpness)
        img_r = enhance_image_quality(img_copy)
        
        # 7. Şəkli şablonun üzərinə yapışdırırıq (alfa kanalı ilə şəffaflıq qorunur)
        canvas.paste(img_r, (paste_x, paste_y), img_r)

    # ==========================================================================
    # --- MƏTNLRİN YERLƏŞDİRİLMƏSİ (Köhnə kodla eyni) ---
    # ==========================================================================
    text_top = 700 
    black = (0, 0, 0)
    bullet = "• "
    line_height = 40
    
    for i, text in enumerate(texts):
        x_start = col_width * i + 40 
        current_y = text_top
        lines = text.strip().split("\n")
        
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith("•"):
                draw.text((x_start, current_y), bullet, fill=black, font=font_bullet)
                draw.text((x_start + 20, current_y), line[1:].strip(), fill=black, font=font_bullet)
            else:
                draw.text((x_start, current_y), line, fill=black, font=font_bullet)
            current_y += line_height

    # 8. Nəticəni qaytarırıq (RGB olaraq)
    output = io.BytesIO()
    canvas.save(output, format="PNG", quality=95)
    output.seek(0)
    logger.info("build_catalog_image bitdi.")
    return output

# ... (start, handle_photo, handle_text, next_photo_or_build eyni qalır) ...

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
