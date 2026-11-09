import asyncio
import json
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiohttp import web
import requests

# --- SOZLAMALAR ---
BOT_TOKEN = "9003948892:AAG27bYVJuEYganhBjm90FODFKFxwvmQxzI"
CHANNEL_USERNAME = -1001444808482  # Post boradigan kanal

# Make.com'dan olgan Webhook manzilingiz (faqat rasmlar uchun ishlatiladi):
MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/ugqus96xbf3sk6l9x49etv6h0kuo3cjq"

# Adminlar ID raqamlari
ADMIN_IDS = [182763217, 466061710, 1681513161]

DB_FILE = "posts.json"
published_posts = set()


# Ma'lumotlarni fayldan o'qish
def load_posts():
  if os.path.exists(DB_FILE):
    try:
      with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return {eval(k): v for k, v in data.items()}
    except Exception:
      return {}
  return {}


# Ma'lumotlarni faylga saqlash
def save_posts():
  try:
    data = {str(k): v for k, v in admin_posts.items()}
    with open(DB_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"❌ Faylga saqlashda xato: {e}")


admin_posts = load_posts()

# Loggingni sozlash
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

HASHTAG = "#yozyovon_tuman_ixtisoslaştirilgan_maktabi"
FOOTER = """💻 maktab matbuot xizmati

✨ Bizni kuzatişda davom eting:

🌐 <a href="https://t.me/PMIyozyovon">Telegram</a> | <a href="https://www.facebook.com/YozyovonIM">Facebook</a> | <a href="http://instagram.com/yozyovon_im">Instagram</a>"""

start_reply_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="/start")]], resize_keyboard=True
)


def convert_to_special_alphabet(text: str) -> str:
  pairs = [
      ("SH", "Ş"),
      ("Sh", "Ş"),
      ("sh", "ş"),
      ("CH", "Ç"),
      ("Ch", "Ç"),
      ("ch", "ç"),
      ("O‘", "Ö"),
      ("O'", "Ö"),
      ("o‘", "ö"),
      ("o'", "ö"),
      ("g\u2018", "ğ"),
      ("g'", "ğ"),
      ("G‘", "Ğ"),
      ("G'", "Ğ"),
      ("g‘", "ğ"),
  ]
  for old, new in pairs:
    text = text.replace(old, new)
  return text


class PostForm(StatesGroup):
  waiting_for_media = State()
  waiting_for_title = State()
  waiting_for_text = State()


@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
  await state.clear()
  await message.answer(
      "Assalomu alaykum! Maktabimiz matbuot xizmati botiga xush kelibsiz. 🤖\n\n"
      "Bu bot yordamida tadbirlar uchun postlar tayyorlashingiz mumkin.\n"
      "Eslatma: Siz tayyorlagan post avval **adminlar ko'rigiga** yuboriladi"
      " va tasdiqlangach kanalga chiqariladi.\n\n"
      "Iltimos, tadbirga oid **1 ta yoki bir nechta (10 tagacha) rasm**"
      " yuboring, yoki **bitta video** yuboring.",
      reply_markup=start_reply_kb,
  )
  await state.update_data(media_type=None, photos=[], video_id=None)
  await state.set_state(PostForm.waiting_for_media)


@dp.message(PostForm.waiting_for_media, F.photo)
async def process_photos(message: Message, state: FSMContext):
  data = await state.get_data()
  if data.get("media_type") == "video":
    await message.answer(
        "⚠️ Siz allaqachon video yuborgansiz! Iltimos, /start tugmasini bosing.",
        reply_markup=start_reply_kb,
    )
    return

  photos = data.get("photos", [])
  if len(photos) >= 10:
    await message.answer(
        "⚠️ Ko'pi bilan 10 ta rasm yuklashingiz mumkin!",
        reply_markup=start_reply_kb,
    )
    return

  photo_file_id = message.photo[-1].file_id
  photos.append(photo_file_id)
  await state.update_data(media_type="photo", photos=photos)

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="Tayyor ✅", callback_data="finish_media")]
      ]
  )
  await message.answer(
      f"Rasm qabul qilindi ({len(photos)}/10). Yana rasm yuborishingiz yoki"
      " tugmani bosishingiz mumkin:",
      reply_markup=start_reply_kb,
  )
  await message.answer("Tasdiqlash uchun bosing:", reply_markup=keyboard)


@dp.message(PostForm.waiting_for_media, F.video)
async def process_video(message: Message, state: FSMContext):
  data = await state.get_data()
  if data.get("photos"):
    await message.answer(
        "⚠️ Siz oldin rasm yuborgansiz! Iltimos, /start tugmasini bosing.",
        reply_markup=start_reply_kb,
    )
    return

  video_id = message.video.file_id
  await state.update_data(media_type="video", video_id=video_id)

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="Tayyor ✅", callback_data="finish_media")]
      ]
  )
  await message.answer(
      "🎥 **Video qabul qilindi!** Davom etish uchun quyidagi tugmani bosing:",
      reply_markup=start_reply_kb,
  )
  await message.answer("Tasdiqlash uchun bosing:", reply_markup=keyboard)


