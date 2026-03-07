import os
import math
import telebot
from telebot import types
import threading
import time
from datetime import datetime, timedelta
import sqlite3
import urllib.request
import urllib.parse
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# -----------------------------------------------------------------------
# ⚙️ SOZLAMALAR
# -----------------------------------------------------------------------
API_TOKEN   = os.environ.get('BOT_TOKEN', '8239336439:AAEsMwnWliN6vWhErJ6YEsup7KxY5DctAp0')
KANAL_ID    = os.environ.get('KANAL_ID', '@shaxsiy_nazoratchi')
KANAL_LINKI = os.environ.get('KANAL_LINKI', 'https://t.me/shaxsiy_nazoratchi')
DB_PATH     = os.environ.get('DB_PATH', 'bot_data.db')

bot = telebot.TeleBot(API_TOKEN, parse_mode=None)

# -----------------------------------------------------------------------
# 💬 MOTIVATSION XABARLAR
# -----------------------------------------------------------------------
MOTIVATSIYA = [
    "🌟 Har bir qadam oldinga — g'alaba sari!",
    "💪 Bugun qiyin, ertaga oson. Davom eting!",
    "🎯 Maqsadingizga har kuni bir qadam yaqinlashing!",
    "🔥 Kichik harakatlar katta natijalarga olib keladi!",
    "⭐ Siz bugungi eng yaxshi versiyangiz bo'ling!",
    "🚀 Izchillik — muvaffaqiyatning kaliti!",
    "🌈 Har bir bajarilgan reja — kelajakka investitsiya!",
    "💡 Bugun ekilgan urug' ertaga meva beradi!",
    "🏆 G'oliblar har kuni o'zlarini yengishadi!",
    "✨ Siz qila olasiz — ishoning o'zingizga!",
]

# -----------------------------------------------------------------------
# 🏆 UNVONLAR (Ball tizimi)
# -----------------------------------------------------------------------
UNVONLAR = [
    (0,    "🥉 Yangi boshlovchi"),
    (100,  "🥈 Harakat qiluvchi"),
    (300,  "🥇 Izchil insonl"),
    (600,  "🏅 Maqsadli shaxs"),
    (1000, "🏆 Nazoratchi ustasi"),
    (2000, "👑 Rivojlanish chempioni"),
]

def get_unvon(ball):
    unvon = UNVONLAR[0][1]
    for min_ball, nom in UNVONLAR:
        if ball >= min_ball:
            unvon = nom
    return unvon

def keyingi_unvon(ball):
    for min_ball, nom in UNVONLAR:
        if ball < min_ball:
            return min_ball, nom
    return None, None

