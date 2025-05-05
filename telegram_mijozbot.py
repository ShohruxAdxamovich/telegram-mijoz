
import os
from dotenv import load_dotenv
load_dotenv()
import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart

# --- Config ---
API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GROUP_ID = int(os.getenv("GROUP_ID"))

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Database ---
conn = sqlite3.connect("manabu.db")
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        name TEXT
    )
""")
conn.commit()

# --- States ---
class SubjectForm(StatesGroup):
    collecting = State()

class AdminBroadcast(StatesGroup):
    choosing_mode = State()
    entering_user_id = State()
    waiting_message = State()

# --- Global subject cache ---
user_subjects_cache = {}

# --- Fan -> Message ID ---
subject_posts = {
    "Ingliz tili": 983,
    "Rus tili": 986,
    "Ona tili": 984,
    "Tarix": 988,
    "Matematika": 985,
    "Fizika": 987,
    "Kimyo": 989,
    "Biologiya": 990
}
FANLAR = list(subject_posts.keys())

# --- Keyboards ---
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Kurslar haqida")],
            [KeyboardButton(text="📞 Bog‘lanish"), KeyboardButton(text="ℹ️ Ma'lumot")],
            [KeyboardButton(text="📘 Fanlar")],
            [KeyboardButton(text="🏠 Bosh menyu")]
        ],
        resize_keyboard=True
    )

def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def subjects_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ingliz tili"), KeyboardButton(text="Rus tili"), KeyboardButton(text="Ona tili")],
            [KeyboardButton(text="Tarix"), KeyboardButton(text="Matematika"), KeyboardButton(text="Fizika")],
            [KeyboardButton(text="Kimyo"), KeyboardButton(text="Biologiya")],
            [KeyboardButton(text="⬅️ Ortga")]
        ],
        resize_keyboard=True
    )

def confirm_subjects_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Ro'yxatdan o'tish"), KeyboardButton(text="⬅️ Bekor qilish")]
        ],
        resize_keyboard=True
    )

def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Hisobot", callback_data="admin_report")],
        [InlineKeyboardButton(text="📤 Umumiy xabar yuborish", callback_data="admin_broadcast_all")],
        [InlineKeyboardButton(text="📨 Yakka xabar yuborish", callback_data="admin_broadcast_one")]
    ])

# --- Main ---
async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(CommandStart())
    @dp.message(lambda msg: msg.text == "🏠 Bosh menyu")
    async def universal_start(message: types.Message, state: FSMContext):
        user = message.from_user
        cur.execute("INSERT OR IGNORE INTO users (user_id, username, name) VALUES (?, ?, ?)",
                    (user.id, user.username, user.full_name))
        conn.commit()
        await state.clear()
        await message.answer(f"Salom, {user.full_name}! Asosiy menyudasiz.", reply_markup=main_menu())

    @dp.message(lambda msg: msg.text == "📘 Fanlar")
    async def show_subjects(message: types.Message, state: FSMContext):
        await state.update_data(subjects=set())
        await state.set_state(SubjectForm.collecting)
        await message.answer("Qaysi fanlarga qiziqasiz? Tanlab bo‘lgach '⬅️ Ortga' ni bosing.", reply_markup=subjects_menu())

    @dp.message(lambda msg: msg.text in FANLAR)
    async def choose_subject(message: types.Message, state: FSMContext):
        state_data = await state.get_data()
        subjects = state_data.get("subjects", set())
        subjects.add(message.text)
        await state.update_data(subjects=subjects)

        post_id = subject_posts.get(message.text)
        if post_id:
            await bot.forward_message(chat_id=message.chat.id, from_chat_id=GROUP_ID, message_id=post_id)
        else:
            await message.answer(f"✅ {message.text} tanlandi.")

    @dp.message(lambda msg: msg.text == "⬅️ Ortga")
    async def finish_subjects(message: types.Message, state: FSMContext):
        state_data = await state.get_data()
        subjects = state_data.get("subjects", set())
        if subjects:
            user_subjects_cache[message.from_user.id] = list(subjects)
            await message.answer("✅ Fanlar tanlandi. Endi ro'yxatdan o'tishingiz mumkin.", reply_markup=confirm_subjects_keyboard())
        else:
            await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu())
        await state.clear()

    @dp.message(lambda msg: msg.text == "✍️ Ro'yxatdan o'tish")
    async def ask_contact(message: types.Message):
        await message.answer("Ro'yxatdan o'tish uchun telefon raqamingizni yuboring:", reply_markup=contact_keyboard())

    @dp.message(lambda msg: msg.contact)
    async def handle_contact(message: types.Message, state: FSMContext):
        await message.answer("Rahmat! Siz bilan tez orada bog'lanamiz.", reply_markup=main_menu())
        user = message.from_user
        username = user.username if user.username else "username yo'q"
        full_name = user.full_name
        phone = message.contact.phone_number
        subjects = user_subjects_cache.get(user.id, [])
        subjects_text = "\n📘 Fanlar: " + ", ".join(subjects) if subjects else ""

        await bot.send_message(
            GROUP_ID,
            f"📲 Yangi ro'yxatdan o'tish:\n"
            f"👤 Ismi: {full_name}\n"
            f"🔗 Username: @{username}\n"
            f"🆔 ID: {user.id}\n"
            f"📞 Telefon: {phone}"
            f"{subjects_text}"
        )
        await state.clear()
        user_subjects_cache.pop(user.id, None)

    @dp.message(lambda msg: msg.text == "⬅️ Bekor qilish")
    async def cancel_registration(message: types.Message):
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu())

    @dp.message(lambda msg: msg.text == "📚 Kurslar haqida")
    async def courses_info(message: types.Message):
        await bot.forward_message(chat_id=message.chat.id, from_chat_id=GROUP_ID, message_id=982)

    @dp.message(lambda msg: msg.text == "📞 Bog‘lanish")
    async def contact(message: types.Message):
        await message.answer("Biz bilan bog‘lanish uchun: @MenejerMutaxasiss")

    @dp.message(lambda msg: msg.text == "ℹ️ Ma'lumot")
    async def info(message: types.Message):
        await message.answer("Biz haqimizda: https://t.me/+GjOm3oOb3aA3MzIy")

    @dp.message(lambda msg: msg.text == "/admin" and msg.from_user.id == ADMIN_ID)
    async def show_admin_panel(message: types.Message):
        await message.answer("Admin paneliga xush kelibsiz:", reply_markup=admin_panel())

    @dp.callback_query(lambda call: call.data == "admin_report")
    async def admin_report(call: types.CallbackQuery):
        cur.execute("SELECT user_id, username, name FROM users")
        users = cur.fetchall()
        text = f"👥 Umumiy foydalanuvchilar soni: {len(users)}\n"
        for u in users:
            username = u[1] if u[1] else "username yo'q"
            text += f"\n🆔 {u[0]} - {u[2]} (@{username})"
        await call.message.answer(text)

    @dp.callback_query(lambda call: call.data == "admin_broadcast_all")
    async def start_broadcast_all(call: types.CallbackQuery, state: FSMContext):
        await state.set_state(AdminBroadcast.waiting_message)
        await state.update_data(mode="all")
        await call.message.answer("✍️ Yuboriladigan xabar (matn, rasm, yoki video) ni kiriting:")

    @dp.callback_query(lambda call: call.data == "admin_broadcast_one")
    async def start_broadcast_one(call: types.CallbackQuery, state: FSMContext):
        await state.set_state(AdminBroadcast.entering_user_id)
        await call.message.answer("🆔 Foydalanuvchi ID sini kiriting:")

    @dp.message(AdminBroadcast.entering_user_id)
    async def enter_user_id(message: types.Message, state: FSMContext):
        await state.update_data(mode="one", user_id=message.text)
        await state.set_state(AdminBroadcast.waiting_message)
        await message.answer("✍️ Yuboriladigan xabarni kiriting:")

    @dp.message(AdminBroadcast.waiting_message)
    async def handle_broadcast_message(message: types.Message, state: FSMContext):
        data = await state.get_data()
        mode = data.get("mode")
        user_id = data.get("user_id")

        cur.execute("SELECT user_id FROM users")
        users = [u[0] for u in cur.fetchall()]

        targets = users if mode == "all" else [int(user_id)]

        for uid in targets:
            try:
                if message.text:
                    await bot.send_message(uid, message.text)
                elif message.photo:
                    await bot.send_photo(uid, photo=message.photo[-1].file_id, caption=message.caption or "")
                elif message.video:
                    await bot.send_video(uid, video=message.video.file_id, caption=message.caption or "")
            except Exception as e:
                print(f"Xatolik: {e}")

        await message.answer("✅ Xabar yuborildi!")
        await state.clear()

    print("Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