@dp.callback_query(F.data == "finish_media")
async def finish_media_callback(callback: CallbackQuery, state: FSMContext):
  data = await state.get_data()
  media_type = data.get("media_type")
  photos = data.get("photos", [])
  video_id = data.get("video_id")

  try:
    await callback.message.edit_reply_markup(reply_markup=None)
  except Exception:
    pass

  if not media_type or (media_type == "photo" and not photos) or (
      media_type == "video" and not video_id
  ):
    await callback.answer(
        "Bu tugma allaqachon ishlatilgan yoki ma'lumotlar topilmadi. Iltimos,"
        " /start ni bosing.",
        show_alert=True,
    )
    return

  await callback.message.answer(
      "Qabul qilindi! Endi **tadbir nomini** yuboring:", reply_markup=start_reply_kb
  )
  await state.set_state(PostForm.waiting_for_title)
  await callback.answer()


@dp.message(PostForm.waiting_for_title, F.text)
async def process_title(message: Message, state: FSMContext):
  await state.update_data(title=message.text)
  await message.answer(
      "Tadbir uchun **post matnini yozib yuboring:**", reply_markup=start_reply_kb
  )
  await state.set_state(PostForm.waiting_for_text)


@dp.message(PostForm.waiting_for_text, F.text)
async def process_post_text(message: Message, state: FSMContext):
  user_text = message.text
  data = await state.get_data()

  title = data.get("title")
  media_type = data.get("media_type")
  photos = data.get("photos")
  video_id = data.get("video_id")

  author_name = message.from_user.full_name
  author_username = (
      f"@{message.from_user.username}"
      if message.from_user.username
      else "Mavjud emas"
  )

  try:
    formatted_title = convert_to_special_alphabet(title.strip())
    formatted_body = convert_to_special_alphabet(user_text.strip())

    final_post = (
        f"{HASHTAG}\n\n<b>{formatted_title}</b>\n\n{formatted_body}\n\n{FOOTER}"
    )

    if len(final_post) > 1024:
      allowed_len = (
          1024
          - len(f"{HASHTAG}\n\n<b>{formatted_title}</b>\n\n\n\n{FOOTER}")
          - 10
      )
      formatted_body = formatted_body[:allowed_len] + "..."
      final_post = (
          f"{HASHTAG}\n\n<b>{formatted_title}</b>\n\n{formatted_body}\n\n{FOOTER}"
      )

    admin_caption = (
        f"🔔 **Yangi post tasdiq uchun keldi!**\n👤 Muallif: {author_name}"
        f" ({author_username})\n\n---\n\n{final_post}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Tasdiqlash ✅", callback_data="approve_post"
                ),
                InlineKeyboardButton(
                    text="Rad etish ❌", callback_data="reject_post"
                ),
            ]
        ]
    )

    for admin_id in ADMIN_IDS:
      try:
        if media_type == "video":
          sent_admin_msg = await bot.send_video(
              chat_id=admin_id,
              video=video_id,
              caption=admin_caption,
              parse_mode="HTML",
              reply_markup=keyboard,
          )
          admin_posts[(admin_id, sent_admin_msg.message_id)] = {
              "media_type": "video",
              "video_id": video_id,
              "caption": final_post,
          }
        elif len(photos) == 1:
          sent_admin_msg = await bot.send_photo(
              chat_id=admin_id,
              photo=photos[0],
              caption=admin_caption,
              parse_mode="HTML",
              reply_markup=keyboard,
          )
          admin_posts[(admin_id, sent_admin_msg.message_id)] = {
              "media_type": "photo",
              "photos": photos,
              "caption": final_post,
          }
        else:
          media_group = [
              InputMediaPhoto(
                  media=photos[0], caption=admin_caption, parse_mode="HTML"
              )
          ]
          for p_id in photos[1:]:
            media_group.append(InputMediaPhoto(media=p_id))

          await bot.send_media_group(chat_id=admin_id, media=media_group)
          sent_admin_msg = await bot.send_message(
              chat_id=admin_id,
              text="Yuqoridagi postni tasdiqlaysizmi?",
              reply_markup=keyboard,
          )
          admin_posts[(admin_id, sent_admin_msg.message_id)] = {
              "media_type": "photo",
              "photos": photos,
              "caption": final_post,
          }
      except Exception as e:
        print(f"❌ Admin {admin_id} ga yuborishda xato: {e}")

    save_posts()

    await message.answer(
        "✅ Post muvaffaqiyatli tayyorlandi va **adminlar ko'rigiga** yuborildi!",
        reply_markup=start_reply_kb,
    )
    await state.clear()

  except Exception as e:
    print(f"❌ Xatolik yuz berdi: {e}")
    await message.answer(
        f"❌ Xatolik yuz berdi: {e}", reply_markup=start_reply_kb
    )
    await state.clear()