# -----------------------------------------------------------------------
# 💾 MA'LUMOTLAR BAZASI
# -----------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        name       TEXT    NOT NULL,
        phone      TEXT    DEFAULT '',
        registered INTEGER DEFAULT 0,
        ball       INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS namoz_times (
        user_id  INTEGER PRIMARY KEY,
        bomdod TEXT, peshin TEXT, asr TEXT, shom TEXT, xufton TEXT,
        saved_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS namoz_notify (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        namoz_nomi  TEXT,
        notified_at REAL,
        asked       INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS namoz_stats (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        namoz_nomi TEXT,
        sana       TEXT,
        holat      TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS daily_tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        task_name   TEXT,
        task_time   TEXT,
        sana        TEXT,
        status      INTEGER,
        notified    INTEGER DEFAULT 0,
        notified_at REAL    DEFAULT 0,
        verified    INTEGER DEFAULT 0,
        source      TEXT    DEFAULT 'daily',
        category    TEXT    DEFAULT 'Umumiy',
        priority    TEXT    DEFAULT 'oddiy'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS weekly_tasks (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        task_name TEXT,
        task_time TEXT,
        category  TEXT    DEFAULT 'Umumiy',
        priority  TEXT    DEFAULT 'oddiy',
        active    INTEGER DEFAULT 1
    )''')

    # Odatlar (Habit tracker)
    c.execute('''CREATE TABLE IF NOT EXISTS habits (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        name      TEXT,
        emoji     TEXT    DEFAULT '✅',
        active    INTEGER DEFAULT 1,
        created   TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS habit_logs (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER,
        user_id  INTEGER,
        sana     TEXT,
        done     INTEGER DEFAULT 0
    )''')

    # Maqsadlar
    c.execute('''CREATE TABLE IF NOT EXISTS goals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        title       TEXT,
        deadline    TEXT,
        reward      TEXT,
        status      TEXT    DEFAULT 'active',
        created     TEXT,
        ball_reward INTEGER DEFAULT 50
    )''')

    # Foydalanuvchi mukofotlari
    c.execute('''CREATE TABLE IF NOT EXISTS rewards (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        title      TEXT,
        ball_cost  INTEGER,
        created    TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------
# 🔧 YORDAMCHI
# -----------------------------------------------------------------------
def uz_time():
    return datetime.utcnow() + timedelta(hours=5)

def today_str():
    return uz_time().strftime("%Y-%m-%d")

def is_registered(uid):
    conn = get_conn()
    row = conn.execute("SELECT registered FROM users WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return bool(row and row['registered'])

def get_name(uid):
    conn = get_conn()
    row = conn.execute("SELECT name FROM users WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return row['name'] if row else "Foydalanuvchi"

def get_ball(uid):
    conn = get_conn()
    row = conn.execute("SELECT ball FROM users WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return row['ball'] if row else 0

def add_ball(uid, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET ball = ball + ? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

import random
def get_motivatsiya():
    return random.choice(MOTIVATSIYA)

# -----------------------------------------------------------------------
# 📋 MENYULAR
# -----------------------------------------------------------------------
def show_main_menu(chat_id, uid=None):
    if uid is None: uid = chat_id
    name = get_name(uid)
    ball = get_ball(uid)
    unvon = get_unvon(ball)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📝 Kunlik reja"),   types.KeyboardButton("📅 Haftalik reja"))
    markup.row(types.KeyboardButton("🕌 Namoz"),          types.KeyboardButton("🎯 Odatlar"))
    markup.row(types.KeyboardButton("🏆 Maqsadlar"),      types.KeyboardButton("📊 Hisobotlar"))
    markup.row(types.KeyboardButton("👤 Profil"))
    bot.send_message(chat_id,
        f"Assalomu alaykum, *{name}*! 👋\n"
        f"{unvon} | 💰 {ball} ball\n\n"
        f"{get_motivatsiya()}",
        reply_markup=markup, parse_mode="Markdown")

def show_namoz_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("⏰ Namoz vaqtlarini kiritish"))
    markup.row(types.KeyboardButton("🧭 Qibla aniqlash"))
    markup.row(types.KeyboardButton("📊 Namoz statistikasi"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "🕌 *Namoz bo'limi:*", reply_markup=markup, parse_mode="Markdown")

def show_kunlik_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("➕ Reja qo'shish"), types.KeyboardButton("📋 Bugungi rejalar"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "📝 *Kunlik reja bo'limi:*", reply_markup=markup, parse_mode="Markdown")

def show_haftalik_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("➕ Haftalik reja qo'shish"), types.KeyboardButton("📋 Haftalik rejalarim"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id,
        "📅 *Haftalik reja bo'limi*\n_Har kuni o'sha vaqtda eslatiladi._",
        reply_markup=markup, parse_mode="Markdown")

def show_hisobot_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📈 Kunlik hisobot"), types.KeyboardButton("📆 Haftalik hisobot"))
    markup.row(types.KeyboardButton("🗓 Oylik hisobot"),  types.KeyboardButton("📉 Grafik"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "📊 *Hisobotlar bo'limi:*", reply_markup=markup, parse_mode="Markdown")

def show_habits_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("➕ Odat qo'shish"), types.KeyboardButton("📋 Odatlarim"))
    markup.row(types.KeyboardButton("✅ Bugungi odatlar"), types.KeyboardButton("📊 Odat statistikasi"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "🎯 *Odatlar (Habit Tracker):*", reply_markup=markup, parse_mode="Markdown")

def show_goals_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("➕ Maqsad qo'shish"), types.KeyboardButton("📋 Maqsadlarim"))
    markup.row(types.KeyboardButton("🎁 Mukofotlar"),       types.KeyboardButton("💰 Ballarim"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "🏆 *Maqsadlar va Mukofotlar:*", reply_markup=markup, parse_mode="Markdown")

# Kategoriya va muhimlik tanlash
KATEGORIYALAR = ["💼 Ish", "📚 O'qish", "🏋️ Sport", "👨‍👩‍👧 Oila", "🌱 Shaxsiy", "⚙️ Boshqa"]
MUHIMLIK = {"🔴 Shoshilinch": "shoshilinch", "🟡 O'rta": "orta", "🟢 Oddiy": "oddiy"}

# -----------------------------------------------------------------------
# 🚀 START VA A'ZOLIK
# -----------------------------------------------------------------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    bot.send_message(uid,
        "Assalomu alaykum! 👋\n*SHAXSIY NAZORATCHI* botiga xush kelibsiz!\n\n"
        "✅ Kunlik/Haftalik rejalar\n🕌 Namoz nazorati\n"
        "🎯 Odatlar kuzatuvi\n🏆 Maqsad va mukofotlar\n📊 Statistika va grafiklar",
        parse_mode="Markdown")
    check_subscription(message)

def check_subscription(message):
    uid = message.from_user.id
    try:
        status = bot.get_chat_member(KANAL_ID, uid).status
        subscribed = status in ['member', 'administrator', 'creator']
    except:
        subscribed = True
    if subscribed:
        if is_registered(uid):
            show_main_menu(uid)
        else:
            ask_name(message)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url=KANAL_LINKI))
        markup.add(types.InlineKeyboardButton("✅ A'zo bo'ldim", callback_data="check_sub"))
        bot.send_message(uid, "⚠️ Botdan foydalanish uchun avval kanalga a'zo bo'ling:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def cb_check_sub(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    check_subscription(call.message)

# -----------------------------------------------------------------------
# 📝 RO'YXATDAN O'TISH
# -----------------------------------------------------------------------
def ask_name(message):
    msg = bot.send_message(message.chat.id, "Ismingizni kiriting:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_save_name)

def step_save_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    if not name or len(name) > 50:
        msg = bot.send_message(uid, "❌ Ism noto'g'ri. Qaytadan kiriting:")
        bot.register_next_step_handler(msg, step_save_name)
        return
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO users (user_id, name, registered) VALUES (?,?,0)", (uid, name))
    conn.commit(); conn.close()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True))
    msg = bot.send_message(uid, f"Rahmat, *{name}*! Telefon raqamingizni yuboring 👇",
                           reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_save_phone)

def step_save_phone(message):
    uid = message.from_user.id
    phone = message.contact.phone_number if message.contact else message.text.strip()
    conn = get_conn()
    conn.execute("UPDATE users SET phone=?, registered=1 WHERE user_id=?", (phone, uid))
    conn.commit(); conn.close()
    bot.send_message(uid, "✅ *Ro'yxatdan muvaffaqiyatli o'tdingiz!*\n\n💰 Boshlang'ich 10 ball berildi!",
                     reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    add_ball(uid, 10)
    show_main_menu(uid)

# -----------------------------------------------------------------------
# 👤 PROFIL
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "👤 Profil")
def show_profile(message):
    uid = message.from_user.id
    ball = get_ball(uid)
    unvon = get_unvon(ball)
    keyingi_b, keyingi_n = keyingi_unvon(ball)

    conn = get_conn()
    jami_reja = conn.execute("SELECT COUNT(*) FROM daily_tasks WHERE user_id=?", (uid,)).fetchone()[0]
    bajarildi = conn.execute("SELECT COUNT(*) FROM daily_tasks WHERE user_id=? AND status=1", (uid,)).fetchone()[0]
    namoz_oq  = conn.execute("SELECT COUNT(*) FROM namoz_stats WHERE user_id=? AND holat='oqildi'", (uid,)).fetchone()[0]
    mukofot   = conn.execute("SELECT COUNT(*) FROM rewards WHERE user_id=?", (uid,)).fetchone()[0]
    conn.close()

    foiz = int(bajarildi / jami_reja * 100) if jami_reja else 0

    text = (f"👤 *PROFIL*\n\n"
            f"📛 Ism: {get_name(uid)}\n"
            f"{unvon}\n"
            f"💰 Ball: {ball}\n")
    if keyingi_b:
        text += f"⬆️ Keyingi unvon: {keyingi_n} ({keyingi_b - ball} ball qoldi)\n"
    text += (f"\n📊 *Statistika:*\n"
             f"📋 Jami reja: {jami_reja}\n"
             f"✅ Bajarildi: {bajarildi} ({foiz}%)\n"
             f"🕌 Namoz o'qildi: {namoz_oq}\n"
             f"🎁 Mukofotlar: {mukofot}\n")
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🕌 NAMOZ BO'LIMI
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🕌 Namoz")
def section_namoz(message):
    show_namoz_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "⏰ Namoz vaqtlarini kiritish")
def namoz_input(message):
    msg = bot.send_message(message.chat.id,
        "🕌 Namoz vaqtlarini *bo'sh joy* bilan yozing:\n"
        "*Bomdod Peshin Asr Shom Xufton*\n\n"
        "📌 Misol: `05:30 13:00 16:30 19:45 21:15`\n"
        "⚠️ *7 kun* davomida amal qiladi.",
        reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_save_namoz)

def step_save_namoz(message):
    uid = message.from_user.id
    parts = message.text.strip().split()
    if len(parts) != 5:
        bot.send_message(uid, "❌ Aynan 5 ta vaqt kiritilishi kerak!"); return
    for p in parts:
        try: datetime.strptime(p, "%H:%M")
        except:
            bot.send_message(uid, f"❌ `{p}` noto'g'ri! HH:MM formatda yozing.", parse_mode="Markdown"); return
    conn = get_conn()
    conn.execute("""INSERT OR REPLACE INTO namoz_times
        (user_id,bomdod,peshin,asr,shom,xufton,saved_at) VALUES (?,?,?,?,?,?,?)""",
        (uid, parts[0], parts[1], parts[2], parts[3], parts[4], today_str()))
    conn.commit(); conn.close()
    bot.send_message(uid,
        f"✅ *Namoz vaqtlari saqlandi (7 kun):*\n\n"
        f"☁️ Bomdod: `{parts[0]}`\n🌞 Peshin: `{parts[1]}`\n"
        f"🌤 Asr: `{parts[2]}`\n🌆 Shom: `{parts[3]}`\n🌃 Xufton: `{parts[4]}`",
        parse_mode="Markdown")
    add_ball(uid, 5)
    show_namoz_menu(message.chat.id)

# 🧭 QIBLA
@bot.message_handler(func=lambda m: m.text == "🧭 Qibla aniqlash")
def qibla_start(message):
    msg = bot.send_message(message.chat.id,
        "🧭 Shahar nomini yozing:\n"
        "📌 Misol: `Toshkent`, `Samarqand`, `London`",
        reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_qibla)

def step_qibla(message):
    uid = message.from_user.id
    city = message.text.strip()
    try:
        # Geocoding — shahar koordinatalarini olish
        city_encoded = urllib.parse.quote(city)
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city_encoded}&format=json&limit=1"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "ShaxsiyNazoratchiBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if not data:
            bot.send_message(uid, "❌ Shahar topilmadi. Qaytadan urinib ko'ring.")
            show_namoz_menu(message.chat.id); return

        lat = float(data[0]['lat'])
        lon = float(data[0]['lon'])
        display_name = data[0]['display_name'].split(',')[0]

        # Ka'ba koordinatalari
        kaba_lat = 21.4225
        kaba_lon = 39.8262

        # Qibla burchagini hisoblash
        lat1 = math.radians(lat)
        lat2 = math.radians(kaba_lat)
        dlon = math.radians(kaba_lon - lon)

        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(x, y))
        qibla = (bearing + 360) % 360

        # Yo'nalishni matn bilan ifodalash
        def direction_text(deg):
            dirs = ["Shimol ⬆️","Shimoli-sharq ↗️","Sharq ➡️","Janubi-sharq ↘️",
                    "Janub ⬇️","Janubi-g'arb ↙️","G'arb ⬅️","Shimoli-g'arb ↖️"]
            return dirs[round(deg / 45) % 8]

        bot.send_message(uid,
            f"🧭 *Qibla yo'nalishi*\n\n"
            f"📍 Shahar: *{display_name}*\n"
            f"🌐 Koordinata: {lat:.4f}, {lon:.4f}\n\n"
            f"🕋 Qibla burchagi: *{qibla:.1f}°*\n"
            f"🧭 Yo'nalish: *{direction_text(qibla)}*\n\n"
            f"_Kompas bilan {qibla:.0f}° ga qarating_",
            parse_mode="Markdown")
    except Exception as e:
        bot.send_message(uid, f"❌ Xatolik: {e}\nQaytadan urinib ko'ring.")
    show_namoz_menu(message.chat.id)

# Namoz statistikasi
@bot.message_handler(func=lambda m: m.text == "📊 Namoz statistikasi")
def namoz_stats_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📅 Kunlik",   callback_data="nstat_daily"),
        types.InlineKeyboardButton("📆 Haftalik", callback_data="nstat_weekly"),
        types.InlineKeyboardButton("🗓 Oylik",    callback_data="nstat_monthly"))
    bot.send_message(message.chat.id, "📊 *Namoz statistikasi:*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("nstat_"))
def cb_namoz_stats(call):
    uid = call.from_user.id
    period = call.data.split("_")[1]
    now = uz_time()
    if period == "daily":
        start = end = today_str(); title = f"Kunlik — {today_str()}"
    elif period == "weekly":
        start = (now - timedelta(days=6)).strftime("%Y-%m-%d"); end = today_str()
        title = f"Haftalik ({start} — {end})"
    else:
        start = now.strftime("%Y-%m-01"); end = today_str()
        title = f"Oylik — {now.strftime('%B %Y')}"

    conn = get_conn()
    rows = conn.execute(
        "SELECT namoz_nomi, holat, COUNT(*) as cnt FROM namoz_stats WHERE user_id=? AND sana>=? AND sana<=? GROUP BY namoz_nomi, holat",
        (uid, start, end)).fetchall()
    conn.close()
    bot.answer_callback_query(call.id)
    if not rows:
        bot.send_message(uid, f"📊 {title}\n\nHali ma'lumot yo'q."); return

    data = {}
    for row in rows:
        n = row['namoz_nomi']
        if n not in data: data[n] = {'oqildi':0,'endi_oqiyman':0,'qazo':0}
        data[n][row['holat']] = row['cnt']

    NAMOZLAR = ['Bomdod ☁️','Peshin 🌞','Asr 🌤','Shom 🌆','Xufton 🌃']
    text = f"📊 *Namoz statistikasi — {title}*\n\n"
    t_oq = t_endi = t_qazo = 0
    for n in NAMOZLAR:
        d = data.get(n, {'oqildi':0,'endi_oqiyman':0,'qazo':0})
        text += f"{n}:\n  ✅{d['oqildi']}  ⏳{d['endi_oqiyman']}  🔄{d['qazo']}\n"
        t_oq += d['oqildi']; t_endi += d['endi_oqiyman']; t_qazo += d['qazo']
    text += f"\n📌 *Jami:* ✅{t_oq}  ⏳{t_endi}  🔄{t_qazo}"
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("namoz_"))
def cb_namoz_answer(call):
    parts   = call.data.split("_", 3)
    holat   = parts[1]
    uid     = int(parts[2])
    nom_key = parts[3] if len(parts) > 3 else ""
    nom     = nom_key.replace("__", " ")
    conn = get_conn()
    conn.execute("INSERT INTO namoz_stats (user_id,namoz_nomi,sana,holat) VALUES (?,?,?,?)",
                 (uid, nom, today_str(), holat))
    conn.commit(); conn.close()
    if holat == "oqildi":
        text = f"✅ Barakalla! *{nom}* o'qildi!"; add_ball(uid, 10)
    elif holat == "endi_oqiyman":
        text = f"⏳ *{nom}* namozini o'qing!"; add_ball(uid, 3)
    else:
        text = f"🔄 *{nom}* qazo sifatida belgilandi."; add_ball(uid, 2)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    except:
        bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 📝 KUNLIK REJA
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "📝 Kunlik reja")
def section_kunlik(message):
    show_kunlik_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Reja qo'shish")
def daily_add(message):
    msg = bot.send_message(message.chat.id, "📝 Reja nomini yozing:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_daily_name)

def step_daily_name(message):
    msg = bot.send_message(message.chat.id, "⏰ Bajarish vaqti (HH:MM):\nMisol: `14:30`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_daily_time, message.text.strip())

def step_daily_time(message, task_name):
    uid = message.from_user.id
    t = message.text.strip()
    try: datetime.strptime(t, "%H:%M")
    except:
        msg = bot.send_message(uid, "❌ Vaqt noto'g'ri! HH:MM formatda:")
        bot.register_next_step_handler(msg, step_daily_time, task_name); return

    # Kategoriya tanlash
    markup = types.InlineKeyboardMarkup(row_width=2)
    for k in KATEGORIYALAR:
        markup.add(types.InlineKeyboardButton(k, callback_data=f"cat_{k}_{task_name}_{t}"))
    bot.send_message(uid, "📂 Kategoriyani tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def cb_category(call):
    parts    = call.data.split("_", 3)
    cat      = parts[1]
    task_name= parts[2]
    t        = parts[3]
    uid      = call.from_user.id

    # Muhimlik tanlash
    markup = types.InlineKeyboardMarkup(row_width=3)
    for label, val in MUHIMLIK.items():
        markup.add(types.InlineKeyboardButton(label, callback_data=f"pri_{val}_{cat}_{task_name}_{t}"))
    try: bot.edit_message_text("⚡ Muhimlik darajasini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except: bot.send_message(uid, "⚡ Muhimlik darajasini tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pri_"))
def cb_priority(call):
    parts     = call.data.split("_", 4)
    priority  = parts[1]
    cat       = parts[2]
    task_name = parts[3]
    t         = parts[4]
    uid       = call.from_user.id

    conn = get_conn()
    conn.execute(
        "INSERT INTO daily_tasks (user_id,task_name,task_time,sana,source,category,priority) VALUES (?,?,?,?,'daily',?,?)",
        (uid, task_name, t, today_str(), cat, priority))
    conn.commit(); conn.close()

    pri_icon = {"shoshilinch":"🔴","orta":"🟡","oddiy":"🟢"}.get(priority,"🟢")
    try:
        bot.edit_message_text(
            f"✅ Reja saqlandi!\n📌 *{task_name}*\n⏰ {t} | {cat} | {pri_icon}",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    except:
        bot.send_message(uid, f"✅ Reja saqlandi!\n📌 *{task_name}*\n⏰ {t} | {cat} | {pri_icon}",
                         parse_mode="Markdown")
    show_kunlik_menu(call.message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📋 Bugungi rejalar")
def view_daily(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute(
        "SELECT task_name,task_time,status,category,priority FROM daily_tasks WHERE user_id=? AND sana=? ORDER BY task_time",
        (uid, today_str())).fetchall()
    conn.close()
    if not rows:
        bot.send_message(uid, "📋 Bugun hali reja yo'q."); return
    text = f"📋 *Bugungi rejalar — {today_str()}:*\n\n"
    for i, row in enumerate(rows, 1):
        ico = "✅" if row['status']==1 else ("❌" if row['status']==0 else "⏳")
        pri = {"shoshilinch":"🔴","orta":"🟡","oddiy":"🟢"}.get(row['priority'],"🟢")
        text += f"{i}. {row['task_name']} — {row['task_time']}\n   {ico} {pri} {row['category']}\n"
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 📅 HAFTALIK REJA
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "📅 Haftalik reja")
def section_haftalik(message):
    show_haftalik_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Haftalik reja qo'shish")
def weekly_add(message):
    msg = bot.send_message(message.chat.id,
        "📅 Haftalik reja nomini yozing:\n_(Har kuni eslatiladi)_",
        reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_weekly_name)

def step_weekly_name(message):
    msg = bot.send_message(message.chat.id, "⏰ Har kuni eslatish vaqti (HH:MM):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_weekly_time, message.text.strip())

def step_weekly_time(message, task_name):
    uid = message.from_user.id; t = message.text.strip()
    try: datetime.strptime(t, "%H:%M")
    except:
        msg = bot.send_message(uid, "❌ HH:MM formatda yozing:")
        bot.register_next_step_handler(msg, step_weekly_time, task_name); return
    conn = get_conn()
    conn.execute("INSERT INTO weekly_tasks (user_id,task_name,task_time) VALUES (?,?,?)", (uid, task_name, t))
    conn.commit(); conn.close()
    bot.send_message(uid, f"✅ *{task_name}* — har kuni ⏰ {t} da eslatiladi!", parse_mode="Markdown")
    show_haftalik_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📋 Haftalik rejalarim")
def view_weekly(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute("SELECT id,task_name,task_time FROM weekly_tasks WHERE user_id=? AND active=1 ORDER BY task_time", (uid,)).fetchall()
    conn.close()
    if not rows:
        bot.send_message(uid, "📋 Haftalik rejalar yo'q."); return
    text = "📅 *HAFTALIK ASOSIY REJALAR:*\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row['task_name']} — ⏰ {row['task_time']}\n"
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.add(types.InlineKeyboardButton(f"🗑 {row['task_name']}", callback_data=f"del_weekly_{row['id']}"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_weekly_"))
def cb_del_weekly(call):
    wid = int(call.data.split("_")[2]); uid = call.from_user.id
    conn = get_conn()
    conn.execute("UPDATE weekly_tasks SET active=0 WHERE id=? AND user_id=?", (wid, uid))
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "✅ O'chirildi")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    bot.send_message(uid, "✅ Haftalik reja o'chirildi.")

# -----------------------------------------------------------------------
# 🎯 ODATLAR (HABIT TRACKER)
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🎯 Odatlar")
def section_habits(message):
    show_habits_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Odat qo'shish")
def habit_add(message):
    msg = bot.send_message(message.chat.id,
        "🎯 Odat nomini yozing:\nMisol: Suv ichish, Kitob o'qish, Yugurish",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_habit_name)

def step_habit_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    msg = bot.send_message(uid, "Emoji tanlang (1 ta emoji yozing yoki Enter bosing):\nMisol: 💧 📚 🏃 🧘")
    bot.register_next_step_handler(msg, step_habit_emoji, name)

def step_habit_emoji(message, name):
    uid = message.from_user.id
    emoji = message.text.strip() if message.text.strip() else "✅"
    conn = get_conn()
    conn.execute("INSERT INTO habits (user_id,name,emoji,created) VALUES (?,?,?,?)",
                 (uid, name, emoji, today_str()))
    conn.commit(); conn.close()
    bot.send_message(uid, f"✅ Odat qo'shildi: {emoji} *{name}*", parse_mode="Markdown")
    add_ball(uid, 5)
    show_habits_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📋 Odatlarim")
def view_habits(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute("SELECT id,name,emoji FROM habits WHERE user_id=? AND active=1", (uid,)).fetchall()
    conn.close()
    if not rows:
        bot.send_message(uid, "📋 Hali odat qo'shilmagan."); return
    text = "📋 *ODATLARIM:*\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row['emoji']} {row['name']}\n"
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.add(types.InlineKeyboardButton(f"🗑 {row['name']}", callback_data=f"del_habit_{row['id']}"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_habit_"))
def cb_del_habit(call):
    hid = int(call.data.split("_")[2]); uid = call.from_user.id
    conn = get_conn()
    conn.execute("UPDATE habits SET active=0 WHERE id=? AND user_id=?", (hid, uid))
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "✅ O'chirildi")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(func=lambda m: m.text == "✅ Bugungi odatlar")
def today_habits(message):
    uid = message.from_user.id
    conn = get_conn()
    habits = conn.execute("SELECT id,name,emoji FROM habits WHERE user_id=? AND active=1", (uid,)).fetchall()
    conn.close()
    if not habits:
        bot.send_message(uid, "📋 Hali odat qo'shilmagan."); return
    markup = types.InlineKeyboardMarkup(row_width=1)
    conn = get_conn()
    for h in habits:
        done = conn.execute("SELECT done FROM habit_logs WHERE habit_id=? AND sana=?", (h['id'], today_str())).fetchone()
        status = "✅" if (done and done['done']) else "⬜"
        markup.add(types.InlineKeyboardButton(
            f"{status} {h['emoji']} {h['name']}",
            callback_data=f"habit_toggle_{h['id']}"))
    conn.close()
    bot.send_message(uid, f"📅 *Bugungi odatlar — {today_str()}:*\nBajarilganini belgilang 👇",
                     reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("habit_toggle_"))
def cb_habit_toggle(call):
    hid = int(call.data.split("_")[2]); uid = call.from_user.id
    conn = get_conn()
    existing = conn.execute("SELECT id,done FROM habit_logs WHERE habit_id=? AND sana=?", (hid, today_str())).fetchone()
    if existing:
        new_done = 0 if existing['done'] else 1
        conn.execute("UPDATE habit_logs SET done=? WHERE id=?", (new_done, existing['id']))
        if new_done: add_ball(uid, 5)
    else:
        conn.execute("INSERT INTO habit_logs (habit_id,user_id,sana,done) VALUES (?,?,?,1)", (hid, uid, today_str()))
        add_ball(uid, 5)
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "✅ Yangilandi!")
    today_habits(call.message)

@bot.message_handler(func=lambda m: m.text == "📊 Odat statistikasi")
def habit_stats(message):
    uid = message.from_user.id
    now = uz_time()
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    conn = get_conn()
    habits = conn.execute("SELECT id,name,emoji FROM habits WHERE user_id=? AND active=1", (uid,)).fetchall()
    conn.close()
    if not habits:
        bot.send_message(uid, "Odat yo'q."); return
    text = f"📊 *Odat statistikasi (7 kun):*\n\n"
    for h in habits:
        conn = get_conn()
        done_cnt = conn.execute(
            "SELECT COUNT(*) FROM habit_logs WHERE habit_id=? AND sana>=? AND done=1", (h['id'], start)).fetchone()[0]
        conn.close()
        foiz = int(done_cnt / 7 * 100)
        bar = "█" * int(foiz / 10) + "░" * (10 - int(foiz / 10))
        text += f"{h['emoji']} *{h['name']}*\n  {bar} {foiz}% ({done_cnt}/7)\n\n"
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🏆 MAQSADLAR VA MUKOFOTLAR
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🏆 Maqsadlar")
def section_goals(message):
    show_goals_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Maqsad qo'shish")
def goal_add(message):
    msg = bot.send_message(message.chat.id,
        "🏆 Maqsad nomini yozing:\nMisol: 30 kun yugurish, Kitob o'qish",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_goal_title)

def step_goal_title(message):
    msg = bot.send_message(message.chat.id,
        "📅 Muddat (kun soni) kiriting:\nMisol: `30` yoki `7`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_goal_deadline, message.text.strip())

def step_goal_deadline(message, title):
    uid = message.from_user.id
    try: days = int(message.text.strip())
    except:
        bot.send_message(uid, "❌ Faqat raqam kiriting!"); return
    deadline = (uz_time() + timedelta(days=days)).strftime("%Y-%m-%d")
    msg = bot.send_message(uid, "🎁 Maqsad bajarilganda o'zingizga qanday mukofot berasiz?\nMisol: Yangi kitob sotib olaman, Kino ko'raman")
    bot.register_next_step_handler(msg, step_goal_reward, title, deadline)

def step_goal_reward(message, title, deadline):
    uid = message.from_user.id
    reward = message.text.strip()
    conn = get_conn()
    conn.execute("INSERT INTO goals (user_id,title,deadline,reward,created,ball_reward) VALUES (?,?,?,?,?,?)",
                 (uid, title, deadline, reward, today_str(), 100))
    conn.commit(); conn.close()
    bot.send_message(uid,
        f"✅ *Maqsad qo'shildi!*\n\n"
        f"🎯 *{title}*\n"
        f"📅 Muddat: {deadline}\n"
        f"🎁 Mukofot: {reward}\n"
        f"💰 Bajarilganda: +100 ball",
        parse_mode="Markdown")
    add_ball(uid, 10)
    show_goals_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📋 Maqsadlarim")
def view_goals(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute("SELECT id,title,deadline,reward,status FROM goals WHERE user_id=? ORDER BY deadline", (uid,)).fetchall()
    conn.close()
    if not rows:
        bot.send_message(uid, "📋 Maqsadlar yo'q."); return
    text = "🏆 *MAQSADLARIM:*\n\n"
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        ico = "✅" if row['status']=='done' else "🎯"
        text += f"{ico} *{row['title']}*\n  📅 {row['deadline']} | 🎁 {row['reward']}\n\n"
        if row['status'] == 'active':
            markup.add(types.InlineKeyboardButton(f"✅ '{row['title']}' bajarildi!", callback_data=f"goal_done_{row['id']}"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("goal_done_"))
def cb_goal_done(call):
    gid = int(call.data.split("_")[2]); uid = call.from_user.id
    conn = get_conn()
    goal = conn.execute("SELECT title,reward,ball_reward FROM goals WHERE id=?", (gid,)).fetchone()
    conn.execute("UPDATE goals SET status='done' WHERE id=?", (gid,))
    conn.commit(); conn.close()
    if goal:
        add_ball(uid, goal['ball_reward'])
        bot.answer_callback_query(call.id, "🎉 Tabriklaymiz!")
        bot.send_message(uid,
            f"🎉 *TABRIKLAYMIZ!*\n\n"
            f"✅ *{goal['title']}* maqsadini bajardingiz!\n"
            f"🎁 Mukofotingiz: {goal['reward']}\n"
            f"💰 +{goal['ball_reward']} ball qo'shildi!",
            parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎁 Mukofotlar")
def view_rewards(message):
    uid = message.from_user.id
    ball = get_ball(uid)
    conn = get_conn()
    rows = conn.execute("SELECT title,ball_cost,created FROM rewards WHERE user_id=? ORDER BY created DESC", (uid,)).fetchall()
    conn.close()
    text = f"🎁 *MUKOFOTLARIM*\n💰 Joriy ball: {ball}\n\n"
    if rows:
        text += "*Olgan mukofotlar:*\n"
        for row in rows:
            text += f"• {row['title']} — {row['ball_cost']} ball ({row['created']})\n"
    else:
        text += "Hali mukofot olmagansiz.\n"
    text += "\n_Ball yig'ib o'zingizga mukofot bering!_"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎁 O'zimga mukofot berish", callback_data="add_reward"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "add_reward")
def cb_add_reward(call):
    uid = call.from_user.id
    msg = bot.send_message(uid,
        f"🎁 O'zingizga qanday mukofot berasiz?\n"
        f"💰 Joriy ballingiz: {get_ball(uid)}\n\n"
        f"Mukofot nomini yozing:")
    bot.register_next_step_handler(msg, step_reward_name)

def step_reward_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    msg = bot.send_message(uid, f"Necha ball sarflaysiz? (Joriy: {get_ball(uid)} ball)")
    bot.register_next_step_handler(msg, step_reward_ball, name)

def step_reward_ball(message, name):
    uid = message.from_user.id
    try: cost = int(message.text.strip())
    except:
        bot.send_message(uid, "❌ Faqat raqam!"); return
    ball = get_ball(uid)
    if cost > ball:
        bot.send_message(uid, f"❌ Yetarli ball yo'q! Sizda {ball} ball bor."); return
    conn = get_conn()
    conn.execute("INSERT INTO rewards (user_id,title,ball_cost,created) VALUES (?,?,?,?)",
                 (uid, name, cost, today_str()))
    conn.execute("UPDATE users SET ball = ball - ? WHERE user_id=?", (cost, uid))
    conn.commit(); conn.close()
    bot.send_message(uid,
        f"🎉 *Mukofot berildi!*\n\n"
        f"🎁 {name}\n"
        f"💰 -{cost} ball sarflandi\n"
        f"💰 Qolgan ball: {ball - cost}",
        parse_mode="Markdown")
    show_goals_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "💰 Ballarim")
def show_balls(message):
    uid = message.from_user.id
    ball = get_ball(uid)
    unvon = get_unvon(ball)
    keyingi_b, keyingi_n = keyingi_unvon(ball)
    text = (f"💰 *BALL TIZIMI*\n\n"
            f"💰 Joriy ball: *{ball}*\n"
            f"🏅 Unvon: {unvon}\n")
    if keyingi_b:
        qoldi = keyingi_b - ball
        text += f"⬆️ Keyingi: {keyingi_n} ({qoldi} ball qoldi)\n"
    text += ("\n*Ball qanday yig'iladi:*\n"
             "✅ Namoz o'qildi: +10 ball\n"
             "⏳ Namoz endi: +3 ball\n"
             "📝 Reja bajarildi: +15 ball\n"
             "🎯 Odat bajarildi: +5 ball\n"
             "🏆 Maqsad bajarildi: +100 ball\n"
             "📅 Haftalik 100%: +50 ball\n")
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 📊 HISOBOTLAR
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "📊 Hisobotlar")
def section_hisobot(message):
    show_hisobot_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📈 Kunlik hisobot")
def h_kunlik(message):
    send_daily_report(message.from_user.id)

@bot.message_handler(func=lambda m: m.text == "📆 Haftalik hisobot")
def h_haftalik(message):
    send_weekly_report(message.from_user.id)

@bot.message_handler(func=lambda m: m.text == "🗓 Oylik hisobot")
def h_oylik(message):
    send_monthly_report(message.from_user.id)

@bot.message_handler(func=lambda m: m.text == "📉 Grafik")
def h_grafik(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📆 Haftalik",  callback_data="graf_weekly"),
        types.InlineKeyboardButton("🗓 Oylik",     callback_data="graf_monthly"))
    markup.row(types.InlineKeyboardButton("🕌 Namoz grafigi", callback_data="graf_namoz"))
    bot.send_message(message.chat.id, "📉 Grafik turini tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("graf_"))
def cb_grafik(call):
    uid = call.from_user.id
    gtype = call.data.split("_")[1]
    bot.answer_callback_query(call.id, "📊 Grafik tayyorlanmoqda...")
    if gtype == "weekly":
        send_weekly_chart(uid)
    elif gtype == "monthly":
        send_monthly_chart(uid)
    elif gtype == "namoz":
        send_namoz_chart(uid)

def send_weekly_chart(uid):
    now = uz_time()
    days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    conn = get_conn()
    text = "📊 *HAFTALIK REJA GRAFIGI*\n\n"
    for d in days:
        row = conn.execute(
            "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=?",
            (uid, d)).fetchone()
        j = row['j'] or 0; b = row['b'] or 0
        foiz = int(b/j*100) if j else 0
        filled = int(foiz/10); empty = 10-filled
        bar = "🟩"*filled + "⬜"*empty
        kun = datetime.strptime(d, "%Y-%m-%d").strftime("%d-%b")
        text += f"📅 {kun}\n{bar} {foiz}% ({b}/{j})\n\n"
    conn.close()
    bot.send_message(uid, text, parse_mode="Markdown")

def send_monthly_chart(uid):
    now = uz_time()
    text = "🗓 *OYLIK REJA GRAFIGI (4 hafta)*\n\n"
    conn = get_conn()
    for w in range(3, -1, -1):
        end_d   = (now - timedelta(days=w*7)).strftime("%Y-%m-%d")
        start_d = (now - timedelta(days=w*7+6)).strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana>=? AND sana<=?",
            (uid, start_d, end_d)).fetchone()
        j = row['j'] or 0; b = row['b'] or 0
        foiz = int(b/j*100) if j else 0
        filled = int(foiz/10); empty = 10-filled
        bar = "🟦"*filled + "⬜"*empty
        hafta = 4-w
        text += f"📆 {hafta}-hafta ({start_d[5:]} — {end_d[5:]})\n{bar} {foiz}% ({b}/{j})\n\n"
    conn.close()
    bot.send_message(uid, text, parse_mode="Markdown")

def send_namoz_chart(uid):
    now = uz_time()
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        "SELECT holat, COUNT(*) as cnt FROM namoz_stats WHERE user_id=? AND sana>=? GROUP BY holat",
        (uid, start)).fetchall()
    conn.close()
    d = {'oqildi':0,'endi_oqiyman':0,'qazo':0}
    for row in rows:
        d[row['holat']] = row['cnt']
    total = sum(d.values())
    if total == 0:
        bot.send_message(uid, "Namoz ma'lumoti yo'q.")
        return
    oq_f  = int(d['oqildi']/total*100) if total else 0
    en_f  = int(d['endi_oqiyman']/total*100) if total else 0
    qaz_f = int(d['qazo']/total*100) if total else 0
    text = "\U0001f54c *NAMOZ GRAFIGI (7 kun)*\n\n"
    text += f"\u2705 O'qildi:       " + "\U0001f7e9"*int(oq_f/10) + "\u2b1c"*(10-int(oq_f/10)) + f" {oq_f}% ({d['oqildi']} ta)\n\n"
    text += f"\u23f3 Endi o'qiyman: " + "\U0001f7e8"*int(en_f/10) + "\u2b1c"*(10-int(en_f/10)) + f" {en_f}% ({d['endi_oqiyman']} ta)\n\n"
    text += f"\U0001f504 Qazo:          " + "\U0001f7e5"*int(qaz_f/10) + "\u2b1c"*(10-int(qaz_f/10)) + f" {qaz_f}% ({d['qazo']} ta)\n\n"
    text += f"\U0001f4cc Jami: {total} ta namoz belgilandi"
    bot.send_message(uid, text, parse_mode="Markdown")

# Hisobot yordamchi funksiyalar
def _task_block(uid, start, end):
    conn = get_conn()
    rows = conn.execute(
        "SELECT sana, COUNT(*) as jami, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as bajardi FROM daily_tasks WHERE user_id=? AND sana>=? AND sana<=? GROUP BY sana ORDER BY sana",
        (uid, start, end)).fetchall()
    conn.close()
    return rows

def _namoz_block(uid, start, end):
    conn = get_conn()
    rows = conn.execute(
        "SELECT holat, COUNT(*) as cnt FROM namoz_stats WHERE user_id=? AND sana>=? AND sana<=? GROUP BY holat",
        (uid, start, end)).fetchall()
    conn.close()
    return {r['holat']: r['cnt'] for r in rows}

def send_daily_report(uid):
    start = end = today_str()
    task_rows = _task_block(uid, start, end)
    namoz_d   = _namoz_block(uid, start, end)
    text = f"📈 *KUNLIK HISOBOT — {today_str()}*\n\n"

    # Eng ko'p/kam kategoriya
    conn = get_conn()
    cat_rows = conn.execute(
        "SELECT category, COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=? GROUP BY category",
        (uid, today_str())).fetchall()
    conn.close()

    text += "📋 *Rejalar:*\n"
    if task_rows:
        row = task_rows[0]
        b = row['bajardi'] or 0; j = row['jami']
        f = int(b/j*100) if j else 0
        text += f"  ✅ {b}/{j} ({f}%)\n"
        bar = "█"*int(f/10) + "░"*(10-int(f/10))
        text += f"  [{bar}]\n"
        if cat_rows:
            text += "\n📂 *Kategoriyalar:*\n"
            for cr in cat_rows:
                cb = cr['b'] or 0; cj = cr['j']
                cf = int(cb/cj*100) if cj else 0
                text += f"  {cr['category']}: {cb}/{cj} ({cf}%)\n"
    else:
        text += "  Bugun reja yo'q.\n"

    text += "\n🕌 *Namoz:*\n"
    if namoz_d:
        text += f"  ✅ O'qildi: {namoz_d.get('oqildi',0)}\n"
        text += f"  ⏳ Endi: {namoz_d.get('endi_oqiyman',0)}\n"
        text += f"  🔄 Qazo: {namoz_d.get('qazo',0)}\n"
    else:
        text += "  Ma'lumot yo'q.\n"

    text += f"\n{get_motivatsiya()}"
    bot.send_message(uid, text, parse_mode="Markdown")

def send_weekly_report(uid):
    now = uz_time()
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d"); end = today_str()
    task_rows = _task_block(uid, start, end); namoz_d = _namoz_block(uid, start, end)
    text = f"📆 *HAFTALIK HISOBOT*\n_{start} — {end}_\n\n"

    text += "📋 *Rejalar (kunlar bo'yicha):*\n"
    t_b = t_j = 0
    if task_rows:
        for row in task_rows:
            b = row['bajardi'] or 0; j = row['jami']
            f = int(b/j*100) if j else 0
            bar = "█"*int(f/10) + "░"*(10-int(f/10))
            text += f"  {row['sana'][5:]}: [{bar}] {b}/{j}\n"
            t_b += b; t_j += j
        umumiy = int(t_b/t_j*100) if t_j else 0
        text += f"\n  ✨ *Umumiy: {t_b}/{t_j} ({umumiy}%)*\n"
        if umumiy == 100:
            add_ball(uid, 50)
            text += "  🏆 *100% — +50 ball!*\n"
    else:
        text += "  Ma'lumot yo'q.\n"

    text += "\n🕌 *Namoz:*\n"
    if namoz_d:
        jami_n = sum(namoz_d.values()); oq = namoz_d.get('oqildi',0)
        foiz_n = int(oq/jami_n*100) if jami_n else 0
        text += f"  ✅ O'qildi: {oq} | ⏳ {namoz_d.get('endi_oqiyman',0)} | 🔄 {namoz_d.get('qazo',0)}\n"
        text += f"  📌 O'qish foizi: {foiz_n}%\n"
    else:
        text += "  Ma'lumot yo'q.\n"
    bot.send_message(uid, text, parse_mode="Markdown")

def send_monthly_report(uid):
    now = uz_time()
    start = now.strftime("%Y-%m-01"); end = today_str()
    task_rows = _task_block(uid, start, end); namoz_d = _namoz_block(uid, start, end)
    text = f"🗓 *OYLIK HISOBOT — {now.strftime('%B %Y')}*\n_{start} — {end}_\n\n"
    t_b = sum((r['bajardi'] or 0) for r in task_rows)
    t_j = sum(r['jami'] for r in task_rows)
    foiz = int(t_b/t_j*100) if t_j else 0
    text += f"📋 *Rejalar:* {t_b}/{t_j} ({foiz}%)\n"

    # Eng yaxshi kun
    if task_rows:
        best = max(task_rows, key=lambda r: (r['bajardi'] or 0)/r['jami'] if r['jami'] else 0)
        worst= min(task_rows, key=lambda r: (r['bajardi'] or 0)/r['jami'] if r['jami'] else 1)
        text += f"  🌟 Eng yaxshi kun: {best['sana']}\n"
        text += f"  📉 Eng kam kun: {worst['sana']}\n"

    text += "\n🕌 *Namoz:*\n"
    if namoz_d:
        jami_n = sum(namoz_d.values()); oq = namoz_d.get('oqildi',0)
        foiz_n = int(oq/jami_n*100) if jami_n else 0
        text += f"  ✅ O'qildi: {oq} ({foiz_n}%)\n"
        text += f"  ⏳ Endi: {namoz_d.get('endi_oqiyman',0)} | 🔄 Qazo: {namoz_d.get('qazo',0)}\n"
    else:
        text += "  Ma'lumot yo'q.\n"
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🔙 ORQAGA
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🔙 Orqaga")
def back_main(message):
    show_main_menu(message.chat.id, message.from_user.id)

# -----------------------------------------------------------------------
# ✅ VAZIFA JAVOBLARI
# -----------------------------------------------------------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("done_") or c.data.startswith("not_"))
def cb_task_answer(call):
    parts = call.data.split("_")
    action = parts[0]; uid = int(parts[1]); tid = int(parts[2])
    status = 1 if action == "done" else 0
    conn = get_conn()
    conn.execute("UPDATE daily_tasks SET status=? WHERE id=?", (status, tid))
    conn.commit(); conn.close()
    if action == "done":
        add_ball(uid, 15)
        text = "✅ Zo'r! Vazifa bajarildi. +15 ball! 💰"
    else:
        text = "❌ Vazifa bajarilmadi. Ertaga urinib ko'ring!"
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except: bot.send_message(uid, text)

# -----------------------------------------------------------------------
# ⏰ TAYMER
# -----------------------------------------------------------------------
def schedule_checker():
    last_minute = ""
    while True:
        try:
            now = uz_time(); current_time = now.strftime("%H:%M")
            if current_time == last_minute:
                time.sleep(5); continue
            last_minute = current_time
            conn = get_conn()

            # 1. NAMOZ ESLATMALARI
            namoz_rows = conn.execute("SELECT user_id,bomdod,peshin,asr,shom,xufton,saved_at FROM namoz_times").fetchall()
            for nrow in namoz_rows:
                uid = nrow['user_id']
                saved = datetime.strptime(nrow['saved_at'], "%Y-%m-%d")
                if (now.date() - saved.date()).days >= 7:
                    try:
                        bot.send_message(uid, "⚠️ *Namoz vaqtlaringiz muddati tugadi!*\nYangilang: *⏰ Namoz vaqtlarini kiritish*", parse_mode="Markdown")
                    except: pass
                    conn.execute("DELETE FROM namoz_times WHERE user_id=?", (uid,))
                    conn.commit(); continue
                NAMOZ_MAP = {'Bomdod ☁️':nrow['bomdod'],'Peshin 🌞':nrow['peshin'],'Asr 🌤':nrow['asr'],'Shom 🌆':nrow['shom'],'Xufton 🌃':nrow['xufton']}
                for nom, vaqt in NAMOZ_MAP.items():
                    if vaqt == current_time:
                        try:
                            bot.send_message(uid, f"🕌 *Namoz vaqti: {nom}*\n⏰ {vaqt}", parse_mode="Markdown")
                            conn.execute("INSERT INTO namoz_notify (user_id,namoz_nomi,notified_at) VALUES (?,?,?)", (uid, nom, time.time()))
                            conn.commit()
                        except: pass

            # 2. NAMOZ 20 DAQIQA
            notify_rows = conn.execute("SELECT id,user_id,namoz_nomi FROM namoz_notify WHERE asked=0 AND notified_at<?", (time.time()-20*60,)).fetchall()
            for nr in notify_rows:
                uid = nr['user_id']; nom = nr['namoz_nomi']
                nom_key = nom.replace(" ", "__")
                try:
                    markup = types.InlineKeyboardMarkup()
                    markup.row(
                        types.InlineKeyboardButton("✅ Ha, o'qidim", callback_data=f"namoz_oqildi_{uid}_{nom_key}"),
                        types.InlineKeyboardButton("⏳ Endi o'qiyman", callback_data=f"namoz_endi_oqiyman_{uid}_{nom_key}"))
                    markup.row(types.InlineKeyboardButton("🔄 Qazo o'qiyman", callback_data=f"namoz_qazo_{uid}_{nom_key}"))
                    bot.send_message(uid, f"🕌 *{nom}* namozini o'qidingizmi?", reply_markup=markup, parse_mode="Markdown")
                    conn.execute("UPDATE namoz_notify SET asked=1 WHERE id=?", (nr['id'],))
                    conn.commit()
                except: pass

            # 3. KUNLIK REJA ESLATMALARI
            daily_remind = conn.execute(
                "SELECT id,user_id,task_name,priority FROM daily_tasks WHERE sana=? AND task_time=? AND notified=0",
                (today_str(), current_time)).fetchall()
            for dr in daily_remind:
                pri_icon = {"shoshilinch":"🔴","orta":"🟡","oddiy":"🟢"}.get(dr['priority'],"🟢")
                try:
                    bot.send_message(dr['user_id'], f"🔔 *Eslatma!* {pri_icon}\n📌 {dr['task_name']} vaqti bo'ldi!", parse_mode="Markdown")
                    conn.execute("UPDATE daily_tasks SET notified=1, notified_at=? WHERE id=?", (time.time(), dr['id']))
                    conn.commit()
                except: pass

            # 4. HAFTALIK REJA ESLATMALARI
            weekly_rows = conn.execute("SELECT user_id,task_name,task_time FROM weekly_tasks WHERE active=1 AND task_time=?", (current_time,)).fetchall()
            for wr in weekly_rows:
                uid = wr['user_id']; wname = wr['task_name']; wtime = wr['task_time']
                existing = conn.execute("SELECT id FROM daily_tasks WHERE user_id=? AND task_name=? AND sana=? AND source='weekly'", (uid, wname, today_str())).fetchone()
                if not existing:
                    conn.execute("INSERT INTO daily_tasks (user_id,task_name,task_time,sana,source,notified,notified_at) VALUES (?,?,?,?,'weekly',1,?)", (uid, wname, wtime, today_str(), time.time()))
                    conn.commit()
                try: bot.send_message(uid, f"📅 *Haftalik reja:*\n📌 {wname}", parse_mode="Markdown")
                except: pass

            # 5. 45 DAQIQA TEKSHIRUVI
            check_45 = conn.execute(
                "SELECT id,user_id,task_name FROM daily_tasks WHERE sana=? AND notified=1 AND verified=0 AND status IS NULL AND notified_at<?",
                (today_str(), time.time()-45*60)).fetchall()
            for cr in check_45:
                try:
                    markup = types.InlineKeyboardMarkup()
                    markup.row(
                        types.InlineKeyboardButton("✅ Ha, bajardim", callback_data=f"done_{cr['user_id']}_{cr['id']}"),
                        types.InlineKeyboardButton("❌ Yo'q", callback_data=f"not_{cr['user_id']}_{cr['id']}"))
                    bot.send_message(cr['user_id'], f"❓ 45 daqiqa o'tdi.\n*'{cr['task_name']}'* bajarildimi?", reply_markup=markup, parse_mode="Markdown")
                    conn.execute("UPDATE daily_tasks SET verified=1 WHERE id=?", (cr['id'],))
                    conn.commit()
                except: pass

            # 6. AVTOMATIK HISOBOTLAR
            all_users = conn.execute("SELECT user_id FROM users WHERE registered=1").fetchall()
            if current_time == "22:00":
                for u in all_users:
                    try: send_daily_report(u['user_id'])
                    except: pass
            if current_time == "21:00" and now.weekday() == 6:
                for u in all_users:
                    try: send_weekly_report(u['user_id'])
                    except: pass
            tomorrow = now + timedelta(days=1)
            if current_time == "21:30" and tomorrow.month != now.month:
                for u in all_users:
                    try: send_monthly_report(u['user_id'])
                    except: pass

            conn.close()
            time.sleep(5)
        except Exception as e:
            print(f"[TAYMER] {e}")
            time.sleep(10)

# -----------------------------------------------------------------------
# 🌐 KEEPALIVE SERVER (Railway uchun — bot uxlamasligi uchun)
# -----------------------------------------------------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")
    def log_message(self, format, *args):
        pass  # Logni jim qilish

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# -----------------------------------------------------------------------
# 🎬 ISHGA TUSHIRISH
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print("✅ Bot ishga tushdi (UTC+5)")

    # Health check server — Railway uchun
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print("🌐 Health server ishga tushdi")

    # Taymer
    t = threading.Thread(target=schedule_checker, daemon=True)
    t.start()

    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            print(f"[POLLING] {e}")
            time.sleep(10)

