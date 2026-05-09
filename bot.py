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
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_title = ImageFont.truetype(font_path, 56)
        font_bullet_key = ImageFont.truetype(font_path, 32)
        font_bullet_val = ImageFont.truetype(font_reg_path, 32)
        font_footer = ImageFont.truetype(font_path, 48)
        font_watermark = ImageFont.truetype(font_path, 110)
    except:
        font_title = font_bullet_key = font_bullet_val = font_footer = font_watermark = ImageFont.load_default()

    # Yuxarı başlıq
    draw.rectangle([(0, 0), (W, 90)], fill=(30, 60, 114))
    title_bbox = draw.textbbox((0, 0), category, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    draw.text(((W - title_w) / 2, (90 - title_h) / 2), category, fill="white", font=font_title)

    # Watermark (ortada şəffaf)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_layer)
    wm_bbox = wm_draw.textbbox((0, 0), WATERMARK_TEXT, font=font_watermark)
    wm_w = wm_bbox[2] - wm_bbox[0]
    wm_h = wm_bbox[3] - wm_bbox[1]
    wm_draw.text(((W - wm_w) / 2, (H - wm_h) / 2 - 50), WATERMARK_TEXT,
                 fill=(180, 200, 230, 45), font=font_watermark)
    canvas = Image.alpha_composite(canvas, wm_layer)
    draw = ImageDraw.Draw(canvas)

    num = len(images)
    col_w = W // num

    # Şəkil sahəsi
    img_top = 100
    img_bottom = 650
    img_area_h = img_bottom - img_top

    # Sütunlar arası ayırıcı xətlər
    for i in range(1, num):
        sep_x = col_w * i
        draw.rectangle([(sep_x - 2, 90), (sep_x + 2, 1110)], fill=(200, 215, 235))

    # Şəkil və mətn arasında ayırıcı
    draw.rectangle([(0, img_bottom), (W, img_bottom + 4)], fill=(30, 60, 114))

    # Footer
    footer_top = 1110
    draw.rectangle([(0, footer_top), (W, H)], fill=(30, 60, 114))
    footer_text = f"səhifə {page_num}"
    ft_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
    ft_w = ft_bbox[2] - ft_bbox[0]
    ft_h = ft_bbox[3] - ft_bbox[1]
    draw.text(((W - ft_w) / 2, footer_top + (H - footer_top - ft_h) / 2),
              footer_text, fill="white", font=font_footer)

    # Şəkilləri yerləşdir
    for i, img in enumerate(images):
        max_w = col_w - 40
        max_h = img_area_h - 20
        orig_w, orig_h = img.size
        ratio = min(max_w / orig_w, max_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        img_r = enhance_image_quality(img.resize((new_w, new_h), Image.Resampling.LANCZOS))
        x = col_w * i + (col_w - new_w) // 2
        y = img_top + (img_area_h - new_h) // 2
        canvas.paste(img_r, (x, y), img_r)

    # Mətnləri yerləşdir
    text_top = img_bottom + 20
    text_bottom = footer_top - 10

    for i, text in enumerate(texts):
        x_start = col_w * i + 25
        y = text_top
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or y >= text_bottom - 40:
                continue

            if line.startswith("•"):
                parts = line[1:].strip().split(":", 1)
                if len(parts) == 2:
                    key = "• " + parts[0].strip() + ":"
                    val = parts[1].strip()

                    draw.text((x_start, y), key, fill=(20, 40, 100), font=font_bullet_key)
                    y += 42

                    max_text_w = col_w - 55
                    words = val.split()
                    line_text = ""
                    for word in words:
                        test = line_text + " " + word if line_text else word
                        bbox = draw.textbbox((0, 0), test, font=font_bullet_val)
                        if bbox[2] - bbox[0] <= max_text_w:
                            line_text = test
                        else:
                            if y < text_bottom - 40:
                                draw.text((x_start + 20, y), line_text,
                                          fill=(60, 60, 60), font=font_bullet_val)
                                y += 36
                            line_text = word
                    if line_text and y < text_bottom - 40:
                        draw.text((x_start + 20, y), line_text,
                                  fill=(60, 60, 60), font=font_bullet_val)
                        y += 46
                else:
                    draw.text((x_start, y), line, fill=(60, 60, 60), font=font_bullet_val)
                    y += 46
            else:
                draw.text((x_start, y), line, fill=(60, 60, 60), font=font_bullet_val)
                y += 46

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="PNG", quality=95)
    output.seek(0)
    return output

# ==================== BOT ====================

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
        await msg.delete()
        await update.message.reply_text(f"❌ Xəta: {e}")

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
        context.user_data['state'] = 'building'
        await update.message.reply_text("🎨 Kataloq yaradılır...", reply_markup=ReplyKeyboardRemove())
        try:
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

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot işə düşdü...")
    app.run_polling()
