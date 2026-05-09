import os
import io
import requests
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# --- API Açarları (Eyni qalır) ---
TOKEN = os.environ.get("BOT_TOKEN", "")
SEGMIND_API_KEY = os.environ.get("SEGMIND_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_FOLDER = "output"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

genai.configure(api_key=GEMINI_API_KEY)

# --- AI və Şəkil Emalı Funksiyaları (Eyni qalır) ---
def get_ai_product_info(category: str) -> str:
    # ... (Sizin mövcud kodunuz) ...
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
    # ... (Sizin mövcud kodunuz) ...
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

# ==============================================================================
# --- DƏYİŞDİRİLMİŞ FUNKSİYA: build_catalog_image ---
# ==============================================================================
def build_catalog_image(images, texts, category, page_num):
    """
    Sıfırdan çəkmək əvəzinə, hazır 'template.png' şablonunu yükləyir
    və məlumatları onun üzərinə yazır.
    """
    template_path = "template.png"
    
    # 1. Şablonu yükləyirik
    if os.path.exists(template_path):
        # Şablonu RGB rejimində açırıq (üzərinə yazmaq üçün)
        canvas = Image.open(template_path).convert("RGB")
    else:
        # Şablon tapılmasa, xəta verməmək üçün ağ fon yaradırıq (keçid variantı)
        canvas = Image.new("RGB", (1080, 1080), (255, 255, 255))
        print(f"XƏTA: '{template_path}' tapılmadı! Ağ fon istifadə olunur.")

    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)

    # 2. Şriftləri yükləyirik (Azərbaycan şrifti dəstəyi üçün)
    # Sizin kodunuzdakı yolları istifadə edə bilərsiniz, 
    # mən sadəlik üçün eyni qovluqdakı 'arial.ttf' istifadə edirəm.
    try:
        # Şrift yollarını öz sisteminizə uyğun tənzimləyin:
        # Məs: "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_path_bold = "arial.ttf" 
        font_path_reg = "arial.ttf"

        font_title = ImageFont.truetype(font_path_bold, 28) # Başlıq üçün
        font_bullet = ImageFont.truetype(font_path_reg, 24) # Əsas mətn üçün
        font_footer = ImageFont.truetype(font_path_bold, 28) # Səhifə nömrəsi üçün
    except:
        font_title = font_bullet = font_footer = ImageFont.load_default()
        print("XƏTA: Şriftlər yüklənmədi! Standart şrift istifadə olunur.")

    # Rənglər
    white = (255, 255, 255)
    black = (0, 0, 0)

    # --- Daimi Mətnlər (Başlıq və Səhifə) ---
    
    # Kateqoriya Başlığı: "Təmizlik vasitələri" (məsələn)
    # Şablondakı göy zolağın mərkəzi (Y ~ 10-15px)
    title_w = draw.textlength(category, font=font_title)
    draw.text(((W - title_w) / 2, 10), category, fill=white, font=font_title)

    # Səhifə nömrəsi: "səhifə 11"
    # Şablondakı aşağı göy zolağın mərkəzi (Y ~ 955px)
    footer_text = f"səhifə {page_num}"
    footer_w = draw.textlength(footer_text, font=font_footer)
    draw.text(((W - footer_w) / 2, 955), footer_text, fill=white, font=font_footer)

    # --- Dinamik Sahələrin Koordinatları ---
    # Bu koordinatlar şablonun ağ boşluqlarına uyğun hesablanıb.
    
    num = len(images)
    col_w = W // num # Sütun genişliyi (məs: 2 məhsul üçün 540px)
    
    # Məhsul şəkilləri üçün sahə
    img_top = 70      # Başlıqdan sonra başlasın
    img_bottom = 680  # Mətn sahəsinə qədər
    img_area_h = img_bottom - img_top

    # Məhsul mətnləri üçün sahə
    text_top = 700    # Şəkildən sonra başlasın
    bullet = "• "     # Bullet point simvolu

    # 3. Şəkilləri yerləşdiririk
    for i, img in enumerate(images):
        max_w = col_w - 40 # Kenarlardan boşluq
        max_h = img_area_h - 20
        orig_w, orig_h = img.size
        
        # Nisbəti qoruyaraq ölçünü dəyişirik
        ratio = min(max_w / orig_w, max_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        
        img_r = enhance_image_quality(img.resize((new_w, new_h), Image.Resampling.LANCZOS))
        
        # Mərkəzə düzürük
        x = col_w * i + (col_w - new_w) // 2
        y = img_top + (img_area_h - new_h) // 2
        
        # Şəkli şablonun üzərinə yapışdırırıq (alfa kanalı ilə)
        canvas.paste(img_r, (x, y), img_r)

    # 4. Mətnləri yerləşdiririk
    line_height = 40 # Sətirlər arası məsafə
    
    for i, text in enumerate(texts):
        x_start = col_w * i + 40 # Sol kenardan boşluq
        current_y = text_top
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Mətni şablonun üzərinə yazırıq
            # Sizin kodunuzdakı mürəkkəb bullet parsing məntiqini sadələşdirdim,
            # çünki AI artıq formatlanmış mətn verir.
            
            # Bullet point-i və mətni ayrı yazaq ki, səliqəli olsun
            if line.startswith("•"):
                draw.text((x_start, current_y), bullet, fill=black, font=font_bullet)
                draw.text((x_start + 20, current_y), line[1:].strip(), fill=black, font=font_bullet)
            else:
                draw.text((x_start, current_y), line, fill=black, font=font_bullet)
            
            current_y += line_height
            
            # Sahədən kənara çıxmamaq üçün yoxlama (opsional)
            if current_y > 940: break

    # 5. Nəticəni qaytarırıq
    output = io.BytesIO()
    canvas.save(output, format="PNG", quality=95)
    output.seek(0)
    return output

# ==============================================================================
# --- BOT MƏNTİQİ (Eyni qalır) ---
# ==============================================================================

async def next_photo_or_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sizin mövcud kodunuz) ...
    idx = context.user_data.get('current_index', 0)
    total = context.user_data.get('total_count', 1)

    if idx < total:
        context.user_data['state'] = 'wait_photo'
        await update.message.reply_text(
            f"📸 {idx + 1}-ci məhsulun şəklini göndərin:",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        context.user_data['state'] = 'building'
        await update.message.reply_text("🎨 Kataloq yaradılır...", reply_markup=ReplyKeyboardRemove())
        try:
            # Dəyişdirilmiş funksiya çağırılır
            output = build_catalog_image(
                context.user_data['images'],
                context.user_data['texts'],
                context.user_data.get('category', 'Kataloq'),
                context.user_data.get('page', '1')
            )
            await update.message.reply_photo(
                photo=output,
                caption="✅ Kataloqunuz hazırdır!"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Kataloq xətası: {e}")
        finally:
            context.user_data.clear()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sizin mövcud kodunuz) ...
    context.user_data.clear()
    context.user_data['state'] = 'wait_category'
    await update.message.reply_text(
        "🗂 Kataloq botuna xoş gəldiniz!\n\n"
        "Kateqoriya adını yazın (yuxarı başlıq üçün):\n"
        "Məs: *Təmizlik vasitələri*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sizin mövcud kodunuz) ...
    state = context.user_data.get('state', '')
    text = update.message.text.strip()

    if state == 'wait_category':
        context.user_data['category'] = text
        context.user_data['state'] = 'wait_page'
        await update.message.reply_text(
            f"✅ Kateqoriya: *{text}*\n\nSəhifə nömrəsini yazın:",
            parse_mode="Markdown"
        )

    elif state == 'wait_page':
        context.user_data['page'] = text
        context.user_data['state'] = 'wait_count'
        keyboard = [["2", "3", "4"]]
        await update.message.reply_text(
            f"✅ Səhifə: *{text}*\n\nNeçə məhsul olacaq?",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif state == 'wait_count':
        try:
            count = int(text)
            if count < 1 or count > 6:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ 1-6 arasında rəqəm yazın.")
            return
        context.user_data['total_count'] = count
        context.user_data['images'] = []
        context.user_data['texts'] = []
        context.user_data['current_index'] = 0
        context.user_data['state'] = 'wait_photo'
        await update.message.reply_text(
            f"✅ {count} məhsul olacaq.\n\n📸 1-ci məhsulun şəklini göndərin:",
            reply_markup=ReplyKeyboardRemove()
        )

    elif state == 'wait_ai_confirm':
        if text == "✅ Təsdiqlə":
            ai_text = context.user_data.get('ai_text', '')
            context.user_data['texts'].append(ai_text)
            await next_photo_or_build(update, context)
        elif text == "✏️ Özüm yazacağam":
            context.user_data['state'] = 'wait_manual_text'
            await update.message.reply_text(
                "📝 Məhsul məlumatını yazın:\n\n"
                "Məs:\n"
                "• Məhsulun adı: Asperox\n"
                "• İstifadə sahəsi: Mətbəx\n"
                "• Məhsulun çəkisi: 650 ml\n"
                "• İstehsalçı: Türkiyə",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            context.user_data['texts'].append(text)
            await next_photo_or_build(update, context)

    elif state == 'wait_manual_text':
        context.user_data['texts'].append(text)
        await next_photo_or_build(update, context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sizin mövcud kodunuz) ...
    if context.user_data.get('state') != 'wait_photo':
        return

    idx = context.user_data.get('current_index', 0)
    msg = await update.message.reply_text("⏳ Şəkil emal edilir...")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()

        result = remove_background(bytes(img_bytes))
        if result:
            product_img = Image.open(io.BytesIO(result)).convert("RGBA")
        else:
            product_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            data = product_img.getdata()
            new_data = []
            for item in data:
                r, g, b, a = item
                if r > 200 and g > 200 and b > 200:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            product_img.putdata(new_data)

        bbox = product_img.getbbox()
        if bbox:
            product_img = product_img.crop(bbox)

        context.user_data['images'].append(product_img)
        context.user_data['current_index'] = idx + 1
        context.user_data['state'] = 'wait_ai_confirm'

        await msg.delete()

        category = context.user_data.get('category', '')
        ai_text = get_ai_product_info(category)
        context.user_data['ai_text'] = ai_text

        keyboard = [["✅ Təsdiqlə", "✏️ Özüm yazacağam"]]
        await update.message.reply_text(
            f"📸 {idx + 1}-ci şəkil qəbul edildi!\n\n"
            f"🤖 AI təklif etdiyi məlumat:\n\n"
            f"`{ai_text}`\n\n"
            f"Təsdiqləyin və ya dəyişdirin:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    except Exception as e:
        if 'msg' in locals(): await msg.delete()
        await update.message.reply_text(f"❌ Xəta: {e}")

# ==================== MAIN (Eyni qalır) ====================

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot işə düşdü...")
    app.run_polling()
