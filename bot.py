import os
import telebot
from telebot import types
import threading
import time
from datetime import datetime, timedelta
import sqlite3

# -----------------------------------------------------------------------
# ⚙️ SOZLAMALAR — Render'da Environment Variable sifatida qo'ying
# -----------------------------------------------------------------------
API_TOKEN = os.environ.get('BOT_TOKEN', '8239336439:AAEsMwnWliN6vWhErJ6YEsup7KxY5DctAp0')
KANAL_ID  = os.environ.get('KANAL_ID', '@shaxsiy_nazoratchi')
KANAL_LINKI = os.environ.get('KANAL_LINKI', 'https://t.me/shaxsiy_nazoratchi')

# SQLite fayl yo'li — Render persistent disk uchun
DB_PATH = os.environ.get('DB_PATH', 'bot_data.db')

bot = telebot.TeleBot(API_TOKEN, parse_mode=None)

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
        user_id   INTEGER PRIMARY KEY,
        name      TEXT    NOT NULL,
        phone     TEXT    DEFAULT '',
        registered INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS namoz_times (
        user_id  INTEGER PRIMARY KEY,
        bomdod   TEXT,
        peshin   TEXT,
        asr      TEXT,
        shom     TEXT,
        xufton   TEXT,
        saved_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS namoz_notify (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        namoz_nomi   TEXT,
        notified_at  REAL,
        asked        INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS namoz_stats (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        namoz_nomi  TEXT,
        sana        TEXT,
        holat       TEXT
    )''')

    # Kunlik rejalar (1 kun uchun)
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
        source      TEXT    DEFAULT "daily"
    )''')

    # Haftalik asosiy rejalar (har kuni takrorlanadi)
    c.execute('''CREATE TABLE IF NOT EXISTS weekly_tasks (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        task_name TEXT,
        task_time TEXT,
        active    INTEGER DEFAULT 1
    )''')

    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------
# 🔧 YORDAMCHI FUNKSIYALAR
# -----------------------------------------------------------------------
def uz_time():
    """UTC+5 — O'zbekiston vaqti"""
    return datetime.utcnow() + timedelta(hours=5)

def today_str():
    return uz_time().strftime("%Y-%m-%d")

def is_registered(user_id):
    conn = get_conn()
    row = conn.execute("SELECT registered FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return bool(row and row['registered'])

def get_name(user_id):
    conn = get_conn()
    row = conn.execute("SELECT name FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row['name'] if row else "Foydalanuvchi"

def namoz_active(user_id):
    """Namoz vaqtlari 7 kun amal qiladimi?"""
    conn = get_conn()
    row = conn.execute("SELECT saved_at FROM namoz_times WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return False
    saved = datetime.strptime(row['saved_at'], "%Y-%m-%d")
    return (uz_time().date() - saved.date()).days < 7

# -----------------------------------------------------------------------
# 📋 MENYULAR
# -----------------------------------------------------------------------
def show_main_menu(chat_id, user_id=None):
    if user_id is None:
        user_id = chat_id
    name = get_name(user_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("📝 Kunlik reja"),
        types.KeyboardButton("📅 Haftalik reja")
    )
    markup.row(
        types.KeyboardButton("🕌 Namoz"),
        types.KeyboardButton("📊 Hisobotlar")
    )
    bot.send_message(chat_id,
        f"Assalomu alaykum, *{name}*! Bo'limni tanlang 👇",
        reply_markup=markup, parse_mode="Markdown")

def show_namoz_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("⏰ Namoz vaqtlarini kiritish"))
    markup.row(types.KeyboardButton("📊 Namoz statistikasi"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "🕌 *Namoz bo'limi:*",
                     reply_markup=markup, parse_mode="Markdown")

def show_kunlik_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("➕ Reja qo'shish"),
        types.KeyboardButton("📋 Bugungi rejalar")
    )
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "📝 *Kunlik reja bo'limi:*",
                     reply_markup=markup, parse_mode="Markdown")

def show_haftalik_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("➕ Haftalik reja qo'shish"),
        types.KeyboardButton("📋 Haftalik rejalarim")
    )
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id,
        "📅 *Haftalik reja bo'limi*\n"
        "_Bu yerga kiritilgan rejalar har kuni o'sha vaqtda eslatiladi._",
        reply_markup=markup, parse_mode="Markdown")

