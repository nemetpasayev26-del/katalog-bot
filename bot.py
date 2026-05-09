import os
import io
import requests
import google.generativeai as genai
import logging

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)

from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler
)

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageEnhance
)

# =========================================================
# LOGLAMA
# =========================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# =========================================================
# API
# =========================================================

TOKEN = os.environ.get("BOT_TOKEN", "")
SEGMIND_API_KEY = os.environ.get("SEGMIND_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

OUTPUT_FOLDER = "output"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

genai.configure(api_key=GEMINI_API_KEY)

# =========================================================
# AI MƏLUMAT
# =========================================================

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
            f"Yalnız bu formatda yaz."
        )

        return response.text.strip()

    except Exception as e:

        logger.error(f"AI Xətası: {e}")

        return (
            "• Məhsulun adı:\n"
            "• İstifadə sahəsi:\n"
            "• Məhsulun çəkisi:\n"
            "• İstehsalçı:"
        )

# =========================================================
# FON SİLMƏ
# =========================================================

def remove_background(img_bytes: bytes):

    logger.info("Segmind API ilə fon silinir...")

    try:

        response = requests.post(
            "https://api.segmind.com/v1/bg-removal",
            files={
                "image": (
                    "image.jpg",
                    img_bytes,
                    "image/jpeg"
                )
            },
            headers={
                "x-api-key": SEGMIND_API_KEY
            },
            timeout=15
        )

        if response.status_code == 200:

            logger.info("Fon uğurla silindi.")

            return response.content

        else:

            logger.warning(
                f"Segmind xətası: {response.status_code}"
            )

    except Exception as e:

        logger.error(f"Segmind API xətası: {e}")

    return None

# =========================================================
# KEYFİYYƏT
# =========================================================

def enhance_image_quality(img):

    return ImageEnhance.Sharpness(img).enhance(1.5)

# =========================================================
# KATALOQ YARAT
# =========================================================

