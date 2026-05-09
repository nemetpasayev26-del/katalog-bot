import os
import io
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

TOKEN = os.environ.get("BOT_TOKEN", "8601872497:AAGpW9QFiogUjQzrr_jSdWTMixgOgS5fL9Y")
OUTPUT_FOLDER = "output"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

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

        # Arxa fonun silinməsi (ağ fon üçün)
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

        # Boşluqların kəsilməsi (crop)
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
            f"📝 **Məhsul məlumatlarını doldurmaq üçün aşağıdakı mətni kopyalayın və doldurub göndərin:**\n\n"
            f"`{shablon}`",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        await update.message.reply_text(f"Xəta baş verdi: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "✅ Kataloqu hazırla":
        await build_catalog(update, context)
    else:
        context.user_data['text_info'] = text
        await update.message.reply_text(
            "✅ Məlumatlar qeyd olundu!\n\n"
            "Başqa şəkil əlavə edə bilərsiniz və ya '✅ Kataloqu hazırla' düyməsini sıxın."
        )

async def build_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get('images', [])
    if not images:
        await update.message.reply_text("Heç bir şəkil göndərilməyib!")
        return

    await update.message.reply_text("🎨 Kataloq yaradılır...")

    try:
        if not os.path.exists("template.png"):
            template = Image.new("RGBA", (1200, 1200), "white")
        else:
            template = Image.open("template.png").convert("RGBA")

        T_W, T_H = template.size
        draw = ImageDraw.Draw(template)

        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                font_path = "arialbd.ttf"
            font_bold = ImageFont.truetype(font_path, int(T_W * 0.035))
            font_desc = ImageFont.truetype(font_path, int(T_W * 0.028))
        except:
            font_bold = ImageFont.load_default()
            font_desc = ImageFont.load_default()

        target_h = int(T_H * 0.55)
        y_pos = int(T_H * 0.20)

        if len(images) == 1:
            img = images[0]
            w_percent = (target_h / float(img.size[1]))
            w_size = int((float(img.size[0]) * float(w_percent)))

            img_resized = enhance_image_quality(img.resize((w_size, target_h), Image.Resampling.LANCZOS))

            x_pos = int((T_W * 0.30) - (img_resized.size[0] / 2))
            template.paste(img_resized, (x_pos, y_pos), img_resized)

            info_text = context.user_data.get('text_info', "Məlumat daxil edilməyib.")
            text_x = int(T_W * 0.55)
            text_y = y_pos + 50

            draw.text((text_x, text_y), "MƏHSUL HAQQINDA:", fill="black", font=font_bold)
            draw.text((text_x, text_y + 70), info_text, fill="#333333", font=font_desc)

        else:
            num = len(images)
            for i, img in enumerate(images):
                w_percent = (target_h / float(img.size[1]))
                w_size = int((float(img.size[0]) * float(w_percent)))

                max_col_w = T_W / num
                if w_size > max_col_w * 0.8:
                    w_size = int(max_col_w * 0.8)
                    h_p = (w_size / float(img.size[0]))
                    final_h = int(img.size[1] * h_p)
                else:
                    final_h = target_h

                img_f = enhance_image_quality(img.resize((w_size, final_h), Image.Resampling.LANCZOS))
                x_pos = int(((T_W / num) * (i + 0.5)) - (img_f.size[0] / 2))
                template.paste(img_f, (x_pos, y_pos), img_f)

        output_path = f"{OUTPUT_FOLDER}/final_{update.message.chat_id}.png"
        template.save(output_path)

        with open(output_path, 'rb') as f:
            await update.message.reply_photo(
                photo=f,
                caption="✅ Kataloqunuz hazırdır!",
                reply_markup=ReplyKeyboardRemove()
            )

    except Exception as e:
        await update.message.reply_text(f"Kataloq yaradılarkən xəta: {e}")
    finally:
        context.user_data['images'] = []
        context.user_data['text_info'] = ""

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Bot işə düşdü...")
    app.run_polling()