def show_hisobot_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("📈 Kunlik hisobot"),
        types.KeyboardButton("📆 Haftalik hisobot")
    )
    markup.row(types.KeyboardButton("🗓 Oylik hisobot"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "📊 *Hisobotlar bo'limi:*",
                     reply_markup=markup, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🚀 START VA A'ZOLIK TEKSHIRUVI
# -----------------------------------------------------------------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    bot.send_message(uid,
        "Assalomu alaykum! 👋\n*SHAXSIY NAZORATCHI* botiga xush kelibsiz!\n\n"
        "Bu bot sizga:\n"
        "✅ Kunlik va haftalik rejalarni boshqarishga\n"
        "🕌 Namoz vaqtlarini kuzatishga\n"
        "📊 Shaxsiy statistika yuritishga yordam beradi.",
        parse_mode="Markdown")
    check_subscription(message)

def check_subscription(message):
    uid = message.from_user.id
    try:
        status = bot.get_chat_member(KANAL_ID, uid).status
        subscribed = status in ['member', 'administrator', 'creator']
    except:
        subscribed = True  # Bot admin bo'lmasa tekshirmasdan o'tkazamiz

    if subscribed:
        if is_registered(uid):
            show_main_menu(uid)
        else:
            ask_name(message)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "📢 Kanalga a'zo bo'lish", url=KANAL_LINKI))
        markup.add(types.InlineKeyboardButton(
            "✅ A'zo bo'ldim", callback_data="check_sub"))
        bot.send_message(uid,
            "⚠️ Botdan foydalanish uchun avval kanalga a'zo bo'ling:",
            reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def cb_check_sub(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    check_subscription(call.message)

# -----------------------------------------------------------------------
# 📝 RO'YXATDAN O'TISH
# -----------------------------------------------------------------------
def ask_name(message):
    msg = bot.send_message(message.chat.id,
        "Ismingizni kiriting:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_save_name)

def step_save_name(message):
    uid = message.from_user.id
    name = message.text.strip()
    if not name or len(name) > 50:
        msg = bot.send_message(uid, "❌ Ism noto'g'ri. Qaytadan kiriting:")
        bot.register_next_step_handler(msg, step_save_name)
        return
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO users (user_id, name, registered) VALUES (?,?,0)",
        (uid, name))
    conn.commit()
    conn.close()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True))
    msg = bot.send_message(uid,
        f"Rahmat, *{name}*! Telefon raqamingizni yuboring 👇",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_save_phone)

def step_save_phone(message):
    uid = message.from_user.id
    phone = message.contact.phone_number if message.contact else message.text.strip()
    conn = get_conn()
    conn.execute("UPDATE users SET phone=?, registered=1 WHERE user_id=?", (phone, uid))
    conn.commit()
    conn.close()
    bot.send_message(uid,
        "✅ *Ro'yxatdan muvaffaqiyatli o'tdingiz!*",
        reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    show_main_menu(uid)

# -----------------------------------------------------------------------
# 🕌 NAMOZ BO'LIMI
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🕌 Namoz")
def section_namoz(message):
    show_namoz_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "⏰ Namoz vaqtlarini kiritish")
def namoz_input_start(message):
    msg = bot.send_message(message.chat.id,
        "🕌 Namoz vaqtlarini *bo'sh joy* bilan ajratib yozing:\n"
        "*Bomdod Peshin Asr Shom Xufton*\n\n"
        "📌 Misol: `05:30 13:00 16:30 19:45 21:15`\n\n"
        "⚠️ Bu vaqtlar *7 kun* davomida amal qiladi.",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_save_namoz)