def build_catalog_image(images, texts, category, page_num):

    logger.info("Yeni kataloq dizaynı başladı...")

    # =========================
    # KANVAS
    # =========================

    W, H = 1080, 1080

    canvas = Image.new(
        "RGB",
        (W, H),
        (255, 255, 255)
    )

    draw = ImageDraw.Draw(canvas)

    # =========================
    # RƏNGLƏR
    # =========================

    BLUE = (35, 55, 100)
    BLACK = (20, 20, 20)
    WHITE = (255, 255, 255)

    # =========================
    # ŞRİFTLƏR
    # =========================

    try:

        font_path = "arial.ttf"

        font_title = ImageFont.truetype(
            font_path,
            34
        )

        font_footer = ImageFont.truetype(
            font_path,
            34
        )

        font_text = ImageFont.truetype(
            font_path,
            23
        )

    except:

        font_title = ImageFont.load_default()
        font_footer = ImageFont.load_default()
        font_text = ImageFont.load_default()

    # =========================
    # ÜST BAR
    # =========================

    top_h = 60

    draw.rectangle(
        [(0, 0), (W, top_h)],
        fill=BLUE
    )

    title = str(category)

    title_w = draw.textlength(
        title,
        font=font_title
    )

    draw.text(
        ((W - title_w) / 2, 12),
        title,
        fill=WHITE,
        font=font_title
    )

    # =========================
    # ALT BAR
    # =========================

    bottom_h = 60

    draw.rectangle(
        [(0, H - bottom_h), (W, H)],
        fill=BLUE
    )

    footer = f"səhifə {page_num}"

    footer_w = draw.textlength(
        footer,
        font=font_footer
    )

    draw.text(
        ((W - footer_w) / 2, H - 48),
        footer,
        fill=WHITE,
        font=font_footer
    )

    # =========================
    # ORTA XƏTT
    # =========================

    draw.rectangle(
        [
            (W // 2 - 2, top_h),
            (W // 2 + 2, H - bottom_h)
        ],
        fill=BLACK
    )

    # =========================
    # WATERMARK
    # =========================

    watermark_path = "watermark.png"

    if os.path.exists(watermark_path):

        wm = Image.open(
            watermark_path
        ).convert("RGBA")

        wm.thumbnail((700, 700))

        alpha = wm.getchannel("A")

        alpha = alpha.point(
            lambda p: 18
        )

        wm.putalpha(alpha)

        wm_x = (W - wm.width) // 2
        wm_y = (H - wm.height) // 2 - 40

        canvas.paste(
            wm,
            (wm_x, wm_y),
            wm
        )

    # =========================
    # MƏHSUL SAHƏSİ
    # =========================

    AREA_TOP = 90
    AREA_BOTTOM = 650

    num_products = len(images)

    col_width = W // num_products

    for i, img in enumerate(images):

        logger.info(
            f"Məhsul {i+1} yerləşdirilir"
        )

        padding_x = 35
        padding_y = 20

        box_x1 = col_width * i + padding_x
        box_x2 = col_width * (i + 1) - padding_x

        box_y1 = AREA_TOP + padding_y
        box_y2 = AREA_BOTTOM - padding_y

        max_w = box_x2 - box_x1
        max_h = box_y2 - box_y1

        img_copy = img.copy()

        img_copy.thumbnail(
            (max_w, max_h),
            Image.Resampling.LANCZOS
        )

        img_copy = enhance_image_quality(
            img_copy
        )

        new_w, new_h = img_copy.size

        paste_x = box_x1 + (
            max_w - new_w
        ) // 2

        paste_y = box_y1 + (
            max_h - new_h
        ) // 2

        canvas.paste(
            img_copy,
            (paste_x, paste_y),
            img_copy
        )

    # =========================
    # MƏTNLƏR
    # =========================

    text_top = 700

    line_height = 36

    for i, text in enumerate(texts):

        x_start = col_width * i + 35

        current_y = text_top

        lines = text.strip().split("\n")

        for line in lines:

            line = line.strip()

            if not line:
                continue

            draw.text(
                (x_start, current_y),
                line,
                fill=BLACK,
                font=font_text
            )

            current_y += line_height

    # =========================
    # KƏNC ÇƏRÇİVƏ
    # =========================

    draw.rounded_rectangle(
        [(2, 2), (W - 2, H - 2)],
        radius=22,
        outline=BLACK,
        width=3
    )

    # =========================
    # ULDUZ
    # =========================

    draw.text(
        (1000, 995),
        "✦",
        fill=WHITE,
        font=font_footer
    )

    # =========================
    # EXPORT
    # =========================

    output = io.BytesIO()

    canvas.save(
        output,
        format="PNG",
        quality=95
    )

    output.seek(0)

    logger.info("Kataloq hazırdır.")

    return output

# =========================================================
# NÖVBƏTİ MƏHSUL
# =========================================================

async def next_photo_or_build(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    idx = context.user_data.get(
        'current_index',
        0
    )

    total = context.user_data.get(
        'total_count',
        1
    )

    if idx < total:

        context.user_data['state'] = 'wait_photo'

        await update.message.reply_text(
            f"📸 {idx + 1}-ci məhsulun şəklini göndərin:",
            reply_markup=ReplyKeyboardRemove()
        )

    else:

        context.user_data['state'] = 'building'

        await update.message.reply_text(
            "🎨 Kataloq yaradılır...",
            reply_markup=ReplyKeyboardRemove()
        )

        try:

            output = build_catalog_image(
                context.user_data['images'],
                context.user_data['texts'],
                context.user_data.get('category', 'Kataloq'),
                context.user_data.get('page', '1')
            )

            await update.message.reply_photo(
                photo=output,
                caption="✅ Kataloq hazırdır!"
            )

        except Exception as e:

            logger.error(f"Kataloq xətası: {e}")

            await update.message.reply_text(
                f"❌ Xəta: {e}"
            )

        finally:

            context.user_data.clear()

# =========================================================
# ŞƏKİL HANDLE
# =========================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    current_state = context.user_data.get('state')

    if current_state != 'wait_photo':
        return

    idx = context.user_data.get(
        'current_index',
        0
    )

    total = context.user_data.get(
        'total_count',
        1
    )

    msg = await update.message.reply_text(
        "⏳ Şəkil emal olunur..."
    )

    try:

        photo = update.message.photo[-1]

        file = await context.bot.get_file(
            photo.file_id
        )

        img_bytes = await file.download_as_bytearray()

        result_bytes = remove_background(
            bytes(img_bytes)
        )

        if result_bytes:

            product_img = Image.open(
                io.BytesIO(result_bytes)
            ).convert("RGBA")

        else:

            product_img = Image.open(
                io.BytesIO(img_bytes)
            ).convert("RGBA")

        bbox = product_img.getbbox()

        if bbox:
            product_img = product_img.crop(bbox)

        context.user_data['images'].append(
            product_img
        )

        context.user_data['current_index'] = idx + 1

        context.user_data['state'] = 'wait_ai_confirm'

        await msg.delete()

        category = context.user_data.get(
            'category',
            'Kataloq'
        )

        ai_text = get_ai_product_info(
            category
        )

        context.user_data['ai_text'] = ai_text

        keyboard = [
            ["✅ Təsdiqlə", "✏️ Özüm yazacağam"]
        ]

        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await update.message.reply_text(
            f"🤖 AI məlumatı:\n\n{ai_text}",
            reply_markup=reply_markup
        )

    except Exception as e:

        logger.error(f"Şəkil xətası: {e}")

        await update.message.reply_text(
            f"❌ Xəta: {e}"
        )

# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    context.user_data['state'] = 'wait_category'

    await update.message.reply_text(
        "🗂 Kateqoriya adını yazın:",
        reply_markup=ReplyKeyboardRemove()
    )

# =========================================================
# TEXT HANDLE
# =========================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = context.user_data.get('state', '')

    text = update.message.text.strip()

    # =========================
    # KATEQORİYA
    # =========================

    if state == 'wait_category':

        context.user_data['category'] = text

        context.user_data['state'] = 'wait_page'

        await update.message.reply_text(
            "📄 Səhifə nömrəsini yazın:"
        )

    # =========================
    # SƏHİFƏ
    # =========================

    elif state == 'wait_page':

        context.user_data['page'] = text

        context.user_data['state'] = 'wait_count'

        keyboard = [["2", "3", "4"]]

        await update.message.reply_text(
            "📦 Neçə məhsul olacaq?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True
            )
        )

    # =========================
    # SAY
    # =========================

    elif state == 'wait_count':

        try:

            count = int(text)

            if count < 1 or count > 6:
                raise ValueError

        except:

            await update.message.reply_text(
                "❌ 1-6 arası rəqəm yazın."
            )

            return

        context.user_data['total_count'] = count

        context.user_data['images'] = []
        context.user_data['texts'] = []

        context.user_data['current_index'] = 0

        context.user_data['state'] = 'wait_photo'

        await update.message.reply_text(
            "📸 1-ci məhsulun şəklini göndərin:",
            reply_markup=ReplyKeyboardRemove()
        )

    # =========================
    # AI TƏSDİQ
    # =========================

    elif state == 'wait_ai_confirm':

        if text == "✅ Təsdiqlə":

            ai_text = context.user_data.get(
                'ai_text',
                ''
            )

            context.user_data['texts'].append(
                ai_text
            )

            await next_photo_or_build(
                update,
                context
            )

        elif text == "✏️ Özüm yazacağam":

            context.user_data['state'] = 'wait_manual_text'

            await update.message.reply_text(
                "📝 Mətn yazın:"
            )

    # =========================
    # MANUAL MƏTN
    # =========================

    elif state == 'wait_manual_text':

        context.user_data['texts'].append(
            text
        )

        await next_photo_or_build(
            update,
            context
        )

# =========================================================
# MAIN
# =========================================================

if __name__ == '__main__':

    if not TOKEN:

        print("BOT_TOKEN tapılmadı!")

        exit(1)

    app = ApplicationBuilder().token(
        TOKEN
    ).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    print("Bot işə düşdü...")

    app.run_polling()
