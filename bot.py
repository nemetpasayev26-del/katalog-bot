import os
import io
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import anthropic

TOKEN = os.environ.get("BOT_TOKEN", "")
SEGMIND_API_KEY = os.environ.get("SEGMIND_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OUTPUT_FOLDER = "output"
WATERMARK_TEXT = "sehrli_bazar"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- AI məhsul məlumatı ---
def get_ai_product_info(category: str) -> str:
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"Sən kataloq assistentisən. '{category}' kateqoriyasına aid tipik bir məhsul üçün "
                    f"aşağıdakı formatda qısa məlumat yaz (Azərbaycan dilində):\n\n"
                    f"• Məhsulun adı: ...\n"
                    f"• İstifadə sahəsi: ...\n"
                    f"• Məhsulun çəkisi: ...\n"
                    f"• İstehsalçı: ...\n\n"
                    f"Yalnız bu formatda yaz, əlavə mətn yazma."
                )
            }]
        )
        return message.content[0].text
    except Exception as e:
        return (
            f"• Məhsulun adı: \n"
            f"• İstifadə sahəsi: \n"
            f"• Məhsulun çəkisi: \n"
            f"• İstehsalçı: "
        )

# --- Arxa fon silmə ---
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

# --- Kataloq qurma ---
def build_catalog_image(images, texts, category, page_num):
    W, H = 1200, 1200
    canvas = Image.new("RGBA", (W, H), (245, 248, 252, 255))
    draw = ImageDraw.Draw(canvas)

    # Şrift
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

    # Watermark (ortada şəffaf)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_layer)
    wm_bbox = wm_draw.textbbox((0, 0), WATERMARK_TEXT, font=font_watermark)
    wm_w = wm_bbox[2] - wm_bbox[0]
    wm_h = wm_bbox[3] - wm_bbox[1]
    wm_draw.text(((W - wm_w) / 2, (H - wm_h) / 2 - 60), WATERMARK_TEXT, fill=(180, 200, 230, 55), font=font_watermark)
    canvas = Image.alpha_composite(canvas, wm_layer)
    draw = ImageDraw.Draw(canvas)

    # Şəkillərin yerləşdirilməsi
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
        canvas.paste(img_r, (x, y), img_r)

    # Ayırıcı xətt
    draw.rectangle([(0, 625), (W, 630)], fill=(200, 210, 225))

    # Mətn hissəsi
    text_top = 645
    col_w_text = W // num

    for i, text in enumerate(texts):
        x_start = col_w_text * i + 30
        y = text_top
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("•"):
                parts = line[1:].strip().split(":", 1)
                if len(parts) == 2:
                    key = "• " + parts[0].strip() + ":"
                    val = parts[1].strip()
                    draw.text((x_start, y), key, fill=(20, 40, 80), font=font_header)
                    y += 36
                    # Uzun mətnləri bölmək
                    words = val.split()
                    line_text = ""
                    for word in words:
                        test = line_text + " " + word if line_text else word
                        bbox = draw.textbbox((0, 0), test, font=font_text)
                        if bbox[2] - bbox[0] < col_w_text - 60:
                            line_text = test
                        else:
                            draw.text((x_start + 20, y), line_text, fill=(50, 50, 50), font=font_text)
                            y += 32
                            line_text = word
                    if line_text:
                        draw.text((x_start + 20, y), line_text, fill=(50, 50, 50), font=font_text)
                        y += 38
                else:
                    draw.text((x_start, y), line, fill=(50, 50, 50), font=font_text)
                    y += 38

        # Sütunlar arası ayırıcı
        if i < num - 1:
            sep_x = col_w_text * (i + 1)
            draw.rectangle([(sep_x - 1, 630), (sep_x + 1, 1110)], fill=(200, 210, 225))

    # Aşağı footer
    draw.rectangle([(0, 1115), (W, H)], fill=(30, 60, 114))
    footer_text = f"səhifə {page_num}"
    ft_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
    ft_w = ft_bbox[2] - ft_bbox[0]
    draw.text(((W - ft_w) / 2, 1128), footer_text, fill="white", font=font_footer)

    # PNG kimi saxla
    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="PNG", quality=95)
    output.seek(0)
    return output

# ==================== BOT HANDLERLƏRİ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    state = context.user_data.get('state', '')
    text = update.message.text.strip()

    if state == 'wait_category':
        context.user_data['category'] = text
        context.user_data['state'] = 'wait_page'
        await update.message.reply_text(
            f"✅ Kateqoriya: *{text}*\n\nİndi səhifə nömrəsini yazın:",
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
            f"✅ {count} məhsul olacaq.\n\n"
            f"📸 1-ci məhsulun şəklini göndərin:",
            reply_markup=ReplyKeyboardRemove()
        )

    elif state == 'wait_ai_confirm':
        # İstifadəçi AI mətnini təsdiqlədi və ya dəyişdi
        context.user_data['texts'].append(text)
        await next_photo_or_build(update, context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', '')
    if state != 'wait_photo':
        return

    idx = context.user_data.get('current_index', 0)
    total = context.user_data.get('total_count', 1)

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
        await msg.delete()

        # AI məlumat təklifi
        category = context.user_data.get('category', '')
        ai_text = get_ai_product_info(category)
        context.user_data['state'] = 'wait_ai_confirm'
        context.user_data['current_index'] = idx + 1

        keyboard = [[f"✅ Təsdiqlə"], ["✏️ Özüm yazacağam"]]
        await update.message.reply_text(
            f"📸 {idx + 1}-ci şəkil qəbul edildi!\n\n"
            f"🤖 AI təklif etdiyi məlumat:\n\n"
            f"`{ai_text}`\n\n"
            f"Təsdiqləyin və ya öz məlumatınızı yazın:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data['ai_text'] = ai_text

    except Exception as e:
        await msg.delete()
        await update.message.reply_text(f"❌ Xəta: {e}")

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get('state', '')

    if state == 'wait_ai_confirm':
        if text == "✅ Təsdiqlə":
            ai_text = context.user_data.get('ai_text', '')
            context.user_data['texts'].append(ai_text)
            await next_photo_or_build(update, context)
        elif text == "✏️ Özüm yazacağam":
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
            # İstifadəçi öz mətnini yazdı
            context.user_data['texts'].append(text)
            await next_photo_or_build(update, context)

async def next_photo_or_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data.get('current_index', 0)
    total = context.user_data.get('total_count', 1)

    if idx < total:
        context.user_data['state'] = 'wait_photo'
        await update.message.reply_text(
            f"📸 {idx + 1}-ci məhsulun şəklini göndərin:",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # Bütün şəkillər toplandı — kataloq qur
        context.user_data['state'] = 'building'
        await update.message.reply_text("🎨 Kataloq yaradılır...", reply_markup=ReplyKeyboardRemove())
        try:
            images = context.user_data['images']
            texts = context.user_data['texts']
            category = context.user_data.get('category', 'Kataloq')
            page = context.user_data.get('page', '1')

            output = build_catalog_image(images, texts, category, page)
            await update.message.reply_photo(
                photo=output,
                caption="✅ Kataloqunuz hazırdır!"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Kataloq xətası: {e}")
        finally:
            context.user_data.clear()

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex("^(✅ Təsdiqlə|✏️ Özüm yazacağam)$"),
        handle_confirm
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot işə düşdü...")
    app.run_polling()