def step_save_namoz(message):
    uid = message.from_user.id
    parts = message.text.strip().split()
    if len(parts) != 5:
        bot.send_message(uid, "❌ Aynan 5 ta vaqt kiritilishi kerak! Qaytadan urinib ko'ring.")
        return
    for p in parts:
        try:
            datetime.strptime(p, "%H:%M")
        except ValueError:
            bot.send_message(uid, f"❌ `{p}` noto'g'ri format! HH:MM ko'rinishida yozing.",
                             parse_mode="Markdown")
            return
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO namoz_times
           (user_id, bomdod, peshin, asr, shom, xufton, saved_at)
           VALUES (?,?,?,?,?,?,?)""",
        (uid, parts[0], parts[1], parts[2], parts[3], parts[4], today_str()))
    conn.commit()
    conn.close()
    bot.send_message(uid,
        f"✅ *Namoz vaqtlari saqlandi (7 kun):*\n\n"
        f"☁️ Bomdod: `{parts[0]}`\n"
        f"🌞 Peshin:  `{parts[1]}`\n"
        f"🌤 Asr:     `{parts[2]}`\n"
        f"🌆 Shom:    `{parts[3]}`\n"
        f"🌃 Xufton:  `{parts[4]}`",
        parse_mode="Markdown")
    show_namoz_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📊 Namoz statistikasi")
def namoz_stats_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📅 Kunlik",   callback_data="nstat_daily"),
        types.InlineKeyboardButton("📆 Haftalik", callback_data="nstat_weekly"),
        types.InlineKeyboardButton("🗓 Oylik",    callback_data="nstat_monthly")
    )
    bot.send_message(message.chat.id,
        "📊 *Namoz statistikasi* — davrni tanlang:",
        reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("nstat_"))
def cb_namoz_stats(call):
    uid = call.from_user.id
    period = call.data.split("_")[1]
    now = uz_time()

    if period == "daily":
        start = end = today_str()
        title = f"Kunlik — {today_str()}"
    elif period == "weekly":
        start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
        end   = today_str()
        title = f"Haftalik ({start} — {end})"
    else:
        start = now.strftime("%Y-%m-01")
        end   = today_str()
        title = f"Oylik — {now.strftime('%B %Y')}"

    conn = get_conn()
    rows = conn.execute(
        """SELECT namoz_nomi, holat, COUNT(*) as cnt
           FROM namoz_stats
           WHERE user_id=? AND sana>=? AND sana<=?
           GROUP BY namoz_nomi, holat""",
        (uid, start, end)).fetchall()
    conn.close()

    bot.answer_callback_query(call.id)

    if not rows:
        bot.send_message(uid, f"📊 {title}\n\nHali ma'lumot yo'q.")
        return

    # Tuzilish
    data = {}
    for row in rows:
        n = row['namoz_nomi']
        if n not in data:
            data[n] = {'oqildi': 0, 'endi_oqiyman': 0, 'qazo': 0}
        data[n][row['holat']] = row['cnt']

    NAMOZLAR = ['Bomdod ☁️', 'Peshin 🌞', 'Asr 🌤', 'Shom 🌆', 'Xufton 🌃']
    text  = f"📊 *Namoz statistikasi — {title}*\n\n"
    t_oq = t_endi = t_qazo = 0

    for n in NAMOZLAR:
        d = data.get(n, {'oqildi': 0, 'endi_oqiyman': 0, 'qazo': 0})
        text += (f"{n}:\n"
                 f"  ✅ O'qildi: {d['oqildi']}  "
                 f"⏳ Endi: {d['endi_oqiyman']}  "
                 f"🔄 Qazo: {d['qazo']}\n")
        t_oq   += d['oqildi']
        t_endi += d['endi_oqiyman']
        t_qazo += d['qazo']

    text += (f"\n📌 *Jami:*  ✅ {t_oq}  ⏳ {t_endi}  🔄 Qazo: {t_qazo}")
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("namoz_"))
def cb_namoz_answer(call):
    # format: namoz_{holat}_{user_id}_{nom_key}
    parts = call.data.split("_", 3)
    holat   = parts[1]
    uid     = int(parts[2])
    nom_key = parts[3] if len(parts) > 3 else ""
    nom     = nom_key.replace("__", " ")

    conn = get_conn()
    conn.execute(
        "INSERT INTO namoz_stats (user_id, namoz_nomi, sana, holat) VALUES (?,?,?,?)",
        (uid, nom, today_str(), holat))
    conn.commit()
    conn.close()

    if holat == "oqildi":
        text = f"✅ Barakalla! *{nom}* namozi o'qildi. Allah qabul qilsin!"
    elif holat == "endi_oqiyman":
        text = f"⏳ Yaxshi, *{nom}* namozini o'qing. Kech qolmang!"
    else:
        text = f"🔄 *{nom}* — qazo sifatida belgilandi."

    try:
        bot.edit_message_text(text, call.message.chat.id,
                              call.message.message_id, parse_mode="Markdown")
    except:
        bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 📝 KUNLIK REJA BO'LIMI
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "📝 Kunlik reja")
def section_kunlik(message):
    show_kunlik_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Reja qo'shish")
def daily_add_start(message):
    msg = bot.send_message(message.chat.id,
        "📝 Reja nomini yozing:",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_daily_name)

def step_daily_name(message):
    msg = bot.send_message(message.chat.id,
        "⏰ Bajarish vaqtini yozing (HH:MM format):\nMisol: `14:30`",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_daily_time, message.text.strip())

def step_daily_time(message, task_name):
    uid = message.from_user.id
    task_time = message.text.strip()
    try:
        datetime.strptime(task_time, "%H:%M")
    except ValueError:
        msg = bot.send_message(uid,
            "❌ Vaqt noto'g'ri! `HH:MM` formatda yozing:",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_daily_time, task_name)
        return
    conn = get_conn()
    conn.execute(
        "INSERT INTO daily_tasks (user_id, task_name, task_time, sana, source) VALUES (?,?,?,?,'daily')",
        (uid, task_name, task_time, today_str()))
    conn.commit()
    conn.close()
    bot.send_message(uid,
        f"✅ Reja saqlandi!\n📌 *{task_name}* — ⏰ {task_time}",
        parse_mode="Markdown")
    show_kunlik_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📋 Bugungi rejalar")
def view_daily(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute(
        """SELECT task_name, task_time, status FROM daily_tasks
           WHERE user_id=? AND sana=? ORDER BY task_time""",
        (uid, today_str())).fetchall()
    conn.close()

    if not rows:
        bot.send_message(uid, "📋 Bugun hali reja yo'q.")
        return

    text = f"📋 *Bugungi rejalar — {today_str()}:*\n\n"
    for i, row in enumerate(rows, 1):
        if row['status'] == 1:
            icon = "✅"
        elif row['status'] == 0:
            icon = "❌"
        else:
            icon = "⏳"
        text += f"{i}. {row['task_name']} — {row['task_time']} {icon}\n"
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 📅 HAFTALIK ASOSIY REJA BO'LIMI
# -----------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "📅 Haftalik reja")
def section_haftalik(message):
    show_haftalik_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Haftalik reja qo'shish")
def weekly_add_start(message):
    msg = bot.send_message(message.chat.id,
        "📅 Haftalik reja nomini yozing:\n_(Bu reja har kuni eslatiladi)_",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_weekly_name)

def step_weekly_name(message):
    msg = bot.send_message(message.chat.id,
        "⏰ Har kuni eslatish vaqtini yozing (HH:MM):\nMisol: `07:00`",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_weekly_time, message.text.strip())

def step_weekly_time(message, task_name):
    uid = message.from_user.id
    task_time = message.text.strip()
    try:
        datetime.strptime(task_time, "%H:%M")
    except ValueError:
        msg = bot.send_message(uid,
            "❌ Vaqt noto'g'ri! `HH:MM` formatda yozing:",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_weekly_time, task_name)
        return
    conn = get_conn()
    conn.execute(
        "INSERT INTO weekly_tasks (user_id, task_name, task_time) VALUES (?,?,?)",
        (uid, task_name, task_time))
    conn.commit()
    conn.close()
    bot.send_message(uid,
        f"✅ Haftalik reja saqlandi!\n"
        f"📌 *{task_name}* — har kuni ⏰ {task_time} da eslatiladi.",
        parse_mode="Markdown")
    show_haftalik_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "📋 Haftalik rejalarim")
def view_weekly(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, task_name, task_time FROM weekly_tasks WHERE user_id=? AND active=1 ORDER BY task_time",
        (uid,)).fetchall()
    conn.close()

    if not rows:
        bot.send_message(uid,
            "📋 Haftalik rejalar yo'q.\n"
            "Qo'shish uchun *➕ Haftalik reja qo'shish* tugmasini bosing.",
            parse_mode="Markdown")
        return

    text = "📅 *HAFTALIK ASOSIY REJALAR:*\n_(Har kuni eslatiladi)_\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row['task_name']} — ⏰ {row['task_time']}\n"

    # O'chirish tugmalari
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.add(types.InlineKeyboardButton(
            f"🗑 {row['task_name']} ni o'chirish",
            callback_data=f"del_weekly_{row['id']}"))

    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_weekly_"))
def cb_del_weekly(call):
    wid = int(call.data.split("_")[2])
    uid = call.from_user.id
    conn = get_conn()
    conn.execute("UPDATE weekly_tasks SET active=0 WHERE id=? AND user_id=?", (wid, uid))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "✅ O'chirildi")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    bot.send_message(uid, "✅ Haftalik reja o'chirildi.")

# -----------------------------------------------------------------------
# 📊 HISOBOTLAR BO'LIMI
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

# ─── HISOBOT FUNKSIYALARI ───────────────────────────────────────────────

def _task_block(uid, start, end):
    """Belgilangan sana oralig'idagi reja bloki."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT sana,
                  COUNT(*) as jami,
                  SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as bajardi
           FROM daily_tasks
           WHERE user_id=? AND sana>=? AND sana<=?
           GROUP BY sana ORDER BY sana""",
        (uid, start, end)).fetchall()
    conn.close()
    return rows

def _namoz_block(uid, start, end):
    conn = get_conn()
    rows = conn.execute(
        """SELECT holat, COUNT(*) as cnt FROM namoz_stats
           WHERE user_id=? AND sana>=? AND sana<=?
           GROUP BY holat""",
        (uid, start, end)).fetchall()
    conn.close()
    return {r['holat']: r['cnt'] for r in rows}

def send_daily_report(uid):
    start = end = today_str()
    task_rows = _task_block(uid, start, end)
    namoz_d   = _namoz_block(uid, start, end)

    text = f"📈 *KUNLIK HISOBOT — {today_str()}*\n\n"

    # Rejalar
    text += "📋 *Rejalar:*\n"
    if task_rows:
        row = task_rows[0]
        bajardi = row['bajardi'] or 0
        jami    = row['jami']
        foiz    = int(bajardi / jami * 100) if jami else 0
        text += f"  ✅ Bajarildi: {bajardi}/{jami}  ({foiz}%)\n"

        conn = get_conn()
        tasks = conn.execute(
            "SELECT task_name, task_time, status FROM daily_tasks WHERE user_id=? AND sana=? ORDER BY task_time",
            (uid, today_str())).fetchall()
        conn.close()
        for t in tasks:
            ico = "✅" if t['status'] == 1 else ("❌" if t['status'] == 0 else "⏳")
            text += f"  {ico} {t['task_name']} — {t['task_time']}\n"
    else:
        text += "  Bugun reja yo'q.\n"

    # Namoz
    text += "\n🕌 *Namoz:*\n"
    if namoz_d:
        text += f"  ✅ O'qildi:       {namoz_d.get('oqildi', 0)}\n"
        text += f"  ⏳ Endi o'qiyman: {namoz_d.get('endi_oqiyman', 0)}\n"
        text += f"  🔄 Qazo:          {namoz_d.get('qazo', 0)}\n"
    else:
        text += "  Ma'lumot yo'q.\n"

    bot.send_message(uid, text, parse_mode="Markdown")

def send_weekly_report(uid):
    now   = uz_time()
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    end   = today_str()
    task_rows = _task_block(uid, start, end)
    namoz_d   = _namoz_block(uid, start, end)

    text = f"📆 *HAFTALIK HISOBOT*\n_{start} — {end}_\n\n"

    # Rejalar
    text += "📋 *Rejalar (kunlar bo'yicha):*\n"
    if task_rows:
        t_b = t_j = 0
        for row in task_rows:
            b = row['bajardi'] or 0
            j = row['jami']
            f = int(b / j * 100) if j else 0
            text += f"  {row['sana']}: {b}/{j} ({f}%)\n"
            t_b += b
            t_j += j
        umumiy = int(t_b / t_j * 100) if t_j else 0
        text += f"\n  ✨ *Umumiy: {t_b}/{t_j} ({umumiy}%)*\n"
    else:
        text += "  Ma'lumot yo'q.\n"

    # Namoz
    text += "\n🕌 *Namoz:*\n"
    if namoz_d:
        jami_n = sum(namoz_d.values())
        oq     = namoz_d.get('oqildi', 0)
        foiz_n = int(oq / jami_n * 100) if jami_n else 0
        text += f"  ✅ O'qildi:       {oq}\n"
        text += f"  ⏳ Endi o'qiyman: {namoz_d.get('endi_oqiyman', 0)}\n"
        text += f"  🔄 Qazo:          {namoz_d.get('qazo', 0)}\n"
        text += f"  📌 O'qish foizi:  {foiz_n}%\n"
    else:
        text += "  Ma'lumot yo'q.\n"

    bot.send_message(uid, text, parse_mode="Markdown")

def send_monthly_report(uid):
    now   = uz_time()
    start = now.strftime("%Y-%m-01")
    end   = today_str()
    task_rows = _task_block(uid, start, end)
    namoz_d   = _namoz_block(uid, start, end)

    text = f"🗓 *OYLIK HISOBOT — {now.strftime('%B %Y')}*\n_{start} — {end}_\n\n"

    # Rejalar
    text += "📋 *Rejalar:*\n"
    if task_rows:
        t_b = sum((r['bajardi'] or 0) for r in task_rows)
        t_j = sum(r['jami'] for r in task_rows)
        foiz = int(t_b / t_j * 100) if t_j else 0
        text += f"  Jami: {t_j} ta reja\n"
        text += f"  ✅ Bajarildi: {t_b} ({foiz}%)\n"
        text += f"  ❌ Bajarilmadi: {t_j - t_b}\n"
    else:
        text += "  Ma'lumot yo'q.\n"

    # Namoz
    text += "\n🕌 *Namoz:*\n"
    if namoz_d:
        jami_n = sum(namoz_d.values())
        oq     = namoz_d.get('oqildi', 0)
        foiz_n = int(oq / jami_n * 100) if jami_n else 0
        text += f"  Jami belgilangan: {jami_n}\n"
        text += f"  ✅ O'qildi:       {oq} ({foiz_n}%)\n"
        text += f"  ⏳ Endi o'qiyman: {namoz_d.get('endi_oqiyman', 0)}\n"
        text += f"  🔄 Qazo:          {namoz_d.get('qazo', 0)}\n"
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
# ✅ VAZIFA JAVOBLARI (45 daqiqa)
# -----------------------------------------------------------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("done_") or c.data.startswith("not_"))
def cb_task_answer(call):
    parts  = call.data.split("_")
    action = parts[0]          # done | not
    uid    = int(parts[1])
    tid    = int(parts[2])
    status = 1 if action == "done" else 0

    conn = get_conn()
    conn.execute("UPDATE daily_tasks SET status=? WHERE id=?", (status, tid))
    conn.commit()
    conn.close()

    text = "✅ Zo'r! Vazifa bajarildi." if action == "done" else "❌ Vazifa bajarilmadi. Ertaga urinib ko'ring!"
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except:
        bot.send_message(uid, text)

# -----------------------------------------------------------------------
# ⏰ TAYMER — Asosiy scheduler
# -----------------------------------------------------------------------
def schedule_checker():
    last_minute = ""
    while True:
        try:
            now          = uz_time()
            current_time = now.strftime("%H:%M")

            if current_time == last_minute:
                time.sleep(5)
                continue
            last_minute = current_time

            conn = get_conn()

            # ═══════════════════════════════════════════════════════
            # 1. NAMOZ ESLATMALARI
            # ═══════════════════════════════════════════════════════
            namoz_rows = conn.execute(
                "SELECT user_id, bomdod, peshin, asr, shom, xufton, saved_at FROM namoz_times"
            ).fetchall()

            for nrow in namoz_rows:
                uid = nrow['user_id']
                saved = datetime.strptime(nrow['saved_at'], "%Y-%m-%d")
                days_passed = (now.date() - saved.date()).days

                # 7 kun o'tgan bo'lsa yangilash so'rash
                if days_passed >= 7:
                    try:
                        bot.send_message(uid,
                            "⚠️ *Namoz vaqtlaringiz muddati tugadi!*\n"
                            "Yangi hafta uchun vaqtlarni yangilang: *⏰ Namoz vaqtlarini kiritish*",
                            parse_mode="Markdown")
                    except:
                        pass
                    conn.execute("DELETE FROM namoz_times WHERE user_id=?", (uid,))
                    conn.commit()
                    continue

                NAMOZ_MAP = {
                    'Bomdod ☁️': nrow['bomdod'],
                    'Peshin 🌞': nrow['peshin'],
                    'Asr 🌤':    nrow['asr'],
                    'Shom 🌆':   nrow['shom'],
                    'Xufton 🌃': nrow['xufton'],
                }
                for nom, vaqt in NAMOZ_MAP.items():
                    if vaqt == current_time:
                        try:
                            bot.send_message(uid,
                                f"🕌 *Namoz vaqti: {nom}*\n⏰ {vaqt}",
                                parse_mode="Markdown")
                            conn.execute(
                                "INSERT INTO namoz_notify (user_id, namoz_nomi, notified_at) VALUES (?,?,?)",
                                (uid, nom, time.time()))
                            conn.commit()
                        except:
                            pass

            # ═══════════════════════════════════════════════════════
            # 2. NAMOZ 20 DAQIQA TEKSHIRUVI
            # ═══════════════════════════════════════════════════════
            notify_rows = conn.execute(
                "SELECT id, user_id, namoz_nomi FROM namoz_notify WHERE asked=0 AND notified_at<?",
                (time.time() - 20 * 60,)).fetchall()

            for nr in notify_rows:
                uid = nr['user_id']
                nom = nr['namoz_nomi']
                nom_key = nom.replace(" ", "__")
                try:
                    markup = types.InlineKeyboardMarkup()
                    markup.row(
                        types.InlineKeyboardButton("✅ Ha, o'qidim",
                            callback_data=f"namoz_oqildi_{uid}_{nom_key}"),
                        types.InlineKeyboardButton("⏳ Endi o'qiyman",
                            callback_data=f"namoz_endi_oqiyman_{uid}_{nom_key}")
                    )
                    markup.row(
                        types.InlineKeyboardButton("🔄 Qazo o'qiyman",
                            callback_data=f"namoz_qazo_{uid}_{nom_key}")
                    )
                    bot.send_message(uid,
                        f"🕌 *{nom}* namozini o'qidingizmi?",
                        reply_markup=markup, parse_mode="Markdown")
                    conn.execute("UPDATE namoz_notify SET asked=1 WHERE id=?", (nr['id'],))
                    conn.commit()
                except:
                    pass

            # ═══════════════════════════════════════════════════════
            # 3. KUNLIK REJA ESLATMALARI
            # ═══════════════════════════════════════════════════════
            daily_remind = conn.execute(
                """SELECT id, user_id, task_name FROM daily_tasks
                   WHERE sana=? AND task_time=? AND notified=0""",
                (today_str(), current_time)).fetchall()

            for dr in daily_remind:
                try:
                    bot.send_message(dr['user_id'],
                        f"🔔 *Eslatma!*\n📌 {dr['task_name']} vaqti bo'ldi!",
                        parse_mode="Markdown")
                    conn.execute(
                        "UPDATE daily_tasks SET notified=1, notified_at=? WHERE id=?",
                        (time.time(), dr['id']))
                    conn.commit()
                except:
                    pass

            # ═══════════════════════════════════════════════════════
            # 4. HAFTALIK REJA ESLATMALARI (har kuni)
            # ═══════════════════════════════════════════════════════
            weekly_rows = conn.execute(
                "SELECT user_id, task_name, task_time FROM weekly_tasks WHERE active=1 AND task_time=?",
                (current_time,)).fetchall()

            for wr in weekly_rows:
                uid = wr['user_id']
                wname = wr['task_name']
                wtime = wr['task_time']
                # Bugun bu reja daily_tasks ga qo'shilganmi?
                existing = conn.execute(
                    "SELECT id FROM daily_tasks WHERE user_id=? AND task_name=? AND sana=? AND source='weekly'",
                    (uid, wname, today_str())).fetchone()
                if not existing:
                    conn.execute(
                        """INSERT INTO daily_tasks
                           (user_id, task_name, task_time, sana, source, notified, notified_at)
                           VALUES (?,?,?,?,'weekly',1,?)""",
                        (uid, wname, wtime, today_str(), time.time()))
                    conn.commit()
                try:
                    bot.send_message(uid,
                        f"📅 *Haftalik reja eslatmasi:*\n📌 {wname}",
                        parse_mode="Markdown")
                except:
                    pass

            # ═══════════════════════════════════════════════════════
            # 5. 45 DAQIQA — Bajarildi/Bajarilmadi so'rovi
            # ═══════════════════════════════════════════════════════
            check_45 = conn.execute(
                """SELECT id, user_id, task_name FROM daily_tasks
                   WHERE sana=? AND notified=1 AND verified=0
                   AND status IS NULL AND notified_at<?""",
                (today_str(), time.time() - 45 * 60)).fetchall()

            for cr in check_45:
                try:
                    markup = types.InlineKeyboardMarkup()
                    markup.row(
                        types.InlineKeyboardButton("✅ Ha, bajardim",
                            callback_data=f"done_{cr['user_id']}_{cr['id']}"),
                        types.InlineKeyboardButton("❌ Yo'q",
                            callback_data=f"not_{cr['user_id']}_{cr['id']}")
                    )
                    bot.send_message(cr['user_id'],
                        f"❓ 45 daqiqa o'tdi.\n*'{cr['task_name']}'* bajarildimi?",
                        reply_markup=markup, parse_mode="Markdown")
                    conn.execute("UPDATE daily_tasks SET verified=1 WHERE id=?", (cr['id'],))
                    conn.commit()
                except:
                    pass

            # ═══════════════════════════════════════════════════════
            # 6. AVTOMATIK HISOBOTLAR
            # ═══════════════════════════════════════════════════════
            all_users = conn.execute(
                "SELECT user_id FROM users WHERE registered=1").fetchall()

            # Kunlik — har kecha 22:00
            if current_time == "22:00":
                for u in all_users:
                    try:
                        send_daily_report(u['user_id'])
                    except:
                        pass

            # Haftalik — Yakshanba 21:00
            if current_time == "21:00" and now.weekday() == 6:
                for u in all_users:
                    try:
                        send_weekly_report(u['user_id'])
                    except:
                        pass

            # Oylik — oy oxirgi kuni 21:30
            tomorrow = now + timedelta(days=1)
            if current_time == "21:30" and tomorrow.month != now.month:
                for u in all_users:
                    try:
                        send_monthly_report(u['user_id'])
                    except:
                        pass

            conn.close()
            time.sleep(5)

        except Exception as e:
            print(f"[TAYMER XATO] {e}")
            time.sleep(10)


# -----------------------------------------------------------------------
# 🎬 ISHGA TUSHIRISH
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print("✅ Bot ishga tushdi (O'zbekiston vaqti UTC+5)")

    # Taymer threadini ishga tushiramiz
    t = threading.Thread(target=schedule_checker, daemon=True)
    t.start()

    # Render free tier uchun: uzilishdan himoyalangan polling
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            print(f"[POLLING XATO] {e} — 10 soniyadan keyin qayta ulanadi...")
            time.sleep(10)