@dp.callback_query(F.data == "approve_post")
async def approve_callback(callback: CallbackQuery):
  if callback.from_user.id not in ADMIN_IDS:
    await callback.answer("Sizda bu amalni bajarish huquqi yo'q!", show_alert=True)
    return

  if callback.message.reply_markup is None:
    await callback.answer(
        "Bu post allaqachon ko'rib chiqilgan!", show_alert=True
    )
    return

  try:
    original_message = callback.message
    admin_id = callback.from_user.id
    msg_id = original_message.message_id

    post_data = admin_posts.get((admin_id, msg_id))

    if not post_data:
      await callback.answer(
          "Xatolik: Post ma'lumotlari topilmadi.", show_alert=True
      )
      return

    media_type = post_data["media_type"]
    post_caption = post_data["caption"]

    if media_type == "video":
      post_unique_key = post_data["video_id"]
    else:
      post_unique_key = post_data["photos"][0]

    if post_unique_key in published_posts:
      await callback.answer(
          "⚠️ Bu post allaqachon boshqa admin tomonidan tasdiqlangan va kanalga"
          " chiqarilgan!",
          show_alert=True,
      )
      if original_message.photo or original_message.video:
        await callback.message.edit_caption(
            caption=(original_message.caption or "")
            + "\n\n✅ [ALLAQACHON TASDIQLANGAN]",
            parse_mode="HTML",
            reply_markup=None,
        )
      else:
        await callback.message.edit_text(
            text="<b>✅ [ALLAQACHON TASDIQLANGAN]</b>",
            parse_mode="HTML",
            reply_markup=None,
        )
      return

    # Kanalga chiqarish
    if media_type == "video":
      await bot.send_video(
          chat_id=CHANNEL_USERNAME,
          video=post_data["video_id"],
          caption=post_caption,
          parse_mode="HTML",
      )
    else:
      photos = post_data["photos"]
      if len(photos) == 1:
        await bot.send_photo(
            chat_id=CHANNEL_USERNAME,
            photo=photos[0],
            caption=post_caption,
            parse_mode="HTML",
        )
      else:
        media_group = [
            InputMediaPhoto(
                media=photos[0], caption=post_caption, parse_mode="HTML"
            )
        ]
        for p_id in photos[1:]:
          media_group.append(InputMediaPhoto(media=p_id))

        await bot.send_media_group(chat_id=CHANNEL_USERNAME, media=media_group)

    published_posts.add(post_unique_key)

    # Make.com Webhook'ga yuborish (Faqat RASMLAR uchun)
    if MAKE_WEBHOOK_URL and "BURAGA" not in MAKE_WEBHOOK_URL:
      try:
        if media_type == "photo":
          file_info = await bot.get_file(post_data["photos"][0])
          file_path = file_info.file_path
          photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

          requests.post(
              MAKE_WEBHOOK_URL,
              json={"photo_url": photo_url, "caption": post_caption},
              timeout=15,
          )
      except Exception as wb_err:
        print(f"❌ Make.com webhook'ga yuborishda xatolik: {wb_err}")

    if original_message.photo or original_message.video:
      old_caption = original_message.caption or ""
      new_caption = old_caption + "\n\n✅ [TASDIQLANDI]"
      await callback.message.edit_caption(
          caption=new_caption, parse_mode="HTML", reply_markup=None
      )
    else:
      await callback.message.edit_text(
          text="<b>✅ [TASDIQLANDI] - Kanalga chiqarildi</b>",
          parse_mode="HTML",
          reply_markup=None,
      )

    await callback.answer("Post muvaffaqiyatli kanalga joylandi!")

  except Exception as e:
    print(f"❌ Kanalga joylashda xato: {e}")
    await callback.answer(f"Xatolik yuz berdi: {e}", show_alert=True)


@dp.channel_post(F.photo)
async def manual_channel_photo_post(message: types.Message):
  try:
    if message.chat.id == CHANNEL_USERNAME or message.chat.username == str(
        CHANNEL_USERNAME
    ).replace("-100", ""):
      if MAKE_WEBHOOK_URL and "BURAGA" not in MAKE_WEBHOOK_URL:
        photo_file_id = message.photo[-1].file_id
        file_info = await bot.get_file(photo_file_id)
        file_path = file_info.file_path
        photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        caption = message.caption or ""

        requests.post(
            MAKE_WEBHOOK_URL,
            json={"photo_url": photo_url, "caption": caption},
            timeout=15,
        )
  except Exception as e:
    print(f"❌ Qo'lda yozilgan kanal fotosini yuborishda xato: {e}")


# --- AIOHTTP WEB SERVER (PORT UCHUN) ---
async def handle_ping(request):
  return web.Response(text="Bot is active and running 24/7!")


async def start_web_server():
  app = web.Application()
  app.router.add_get("/", handle_ping)
  runner = web.AppRunner(app)
  await runner.setup()
  port = int(os.environ.get("PORT", 10000))
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()
  print(f"🌐 Aiohttp web server {port}-portda ishga tushdi!")


async def main():
  await start_web_server()
  await bot.delete_webhook(drop_pending_updates=True)
  print("🤖 Telegram bot polling rejimiga o'tdi va ishlayapti!")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
