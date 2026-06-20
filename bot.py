import os
import math
import re
import logging
import telebot
from telebot import types
import threading
import time
from datetime import datetime, timedelta
import sqlite3
import urllib.request
import urllib.parse
import json
import hashlib
import hmac
import random
from flask import Flask, request, jsonify, g
from flask_cors import CORS

# -----------------------------------------------------------------------
# 📝 LOGGING — xatoliklar endi jim yutilmaydi, konsolga yoziladi
# -----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("shaxsiy_nazoratchi")

# -----------------------------------------------------------------------
# ⚙️ SOZLAMALAR
# -----------------------------------------------------------------------
# ⚠️ TOKEN HECH QACHON KODGA YOZILMAYDI — faqat Render/serverdagi
# Environment Variables orqali beriladi. Agar oldin tokenni shu faylga
# yozib GitHub'ga yuklagan bo'lsangiz, @BotFather'da /revoke qiling va
# yangi token oling — eski token allaqachon oshkor bo'lgan hisoblanadi!
API_TOKEN    = os.environ.get('BOT_TOKEN')
KANAL_ID     = os.environ.get('KANAL_ID', '@shaxsiy_nazoratchi')
KANAL_LINKI  = os.environ.get('KANAL_LINKI', 'https://t.me/shaxsiy_nazoratchi')
DB_PATH      = os.environ.get('DB_PATH', 'bot_data.db')
MINI_APP_URL = os.environ.get('MINI_APP_URL', '')

if not API_TOKEN:
    raise RuntimeError(
        "❌ BOT_TOKEN topilmadi!\n"
        "Render Dashboard → Environment → BOT_TOKEN qiymatini kiriting.\n"
        "Tokenni hech qachon kod ichiga yozmang."
    )

# 🔐 ADMIN TIZIMI — faqat shu Telegram ID'lar xavfli buyruqlardan
# (masalan /reset_db) foydalana oladi.
# Render → Environment → ADMIN_IDS = "123456789,987654321"
ADMIN_IDS = set()
for _admin_x in os.environ.get('ADMIN_IDS', '').split(','):
    _admin_x = _admin_x.strip()
    if _admin_x.isdigit():
        ADMIN_IDS.add(int(_admin_x))

if not ADMIN_IDS:
    log.warning("⚠️ ADMIN_IDS sozlanmagan — admin buyruqlari hech kim uchun ishlamaydi.")

def is_admin(uid):
    return uid in ADMIN_IDS

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
    "🌄 Har bir tong — yangi imkoniyat!",
    "⚡ Kichik odatlar — katta natijalarga sabab!",
    "🎖️ Izchillik — iste'doddan kuchli!",
    "🧠 O'z ustingizda ishlash — eng katta g'alaba!",
    "🌺 Bugungi mehnat — ertangi farovonlik!",
]

# -----------------------------------------------------------------------
# 🏆 UNVONLAR (Ball tizimi)
# -----------------------------------------------------------------------
UNVONLAR = [
    (0,    "🥉 Yangi boshlovchi",    1),
    (100,  "🥈 Harakat qiluvchi",    2),
    (300,  "🥇 Izchil inson",        3),
    (600,  "🏅 Maqsadli shaxs",      4),
    (1000, "🏆 Nazoratchi ustasi",   5),
    (2000, "👑 Rivojlanish chempioni", 6),
    (4000, "🌟 Intizom afsonasi",    7),
    (7000, "🔱 Mutlaq nazoratchi",   8),
]

# 🎭 VIRTUAL AVATAR (Matn asosida)
AVATAR_STYLES = {
    "warrior":  {"emoji": "⚔️🛡️", "name": "Jangchi"},
    "scholar":  {"emoji": "📚🎓", "name": "Olim"},
    "monk":     {"emoji": "🧘🕌", "name": "Zohid"},
    "champion": {"emoji": "🏆🥊", "name": "Chempion"},
    "sage":     {"emoji": "🌟🔮", "name": "Donishmand"},
    "phoenix":  {"emoji": "🔥🦅", "name": "Fenikis"},
    "dragon":   {"emoji": "🐉👑", "name": "Ajdaho"},
    "legend":   {"emoji": "⚡💫", "name": "Afsona"},
}

AVATAR_FRAMES = {
    "none":    {"emoji": "",     "name": "Yo'q"},
    "gold":    {"emoji": "🌕",   "name": "Oltin"},
    "diamond": {"emoji": "💎",   "name": "Olmos"},
    "fire":    {"emoji": "🔥",   "name": "Olov"},
    "star":    {"emoji": "⭐",   "name": "Yulduz"},
    "crown":   {"emoji": "👑",   "name": "Toj"},
    "rainbow": {"emoji": "🌈",   "name": "Kamalak"},
}

AVATAR_BADGES = {
    "none":       {"emoji": "",   "name": "Yo'q"},
    "namoz":      {"emoji": "🕌", "name": "Namozxon"},
    "sportsman":  {"emoji": "💪", "name": "Sportchi"},
    "reader":     {"emoji": "📚", "name": "Kitobxon"},
    "achiever":   {"emoji": "🎯", "name": "Maqsadchi"},
    "disciplined":{"emoji": "⚡", "name": "Intizomli"},
    "legend_b":   {"emoji": "🌟", "name": "Afsona"},
}

# 🛒 DO'KON BUYUMLARI (seed data)
STORE_ITEMS_SEED = [
    # Avatar uslublari
    {"name": "Olim Avatar",     "emoji": "📚", "description": "Bilim va hikmat timsoli", "item_type": "avatar_style", "item_key": "scholar",  "ball_cost": 200,  "required_level": 2},
    {"name": "Zohid Avatar",    "emoji": "🧘", "description": "Tin va ruh sohibi",        "item_type": "avatar_style", "item_key": "monk",     "ball_cost": 300,  "required_level": 3},
    {"name": "Chempion Avatar", "emoji": "🏆", "description": "G'alaba timsoli",          "item_type": "avatar_style", "item_key": "champion", "ball_cost": 500,  "required_level": 4},
    {"name": "Donishmand Avatar","emoji":"🌟", "description": "Ulug' bilimdon",            "item_type": "avatar_style", "item_key": "sage",     "ball_cost": 800,  "required_level": 5},
    {"name": "Fenikis Avatar",  "emoji": "🔥", "description": "Qayta tugiluvchi quvvat",  "item_type": "avatar_style", "item_key": "phoenix",  "ball_cost": 1200, "required_level": 6},
    {"name": "Ajdaho Avatar",   "emoji": "🐉", "description": "Eng qudratli mavjudot",    "item_type": "avatar_style", "item_key": "dragon",   "ball_cost": 2000, "required_level": 7},
    {"name": "Afsona Avatar",   "emoji": "⚡", "description": "Erishib bo'lmaydigan zirvа","item_type": "avatar_style", "item_key": "legend",   "ball_cost": 5000, "required_level": 8},
    # Ramkalar
    {"name": "Oltin Ramka",     "emoji": "🌕", "description": "Shon-sharaf ramkasi",       "item_type": "frame",       "item_key": "gold",     "ball_cost": 150,  "required_level": 2},
    {"name": "Olmos Ramka",     "emoji": "💎", "description": "Noyob olmosli ramka",        "item_type": "frame",       "item_key": "diamond",  "ball_cost": 400,  "required_level": 4},
    {"name": "Olov Ramka",      "emoji": "🔥", "description": "Yonib turuvchi ramka",       "item_type": "frame",       "item_key": "fire",     "ball_cost": 300,  "required_level": 3},
    {"name": "Yulduz Ramka",    "emoji": "⭐", "description": "Yulduzli ramka",             "item_type": "frame",       "item_key": "star",     "ball_cost": 250,  "required_level": 3},
    {"name": "Toj Ramka",       "emoji": "👑", "description": "Podshohona ramka",           "item_type": "frame",       "item_key": "crown",    "ball_cost": 600,  "required_level": 5},
    {"name": "Kamalak Ramka",   "emoji": "🌈", "description": "Rang-barang ramka",          "item_type": "frame",       "item_key": "rainbow",  "ball_cost": 500,  "required_level": 5},
    # Nishonlar
    {"name": "Namozxon Nishoni","emoji": "🕌", "description": "5 vaqt namoz o'quvchi",     "item_type": "badge",       "item_key": "namoz",    "ball_cost": 200,  "required_level": 2},
    {"name": "Sportchi Nishoni","emoji": "💪", "description": "Jismoniy baquvvat",          "item_type": "badge",       "item_key": "sportsman","ball_cost": 200,  "required_level": 2},
    {"name": "Kitobxon Nishoni","emoji": "📚", "description": "Bilim izlovchi",             "item_type": "badge",       "item_key": "reader",   "ball_cost": 200,  "required_level": 2},
    {"name": "Intizomli Nishon","emoji": "⚡", "description": "Temir intizom sohibi",       "item_type": "badge",       "item_key": "disciplined","ball_cost":500, "required_level": 4},
    {"name": "Afsona Nishoni",  "emoji": "🌟", "description": "Barcha ularga erishgan",     "item_type": "badge",       "item_key": "legend_b", "ball_cost": 3000, "required_level": 7},
]

# 📦 HABIT MARKETPLACE PAKETLARI
HABIT_PACKAGES = {
    "namoz_pack": {
        "name": "🕌 Namoz Paketi",
        "description": "Diniy intizom uchun to'liq paket",
        "habits": [
            {"name": "5 vaqt namoz",         "emoji": "🕌"},
            {"name": "Bomdod namozi (o'z vaqtida)", "emoji": "🌙"},
            {"name": "Qur'on o'qish",         "emoji": "📖"},
            {"name": "Zikr aytish (33x3)",    "emoji": "📿"},
            {"name": "Tong duosi",            "emoji": "🤲"},
        ]
    },
    "sport_pack": {
        "name": "💪 Sport Paketi",
        "description": "Jismoniy salomatlik uchun",
        "habits": [
            {"name": "Tong yugurish (20 daqiqa)", "emoji": "🏃"},
            {"name": "Suvdan ichish (8 stakan)", "emoji": "💧"},
            {"name": "Mashq qilish",          "emoji": "🏋️"},
            {"name": "Cho'zilish",             "emoji": "🧘"},
            {"name": "10000 qadam",            "emoji": "👣"},
        ]
    },
    "bilim_pack": {
        "name": "📚 Bilim Paketi",
        "description": "Bilim va o'sish uchun",
        "habits": [
            {"name": "Kitob o'qish (30 daqiqa)", "emoji": "📚"},
            {"name": "Ingliz tili (15 daqiqa)", "emoji": "🌍"},
            {"name": "Dars takrorlash",        "emoji": "✏️"},
            {"name": "Podcast/Audio kitob",    "emoji": "🎧"},
            {"name": "Yangi so'z o'rganish",   "emoji": "🧠"},
        ]
    },
    "sat_pack": {
        "name": "🎓 SAT/Imtihon Paketi",
        "description": "Imtihon tayyorgarlik paketi",
        "habits": [
            {"name": "Math masala yechish",    "emoji": "📐"},
            {"name": "Grammar mashqlari",      "emoji": "✍️"},
            {"name": "Vocabulary 10 so'z",     "emoji": "📝"},
            {"name": "Reading comprehension",  "emoji": "👓"},
            {"name": "Test ishlash",           "emoji": "📋"},
        ]
    },
    "soglik_pack": {
        "name": "🌿 Sog'liq Paketi",
        "description": "Sog'lom turmush tarzi",
        "habits": [
            {"name": "Erta turish (5:30 gacha)", "emoji": "🌅"},
            {"name": "Sog'lom nonushta",       "emoji": "🥗"},
            {"name": "Tuni 23:00 gacha yotish","emoji": "😴"},
            {"name": "Telefon cheklash (2 soat)","emoji": "📵"},
            {"name": "Toza havo (30 daqiqa)",  "emoji": "🌬️"},
        ]
    },
}

# 🏁 CHALLENGELAR
CHALLENGE_TEMPLATES = {
    "7kun_namoz": {
        "title": "7 Kunlik Namoz Challenge",
        "description": "7 kun ketma-ket 5 vaqt namoz o'qing",
        "duration_days": 7,
        "ball_reward": 200,
        "emoji": "🕌"
    },
    "7kun_sport": {
        "title": "7 Kunlik Sport Challenge",
        "description": "7 kun ketma-ket sport qiling",
        "duration_days": 7,
        "ball_reward": 150,
        "emoji": "💪"
    },
    "30kun_kitob": {
        "title": "30 Kunlik Kitob Challenge",
        "description": "30 kun har kuni kitob o'qing",
        "duration_days": 30,
        "ball_reward": 500,
        "emoji": "📚"
    },
    "30kun_erta": {
        "title": "30 Kunlik Erta Turish",
        "description": "30 kun soat 6:00 gacha turing",
        "duration_days": 30,
        "ball_reward": 600,
        "emoji": "🌅"
    },
    "21kun_odat": {
        "title": "21 Kunlik Odat Shakllantirish",
        "description": "21 kun ketma-ket odatlarni bajaring",
        "duration_days": 21,
        "ball_reward": 350,
        "emoji": "🎯"
    },
    "30kun_reja": {
        "title": "30 Kunlik Reja Bajarish",
        "description": "30 kun har kuni rejalarning 80%+ sini bajaring",
        "duration_days": 30,
        "ball_reward": 700,
        "emoji": "📋"
    },
}

def get_unvon(ball):
    unvon = UNVONLAR[0][1]
    for min_ball, nom, _ in UNVONLAR:
        if ball >= min_ball:
            unvon = nom
    return unvon

def get_level(ball):
    level = 1
    for min_ball, _, lv in UNVONLAR:
        if ball >= min_ball:
            level = lv
    return level

def keyingi_unvon(ball):
    for min_ball, nom, _ in UNVONLAR:
        if ball < min_ball:
            return min_ball, nom
    return None, None

# -----------------------------------------------------------------------
# 💾 MA'LUMOTLAR BAZASI
# -----------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Asosiy jadvallar (mavjud)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        name       TEXT    NOT NULL,
        phone      TEXT    DEFAULT '',
        registered INTEGER DEFAULT 0,
        ball       INTEGER DEFAULT 0,
        penalty_ball INTEGER DEFAULT 0
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

    c.execute('''CREATE TABLE IF NOT EXISTS rewards (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        title      TEXT,
        ball_cost  INTEGER,
        created    TEXT
    )''')

    # 🆕 YANGI JADVALLAR

    # Virtual Avatar
    c.execute('''CREATE TABLE IF NOT EXISTS avatar (
        user_id  INTEGER PRIMARY KEY,
        style    TEXT DEFAULT 'warrior',
        frame    TEXT DEFAULT 'none',
        badge    TEXT DEFAULT 'none',
        xp       INTEGER DEFAULT 0
    )''')

    # Do'kon buyumlari
    c.execute('''CREATE TABLE IF NOT EXISTS store_items (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT,
        emoji          TEXT,
        description    TEXT,
        item_type      TEXT,
        item_key       TEXT,
        ball_cost      INTEGER,
        required_level INTEGER DEFAULT 1,
        active         INTEGER DEFAULT 1
    )''')

    # Foydalanuvchi xarid qilgan buyumlar
    c.execute('''CREATE TABLE IF NOT EXISTS user_items (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        item_id      INTEGER,
        item_type    TEXT,
        item_key     TEXT,
        purchased_at TEXT
    )''')

    # Challengelar
    c.execute('''CREATE TABLE IF NOT EXISTS challenges (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        key            TEXT UNIQUE,
        title          TEXT,
        description    TEXT,
        duration_days  INTEGER,
        ball_reward    INTEGER DEFAULT 100,
        emoji          TEXT DEFAULT '🏆',
        active         INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_challenges (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        challenge_id INTEGER,
        challenge_key TEXT,
        start_date   TEXT,
        end_date     TEXT,
        status       TEXT DEFAULT 'active',
        progress     INTEGER DEFAULT 0
    )''')

    # Zikr Trackeri
    c.execute('''CREATE TABLE IF NOT EXISTS zikrs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER,
        name          TEXT,
        emoji         TEXT DEFAULT '📿',
        target_count  INTEGER DEFAULT 33,
        reminder_time TEXT DEFAULT '',
        active        INTEGER DEFAULT 1,
        created       TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS zikr_logs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        zikr_id    INTEGER,
        user_id    INTEGER,
        sana       TEXT,
        count      INTEGER DEFAULT 0,
        updated_at REAL DEFAULT 0
    )''')

    # 🌙 "Bu kunlar" — ayollar uchun, belgilangan kunlarda namoz farz emasligi
    # sababli, shu kunlar statistikadan (qazo hisobidan) chiqarib tashlanadi.
    c.execute('''CREATE TABLE IF NOT EXISTS cycle_days (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sana    TEXT,
        UNIQUE(user_id, sana)
    )''')

    conn.commit()

    # 🔧 MIGRATSIYA — eski (allaqachon ishlab turgan) bazalarga yangi ustunlarni
    # xavfsiz qo'shamiz. CREATE TABLE IF NOT EXISTS mavjud jadvalni o'zgartirmaydi,
    # shuning uchun yangi ustunlar ALTER TABLE orqali alohida qo'shiladi.
    def _add_column_if_missing(table, col_name, col_def):
        existing = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
        if col_name not in existing:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")

    _add_column_if_missing('users', 'gender', "gender TEXT DEFAULT NULL")
    _add_column_if_missing('users', 'theme', "theme TEXT DEFAULT 'dark'")
    _add_column_if_missing('users', 'day_end_time', "day_end_time TEXT DEFAULT '22:00'")

    # 🚀 INDEKSLAR — eng ko'p ishlatiladigan so'rovlarni tezlashtiradi.
    # CREATE INDEX IF NOT EXISTS xavfsiz — mavjud bo'lsa o'tkazib yuboradi.
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_daily_tasks_user_sana    ON daily_tasks(user_id, sana)",
        "CREATE INDEX IF NOT EXISTS idx_namoz_stats_user_sana    ON namoz_stats(user_id, sana)",
        "CREATE INDEX IF NOT EXISTS idx_habit_logs_habit_sana    ON habit_logs(habit_id, sana)",
        "CREATE INDEX IF NOT EXISTS idx_habit_logs_user_sana     ON habit_logs(user_id, sana)",
        "CREATE INDEX IF NOT EXISTS idx_habits_user              ON habits(user_id, active)",
        "CREATE INDEX IF NOT EXISTS idx_zikr_logs_zikr_sana      ON zikr_logs(zikr_id, sana)",
        "CREATE INDEX IF NOT EXISTS idx_zikrs_user               ON zikrs(user_id, active)",
        "CREATE INDEX IF NOT EXISTS idx_goals_user               ON goals(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_namoz_notify_asked       ON namoz_notify(asked, notified_at)",
        "CREATE INDEX IF NOT EXISTS idx_cycle_days_user_sana     ON cycle_days(user_id, sana)",
    ]
    for idx_sql in indexes:
        c.execute(idx_sql)

    conn.commit()

    # Do'kon buyumlarini seed qilish
    for item in STORE_ITEMS_SEED:
        c.execute("SELECT id FROM store_items WHERE item_key=? AND item_type=?", (item['item_key'], item['item_type']))
        if not c.fetchone():
            c.execute("""INSERT INTO store_items (name,emoji,description,item_type,item_key,ball_cost,required_level)
                         VALUES (?,?,?,?,?,?,?)""",
                      (item['name'], item['emoji'], item['description'],
                       item['item_type'], item['item_key'],
                       item['ball_cost'], item['required_level']))

    # Challenge templatelarini seed qilish
    for key, ch in CHALLENGE_TEMPLATES.items():
        c.execute("SELECT id FROM challenges WHERE key=?", (key,))
        if not c.fetchone():
            c.execute("""INSERT INTO challenges (key,title,description,duration_days,ball_reward,emoji)
                         VALUES (?,?,?,?,?,?)""",
                      (key, ch['title'], ch['description'], ch['duration_days'], ch['ball_reward'], ch['emoji']))

    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------
# 🔧 YORDAMCHI FUNKSIYALAR
# -----------------------------------------------------------------------

def uz_time():
    return datetime.utcnow() + timedelta(hours=5)

def today_str():
    return uz_time().strftime("%Y-%m-%d")

def hhmm_plus(hhmm, minutes):
    """'HH:MM' qiymatiga necha daqiqa qo'shilganini hisoblaydi (kecha/kunduz
    chegarasidan o'tib ketishni ham to'g'ri hisoblaydi)."""
    try:
        t = datetime.strptime(hhmm, "%H:%M")
    except (ValueError, TypeError):
        t = datetime.strptime("22:00", "%H:%M")
    return (t + timedelta(minutes=minutes)).strftime("%H:%M")

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
    if amount < 0:
        # Jarima: ball 0 dan past tushmasin
        current = conn.execute("SELECT ball FROM users WHERE user_id=?", (uid,)).fetchone()
        if current:
            new_ball = max(0, current['ball'] + amount)
            conn.execute("UPDATE users SET ball=? WHERE user_id=?", (new_ball, uid))
    else:
        conn.execute("UPDATE users SET ball = ball + ? WHERE user_id=?", (amount, uid))
        # Avatar XP ham oshirish
        conn.execute("INSERT OR IGNORE INTO avatar (user_id) VALUES (?)", (uid,))
        conn.execute("UPDATE avatar SET xp = xp + ? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

def add_ball_conn(conn, uid, amount):
    if amount < 0:
        current = conn.execute("SELECT ball FROM users WHERE user_id=?", (uid,)).fetchone()
        if current:
            new_ball = max(0, current['ball'] + amount)
            conn.execute("UPDATE users SET ball=? WHERE user_id=?", (new_ball, uid))
    else:
        conn.execute("UPDATE users SET ball = ball + ? WHERE user_id=?", (amount, uid))
        conn.execute("INSERT OR IGNORE INTO avatar (user_id) VALUES (?)", (uid,))
        conn.execute("UPDATE avatar SET xp = xp + ? WHERE user_id=?", (amount, uid))

def get_motivatsiya():
    return random.choice(MOTIVATSIYA)

def get_avatar(uid, conn=None):
    _own = conn is None
    if _own:
        conn = get_conn()
    row = conn.execute("SELECT style,frame,badge FROM avatar WHERE user_id=?", (uid,)).fetchone()
    if _own:
        conn.close()
    if not row:
        return {"style": "warrior", "frame": "none", "badge": "none"}
    return dict(row)

def render_avatar(uid):
    """Avatar matn ko'rinishida chiqarish"""
    av = get_avatar(uid)
    style_data = AVATAR_STYLES.get(av['style'], AVATAR_STYLES['warrior'])
    frame_data = AVATAR_FRAMES.get(av['frame'], AVATAR_FRAMES['none'])
    badge_data = AVATAR_BADGES.get(av['badge'], AVATAR_BADGES['none'])
    ball = get_ball(uid)
    level = get_level(ball)

    frame_e = frame_data['emoji']
    badge_e = badge_data['emoji']
    style_e = style_data['emoji']

    lines = [
        f"┌─── ⭐ AVATAR ───┐",
        f"│  {frame_e}{style_e}{frame_e}  │",
        f"│  {style_data['name']}  │",
        f"│  Daraja: {level} / 8   │",
    ]
    if badge_e:
        lines.append(f"│  Nishon: {badge_e} {badge_data['name']}  │")
    lines.append(f"└────────────────┘")
    return "\n".join(lines)

# -----------------------------------------------------------------------
# 💯 INTIZOM INDEKSI
# -----------------------------------------------------------------------

def calculate_intizom(uid, sana=None, conn=None):
    """0-100 intizom indeksini hisoblash.
    conn berilsa mavjud ulanish ishlatiladi (yangi ulanish ochilmaydi).
    """
    if sana is None:
        sana = today_str()
    _own_conn = conn is None
    if _own_conn:
        conn = get_conn()

    score = 0
    details = {}

    # 1. REJA (40 ball)
    task_row = conn.execute(
        "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=?",
        (uid, sana)).fetchone()
    j = task_row['j'] or 0
    b = task_row['b'] or 0
    if j > 0:
        reja_foiz = b / j
        reja_ball = int(reja_foiz * 40)
    else:
        reja_foiz = 0
        reja_ball = 0
    score += reja_ball
    details['reja'] = {"jami": j, "bajarildi": b, "ball": reja_ball}

    # 2. NAMOZ (30 ball)
    namoz_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM namoz_stats WHERE user_id=? AND sana=? AND holat='oqildi'",
        (uid, sana)).fetchone()
    namoz_oqildi = namoz_row['cnt'] or 0
    namoz_ball = int((namoz_oqildi / 5) * 30)
    score += namoz_ball
    details['namoz'] = {"oqildi": namoz_oqildi, "ball": namoz_ball}

    # 3. ODATLAR (20 ball)
    habits_total = conn.execute(
        "SELECT COUNT(*) FROM habits WHERE user_id=? AND active=1", (uid,)).fetchone()[0]
    habits_done = conn.execute(
        "SELECT COUNT(*) FROM habit_logs WHERE user_id=? AND sana=? AND done=1",
        (uid, sana)).fetchone()[0]
    if habits_total > 0:
        odat_foiz = habits_done / habits_total
        odat_ball = int(odat_foiz * 20)
    else:
        odat_foiz = 0
        odat_ball = 0
    score += odat_ball
    details['odatlar'] = {"jami": habits_total, "bajarildi": habits_done, "ball": odat_ball}

    # 4. STREAK BONUS (10 ball)
    streak = 0
    d = uz_time().date()
    for _ in range(10):
        ds = d.strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=?",
            (uid, ds)).fetchone()
        if (row['j'] or 0) > 0 and (row['b'] or 0) >= (row['j'] or 1) * 0.5:
            streak += 1
        else:
            break
        d = d - timedelta(days=1)
    streak_ball = min(10, streak)
    score += streak_ball
    details['streak'] = {"kun": streak, "ball": streak_ball}

    if _own_conn:
        conn.close()
    return min(100, score), details

def intizom_rang(score):
    if score >= 90: return "🌟 A'lo"
    if score >= 75: return "✅ Yaxshi"
    if score >= 60: return "🟡 O'rtacha"
    if score >= 40: return "🟠 Past"
    return "🔴 Juda past"

# -----------------------------------------------------------------------
# 🌙 "BU KUNLAR" — namozdan vaqtinchalik ozod etilgan kunlar
# -----------------------------------------------------------------------

def is_cycle_day(conn, uid, sana=None):
    """Foydalanuvchi shu kunni 'Bu kunlar' deb belgilaganmi — shunday bo'lsa,
    namoz so'rovlari yuborilmaydi va statistikada hisobga olinmaydi."""
    sana = sana or today_str()
    row = conn.execute("SELECT 1 FROM cycle_days WHERE user_id=? AND sana=?", (uid, sana)).fetchone()
    return row is not None

def compute_namoz_streak(conn, uid):
    """Necha kun ketma-ket birorta ham namoz qazo qilinmagan (Bu kunlar
    bo'lgan kunlar ham streak hisobiga qo'shiladi — chunki o'sha kun namoz
    farz bo'lmagan, demak intizom buzilmagan)."""
    streak = 0
    d = uz_time().date()
    today_checked_once = False
    while True:
        ds = d.strftime("%Y-%m-%d")
        if is_cycle_day(conn, uid, ds):
            streak += 1
            d -= timedelta(days=1); continue
        total_cnt = conn.execute("SELECT COUNT(*) FROM namoz_stats WHERE user_id=? AND sana=?", (uid, ds)).fetchone()[0]
        qazo_cnt = conn.execute("SELECT COUNT(*) FROM namoz_stats WHERE user_id=? AND sana=? AND holat='qazo'", (uid, ds)).fetchone()[0]
        if ds == today_str() and total_cnt == 0 and not today_checked_once:
            # Bugungi kun hali tugamagan, hali hech narsa belgilanmagan bo'lishi
            # mumkin — bu streak'ni uzmaydi, shunchaki kechagidan boshlaymiz.
            today_checked_once = True
            d -= timedelta(days=1); continue
        if total_cnt == 0 or qazo_cnt > 0:
            break
        streak += 1
        d -= timedelta(days=1)
    return streak

# -----------------------------------------------------------------------
# 🤖 AI NAZORATCHI (Aqlli tahlil)
# -----------------------------------------------------------------------

def generate_ai_report(uid):
    """Kechki avtomatik AI hisoboti"""
    sana = today_str()
    conn = get_conn()
    name = get_name(uid)

    # Bugungi ma'lumotlar
    tasks = conn.execute(
        "SELECT task_name, status, priority FROM daily_tasks WHERE user_id=? AND sana=?",
        (uid, sana)).fetchall()
    namoz_today = conn.execute(
        "SELECT holat, COUNT(*) as cnt FROM namoz_stats WHERE user_id=? AND sana=? GROUP BY holat",
        (uid, sana)).fetchall()
    habits_today = conn.execute(
        """SELECT h.name, h.emoji, COALESCE(hl.done,0) as done
           FROM habits h
           LEFT JOIN habit_logs hl ON h.id=hl.habit_id AND hl.sana=?
           WHERE h.user_id=? AND h.active=1""",
        (sana, uid)).fetchall()

    # Haftalik trend
    week_start = (uz_time() - timedelta(days=6)).strftime("%Y-%m-%d")
    week_data = conn.execute(
        """SELECT sana,
           COUNT(*) as j,
           SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b
           FROM daily_tasks WHERE user_id=? AND sana>=?
           GROUP BY sana ORDER BY sana""",
        (uid, week_start)).fetchall()

    conn.close()

    score, _ = calculate_intizom(uid, sana)

    # Bajarilgan/bajarilmagan rejalar
    done_tasks   = [t for t in tasks if t['status'] == 1]
    undone_tasks = [t for t in tasks if t['status'] != 1]
    urgent_undone = [t for t in undone_tasks if t['priority'] == 'shoshilinch']

    # Namoz holati
    namoz_d = {r['holat']: r['cnt'] for r in namoz_today}
    namoz_oqildi = namoz_d.get('oqildi', 0)

    # Odat holati
    done_habits   = [h for h in habits_today if h['done']]
    undone_habits = [h for h in habits_today if not h['done']]

    # Haftalik trend tahlili
    week_foiz = []
    for wd in week_data:
        f = int((wd['b'] or 0) / wd['j'] * 100) if wd['j'] else 0
        week_foiz.append(f)
    avg_week = int(sum(week_foiz) / len(week_foiz)) if week_foiz else 0

    # Hisobot yozish
    report = f"🤖 *AI NAZORATCHI — {sana}*\n"
    report += f"👤 {name}\n"
    report += f"─────────────────────\n\n"

    # Intizom indeksi
    report += f"💯 *Bugungi intizom: {score}/100* {intizom_rang(score)}\n\n"

    # Bajarilganlar
    report += f"✅ *Bajarildi ({len(done_tasks)} ta):*\n"
    if done_tasks:
        for t in done_tasks[:5]:
            report += f"  • {t['task_name']}\n"
        if len(done_tasks) > 5:
            report += f"  ... va yana {len(done_tasks)-5} ta\n"
    else:
        report += "  Hali hech narsa bajarilmagan\n"

    report += f"\n❌ *Bajarilmadi ({len(undone_tasks)} ta):*\n"
    if undone_tasks:
        for t in undone_tasks[:5]:
            pri = "🔴" if t['priority']=='shoshilinch' else ("🟡" if t['priority']=='orta' else "🟢")
            report += f"  {pri} {t['task_name']}\n"
    else:
        report += "  Hammasi bajarildi! 🎉\n"

    # Namoz holati
    report += f"\n🕌 *Namoz: {namoz_oqildi}/5 ta o'qildi*\n"
    if namoz_oqildi == 5:
        report += "  Mashallah! Barcha namozlar o'qildi! ✨\n"
    elif namoz_oqildi == 0:
        report += "  ⚠️ Biror namoz belgilanmagan\n"

    # Odatlar
    report += f"\n🎯 *Odatlar: {len(done_habits)}/{len(habits_today)} bajarildi*\n"

    # Haftalik trend
    if avg_week > 0:
        trend_emoji = "📈" if (len(week_foiz) >= 2 and week_foiz[-1] > week_foiz[-2]) else "📉"
        report += f"\n{trend_emoji} *Haftalik o'rtacha: {avg_week}%*\n"

    # Ertaga tavsiyalar
    report += f"\n💡 *Ertaga e'tibor bering:*\n"
    suggestions = []
    if urgent_undone:
        suggestions.append(f"🔴 Shoshilinch: {urgent_undone[0]['task_name']}")
    if namoz_oqildi < 3:
        suggestions.append("🕌 Namozlarni o'z vaqtida o'qing")
    if undone_habits:
        suggestions.append(f"🎯 {undone_habits[0]['emoji']} {undone_habits[0]['name']} odatini bajaring")
    if avg_week < 50:
        suggestions.append("📋 Kam reja qo'shib, sifatli bajaring")
    elif avg_week > 80:
        suggestions.append("🚀 Zo'r natija! Yangi challenge boshlang")
    if not suggestions:
        suggestions.append("✨ Bugungi kabi ertaga ham ishlang!")

    for s in suggestions[:3]:
        report += f"  → {s}\n"

    # Motivatsiya
    report += f"\n{get_motivatsiya()}"

    return report

# -----------------------------------------------------------------------
# 📋 MENYULAR
# -----------------------------------------------------------------------

def show_main_menu(chat_id, uid=None):
    if uid is None: uid = chat_id
    name = get_name(uid)
    ball = get_ball(uid)
    unvon = get_unvon(ball)
    av = get_avatar(uid)
    style_e = AVATAR_STYLES.get(av['style'], AVATAR_STYLES['warrior'])['emoji']
    frame_e = AVATAR_FRAMES.get(av['frame'], AVATAR_FRAMES['none'])['emoji']

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📝 Kunlik reja"),   types.KeyboardButton("📅 Haftalik reja"))
    markup.row(types.KeyboardButton("🕌 Namoz"),          types.KeyboardButton("🎯 Odatlar"))
    markup.row(types.KeyboardButton("🏆 Maqsadlar"),      types.KeyboardButton("📊 Hisobotlar"))
    markup.row(types.KeyboardButton("📿 Zikr"),           types.KeyboardButton("🏁 Challenge"))
    markup.row(types.KeyboardButton("🛒 Do'kon"),         types.KeyboardButton("👥 Reyting"))
    markup.row(types.KeyboardButton("💯 Intizom"),        types.KeyboardButton("👤 Profil"))

    bot.send_message(chat_id,
        f"{frame_e}{style_e}{frame_e} *{name}*\n"
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
    markup.row(types.KeyboardButton("🗺 Heatmap"),        types.KeyboardButton("🤖 AI Hisobot"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "📊 *Hisobotlar bo'limi:*", reply_markup=markup, parse_mode="Markdown")

def show_habits_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("➕ Odat qo'shish"), types.KeyboardButton("📋 Odatlarim"))
    markup.row(types.KeyboardButton("✅ Bugungi odatlar"), types.KeyboardButton("📊 Odat statistikasi"))
    markup.row(types.KeyboardButton("📦 Habit Marketplace"), types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "🎯 *Odatlar (Habit Tracker):*", reply_markup=markup, parse_mode="Markdown")

def show_goals_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("➕ Maqsad qo'shish"), types.KeyboardButton("📋 Maqsadlarim"))
    markup.row(types.KeyboardButton("🎁 Mukofotlar"),       types.KeyboardButton("💰 Ballarim"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "🏆 *Maqsadlar va Mukofotlar:*", reply_markup=markup, parse_mode="Markdown")

def show_zikr_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("➕ Zikr qo'shish"), types.KeyboardButton("📿 Zikrlarim"))
    markup.row(types.KeyboardButton("✅ Zikr sanash"),   types.KeyboardButton("📊 Zikr statistikasi"))
    markup.row(types.KeyboardButton("🔙 Orqaga"))
    bot.send_message(chat_id, "📿 *Zikr Trackeri:*\n_Zikrlarni saning va statistikani kuting._",
                     reply_markup=markup, parse_mode="Markdown")

KATEGORIYALAR = ["💼 Ish", "📚 O'qish", "🏋️ Sport", "👨‍👩‍👧 Oila", "🌱 Shaxsiy", "⚙️ Boshqa"]
MUHIMLIK = {"🔴 Shoshilinch": "shoshilinch", "🟡 O'rta": "orta", "🟢 Oddiy": "oddiy"}

# -----------------------------------------------------------------------
# 🚀 START VA A'ZOLIK
# -----------------------------------------------------------------------

@bot.message_handler(commands=['start'])

def cmd_start(message):
    uid = message.from_user.id
    markup = types.InlineKeyboardMarkup()
    if MINI_APP_URL:
        markup.add(types.InlineKeyboardButton("📱 Ilovani ochish", web_app=types.WebAppInfo(url=MINI_APP_URL)))
    markup.add(types.InlineKeyboardButton("📢 Kanal", url=KANAL_LINKI))
    bot.send_message(uid,
        "Assalomu alaykum! 👋\n*SHAXSIY NAZORATCHI* botiga xush kelibsiz!\n\n"
        "✅ Kunlik/Haftalik rejalar\n🕌 Namoz nazorati\n"
        "🎯 Odatlar kuzatuvi\n🏆 Maqsad va mukofotlar\n"
        "📿 Zikr trackeri\n🏁 Challenge tizimi\n"
        "🛒 Ball do'koni\n💯 Intizom indeksi\n📊 AI hisobotlar",
        reply_markup=markup, parse_mode="Markdown")
    check_subscription(message)

@bot.message_handler(commands=['app'])

def cmd_app(message):
    uid = message.from_user.id
    if not MINI_APP_URL:
        bot.send_message(uid, "⚠️ Mini App hali sozlanmagan."); return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📱 Ilovani ochish", web_app=types.WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(uid, "📱 *Shaxsiy Nazoratchi* ilovasini oching:", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['reset_db'])

def cmd_reset_db(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.send_message(uid, "⛔ Bu buyruq faqat administrator uchun.")
        return
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Ha, tozala", callback_data="confirm_reset"),
        types.InlineKeyboardButton("❌ Yo'q", callback_data="cancel_reset"))
    bot.send_message(uid, "⚠️ *DIQQAT!*\nBarcha ma'lumotlar o'chib ketadi!\nDavom etishni xohlaysizmi?",
                     reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "confirm_reset")

def cb_confirm_reset(call):
    uid = call.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "⛔ Ruxsat yo'q", show_alert=True)
        return
    conn = None
    try:
        conn = get_conn()
        tables = ['users','namoz_times','namoz_notify','namoz_stats','daily_tasks','weekly_tasks',
                  'habits','habit_logs','goals','rewards','avatar','user_items','user_challenges',
                  'zikrs','zikr_logs']
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        bot.edit_message_text("✅ *Baza to'liq tozalandi!*\n\nQaytadan boshlash: /start",
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    except Exception as e:
        log.exception("reset_db xatosi")
        bot.send_message(uid, f"❌ Xatolik: {e}")
    finally:
        if conn:
            conn.close()

@bot.callback_query_handler(func=lambda c: c.data == "cancel_reset")

def cb_cancel_reset(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Ruxsat yo'q", show_alert=True)
        return
    bot.edit_message_text("❌ Bekor qilindi.", call.message.chat.id, call.message.message_id)

def check_subscription(message):
    uid = message.from_user.id
    try:
        status = bot.get_chat_member(KANAL_ID, uid).status
        subscribed = status in ['member','administrator','creator']
    except Exception as e:
        log.debug("Xatolik: %s", e)
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
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        log.debug("Xatolik (e'tiborga olinmadi): %s", e)
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
        bot.register_next_step_handler(msg, step_save_name); return
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO users (user_id,name,registered) VALUES (?,?,0)", (uid, name))
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
    conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, uid))
    conn.commit(); conn.close()
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("👨 Erkak", callback_data="gender_erkak"),
        types.InlineKeyboardButton("👩 Ayol", callback_data="gender_ayol"))
    bot.send_message(uid, "Jinsingizni tanlang:", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(uid, "👤", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ("gender_erkak", "gender_ayol"))
def cb_gender_select(call):
    uid = call.from_user.id
    gender = "erkak" if call.data == "gender_erkak" else "ayol"
    conn = get_conn()
    conn.execute("UPDATE users SET gender=?, registered=1 WHERE user_id=?", (gender, uid))
    conn.execute("INSERT OR IGNORE INTO avatar (user_id) VALUES (?)", (uid,))
    conn.commit(); conn.close()
    bot.edit_message_text(f"{'👨' if gender == 'erkak' else '👩'} Tanlandi!", call.message.chat.id, call.message.message_id)
    bot.send_message(uid,
        "✅ *Ro'yxatdan muvaffaqiyatli o'tdingiz!*\n\n"
        "💰 Boshlang'ich 10 ball berildi!\n"
        "🎭 Avatar: Jangchi ⚔️🛡️\n\n"
        "💡 Ball yig'ib avatarni rivojlantiring!",
        parse_mode="Markdown")
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
    level = get_level(ball)
    keyingi_b, keyingi_n = keyingi_unvon(ball)
    score, _ = calculate_intizom(uid)

    conn = get_conn()
    jami_reja  = conn.execute("SELECT COUNT(*) FROM daily_tasks WHERE user_id=?", (uid,)).fetchone()[0]
    bajarildi  = conn.execute("SELECT COUNT(*) FROM daily_tasks WHERE user_id=? AND status=1", (uid,)).fetchone()[0]
    namoz_oq   = conn.execute("SELECT COUNT(*) FROM namoz_stats WHERE user_id=? AND holat='oqildi'", (uid,)).fetchone()[0]
    mukofot    = conn.execute("SELECT COUNT(*) FROM rewards WHERE user_id=?", (uid,)).fetchone()[0]
    challenge_done = conn.execute("SELECT COUNT(*) FROM user_challenges WHERE user_id=? AND status='completed'", (uid,)).fetchone()[0]
    zikr_count = conn.execute("SELECT SUM(count) FROM zikr_logs WHERE user_id=?", (uid,)).fetchone()[0] or 0
    conn.close()

    foiz = int(bajarildi / jami_reja * 100) if jami_reja else 0
    avatar_str = render_avatar(uid)

    text = (f"👤 *PROFIL*\n\n"
            f"{avatar_str}\n\n"
            f"📛 Ism: {get_name(uid)}\n"
            f"{unvon} | Daraja: {level}/8\n"
            f"💰 Ball: {ball}\n")
    if keyingi_b:
        text += f"⬆️ Keyingi: {keyingi_n} ({keyingi_b-ball} ball qoldi)\n"
    text += (f"\n💯 Bugungi intizom: {score}/100 {intizom_rang(score)}\n"
             f"\n📊 *Statistika:*\n"
             f"📋 Jami reja: {jami_reja} | ✅ {bajarildi} ({foiz}%)\n"
             f"🕌 Namoz o'qildi: {namoz_oq} marta\n"
             f"📿 Jami zikr: {zikr_count} marta\n"
             f"🏁 Tugallangan challenge: {challenge_done}\n"
             f"🎁 Mukofotlar: {mukofot}\n")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎭 Avatarni boshqarish", callback_data="manage_avatar"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🎭 AVATAR BO'LIMI
# -----------------------------------------------------------------------

@bot.callback_query_handler(func=lambda c: c.data == "manage_avatar")

def cb_manage_avatar(call):
    uid = call.from_user.id
    av = get_avatar(uid)
    ball = get_ball(uid)
    level = get_level(ball)

    style_data = AVATAR_STYLES.get(av['style'], AVATAR_STYLES['warrior'])
    frame_data = AVATAR_FRAMES.get(av['frame'], AVATAR_FRAMES['none'])
    badge_data = AVATAR_BADGES.get(av['badge'], AVATAR_BADGES['none'])

    text = (f"🎭 *AVATAR BOSHQARUVI*\n\n"
            f"{render_avatar(uid)}\n\n"
            f"🎨 Uslub: {style_data['emoji']} {style_data['name']}\n"
            f"🖼 Ramka: {frame_data['emoji'] or '—'} {frame_data['name']}\n"
            f"🏅 Nishon: {badge_data['emoji'] or '—'} {badge_data['name']}\n\n"
            f"💰 Ball: {ball} | Daraja: {level}/8\n\n"
            f"_Do'konga kirib yangi buyumlar sotib oling!_")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 Do'konga o'tish", callback_data="show_store"))
    markup.add(types.InlineKeyboardButton("🎨 Uslub tanlash", callback_data="choose_style"))
    markup.add(types.InlineKeyboardButton("🖼 Ramka tanlash", callback_data="choose_frame"))
    markup.add(types.InlineKeyboardButton("🏅 Nishon tanlash", callback_data="choose_badge"))

    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "choose_style")

def cb_choose_style(call):
    uid = call.from_user.id
    conn = get_conn()
    owned = {r['item_key'] for r in conn.execute(
        "SELECT item_key FROM user_items WHERE user_id=? AND item_type='avatar_style'", (uid,)).fetchall()}
    conn.close()
    owned.add('warrior')  # Boshlang'ich avatar har doim mavjud

    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, data in AVATAR_STYLES.items():
        if key in owned:
            markup.add(types.InlineKeyboardButton(f"✅ {data['emoji']} {data['name']}", callback_data=f"set_style_{key}"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="manage_avatar"))
    try: bot.edit_message_text("🎨 *Uslub tanlang:*\n_(Xarid qilinganlar ko'rsatilmoqda)_",
                               call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "🎨 *Uslub tanlang:*", reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_style_"))

def cb_set_style(call):
    uid = call.from_user.id
    style_key = call.data.replace("set_style_", "")
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO avatar (user_id) VALUES (?)", (uid,))
    conn.execute("UPDATE avatar SET style=? WHERE user_id=?", (style_key, uid))
    conn.commit(); conn.close()
    style_data = AVATAR_STYLES.get(style_key, AVATAR_STYLES['warrior'])
    bot.answer_callback_query(call.id, f"✅ {style_data['emoji']} {style_data['name']} tanlandi!")
    cb_manage_avatar(call)

@bot.callback_query_handler(func=lambda c: c.data == "choose_frame")

def cb_choose_frame(call):
    uid = call.from_user.id
    conn = get_conn()
    owned = {r['item_key'] for r in conn.execute(
        "SELECT item_key FROM user_items WHERE user_id=? AND item_type='frame'", (uid,)).fetchall()}
    conn.close()
    owned.add('none')

    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, data in AVATAR_FRAMES.items():
        if key in owned:
            markup.add(types.InlineKeyboardButton(f"✅ {data['emoji'] or '—'} {data['name']}", callback_data=f"set_frame_{key}"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="manage_avatar"))
    try: bot.edit_message_text("🖼 *Ramka tanlang:*", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "🖼 *Ramka tanlang:*", reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_frame_"))

def cb_set_frame(call):
    uid = call.from_user.id
    frame_key = call.data.replace("set_frame_", "")
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO avatar (user_id) VALUES (?)", (uid,))
    conn.execute("UPDATE avatar SET frame=? WHERE user_id=?", (frame_key, uid))
    conn.commit(); conn.close()
    frame_data = AVATAR_FRAMES.get(frame_key, AVATAR_FRAMES['none'])
    bot.answer_callback_query(call.id, f"✅ {frame_data['name']} ramka tanlandi!")
    cb_manage_avatar(call)

@bot.callback_query_handler(func=lambda c: c.data == "choose_badge")

def cb_choose_badge(call):
    uid = call.from_user.id
    conn = get_conn()
    owned = {r['item_key'] for r in conn.execute(
        "SELECT item_key FROM user_items WHERE user_id=? AND item_type='badge'", (uid,)).fetchall()}
    conn.close()
    owned.add('none')

    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, data in AVATAR_BADGES.items():
        if key in owned:
            markup.add(types.InlineKeyboardButton(f"✅ {data['emoji'] or '—'} {data['name']}", callback_data=f"set_badge_{key}"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="manage_avatar"))
    try: bot.edit_message_text("🏅 *Nishon tanlang:*", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "🏅 *Nishon tanlang:*", reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_badge_"))

def cb_set_badge(call):
    uid = call.from_user.id
    badge_key = call.data.replace("set_badge_", "")
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO avatar (user_id) VALUES (?)", (uid,))
    conn.execute("UPDATE avatar SET badge=? WHERE user_id=?", (badge_key, uid))
    conn.commit(); conn.close()
    badge_data = AVATAR_BADGES.get(badge_key, AVATAR_BADGES['none'])
    bot.answer_callback_query(call.id, f"✅ {badge_data['name']} nishon tanlandi!")
    cb_manage_avatar(call)

# -----------------------------------------------------------------------
# 🛒 BALL DO'KONI
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "🛒 Do'kon")

def show_store(message):
    uid = message.from_user.id
    ball = get_ball(uid)
    level = get_level(ball)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🎨 Avatar uslublari", callback_data="store_avatar_style"),
        types.InlineKeyboardButton("🖼 Ramkalar", callback_data="store_frame"))
    markup.row(
        types.InlineKeyboardButton("🏅 Nishonlar", callback_data="store_badge"))
    bot.send_message(uid,
        f"🛒 *BALL DO'KONI*\n\n"
        f"💰 Ballingiz: *{ball}*\n"
        f"⭐ Darajangiz: *{level}/8*\n\n"
        f"_Ball yig'ib qimmatli buyumlar sotib oling!_",
        reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "show_store")

def cb_show_store(call):
    uid = call.from_user.id
    ball = get_ball(uid)
    level = get_level(ball)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🎨 Avatar uslublari", callback_data="store_avatar_style"),
        types.InlineKeyboardButton("🖼 Ramkalar", callback_data="store_frame"))
    markup.row(
        types.InlineKeyboardButton("🏅 Nishonlar", callback_data="store_badge"))
    try:
        bot.edit_message_text(
            f"🛒 *BALL DO'KONI*\n\n💰 Ballingiz: *{ball}*\n⭐ Darajangiz: *{level}/8*",
            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, f"🛒 *BALL DO'KONI*", reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

def show_store_category(call, item_type, category_name):
    uid = call.from_user.id
    ball = get_ball(uid)
    level = get_level(ball)
    conn = get_conn()
    items = conn.execute(
        "SELECT * FROM store_items WHERE item_type=? AND active=1 ORDER BY ball_cost",
        (item_type,)).fetchall()
    owned = {r['item_key'] for r in conn.execute(
        "SELECT item_key FROM user_items WHERE user_id=? AND item_type=?",
        (uid, item_type)).fetchall()}
    conn.close()
    if item_type == 'avatar_style':
        owned.add('warrior')

    text = f"🛒 *{category_name}*\n💰 Ballingiz: {ball} | Daraja: {level}/8\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in items:
        if item['item_key'] in owned:
            btn_text = f"✅ {item['emoji']} {item['name']} (Xarid qilingan)"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"already_owned_{item['id']}"))
        elif level < item['required_level']:
            btn_text = f"🔒 {item['emoji']} {item['name']} — {item['ball_cost']} ball (Daraja {item['required_level']})"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"locked_item_{item['id']}"))
        elif ball < item['ball_cost']:
            btn_text = f"💸 {item['emoji']} {item['name']} — {item['ball_cost']} ball"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"no_ball_{item['id']}"))
        else:
            btn_text = f"🛒 {item['emoji']} {item['name']} — {item['ball_cost']} ball"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_item_{item['id']}"))

    markup.add(types.InlineKeyboardButton("🔙 Do'konga qaytish", callback_data="show_store"))
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "store_avatar_style")

def cb_store_avatar(call):
    show_store_category(call, "avatar_style", "🎨 Avatar Uslublari")

@bot.callback_query_handler(func=lambda c: c.data == "store_frame")

def cb_store_frame(call):
    show_store_category(call, "frame", "🖼 Ramkalar")

@bot.callback_query_handler(func=lambda c: c.data == "store_badge")

def cb_store_badge(call):
    show_store_category(call, "badge", "🏅 Nishonlar")

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_item_"))

def cb_buy_item(call):
    uid = call.from_user.id
    item_id = int(call.data.replace("buy_item_", ""))
    conn = get_conn()
    item = conn.execute("SELECT * FROM store_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        bot.answer_callback_query(call.id, "❌ Buyum topilmadi!"); return
    ball = get_ball(uid)
    if ball < item['ball_cost']:
        conn.close()
        bot.answer_callback_query(call.id, f"❌ Yetarli ball yo'q! Kerak: {item['ball_cost']}"); return
    # Xarid
    conn.execute("INSERT INTO user_items (user_id,item_id,item_type,item_key,purchased_at) VALUES (?,?,?,?,?)",
                 (uid, item_id, item['item_type'], item['item_key'], today_str()))
    add_ball_conn(conn, uid, -item['ball_cost'])
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, f"✅ {item['emoji']} {item['name']} xarid qilindi!")
    bot.send_message(uid,
        f"🎉 *Xarid muvaffaqiyatli!*\n\n"
        f"{item['emoji']} *{item['name']}*\n"
        f"💰 -{item['ball_cost']} ball\n"
        f"💰 Qolgan ball: {get_ball(uid)}\n\n"
        f"_Profil → Avatarni boshqarish orqali kiyib oling!_",
        parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("locked_item_"))

def cb_locked_item(call):
    item_id = int(call.data.replace("locked_item_", ""))
    conn = get_conn()
    item = conn.execute("SELECT * FROM store_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    if item:
        bot.answer_callback_query(call.id, f"🔒 Daraja {item['required_level']} kerak!", show_alert=True)
    else:
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("no_ball_"))

def cb_no_ball(call):
    item_id = int(call.data.replace("no_ball_", ""))
    conn = get_conn()
    item = conn.execute("SELECT * FROM store_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    if item:
        bot.answer_callback_query(call.id, f"💰 Yetarli ball yo'q! {item['ball_cost']} ball kerak.", show_alert=True)
    else:
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("already_owned_"))

def cb_already_owned(call):
    bot.answer_callback_query(call.id, "✅ Bu buyum allaqachon sizda bor!")

# -----------------------------------------------------------------------
# 💯 INTIZOM INDEKSI
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "💯 Intizom")

def show_intizom(message):
    uid = message.from_user.id
    score, details = calculate_intizom(uid)
    name = get_name(uid)

    bar_len = int(score / 10)
    bar = "█" * bar_len + "░" * (10 - bar_len)

    text = (f"💯 *INTIZOM INDEKSI*\n\n"
            f"👤 {name}\n"
            f"📅 {today_str()}\n\n"
            f"[{bar}] *{score}/100*\n"
            f"{intizom_rang(score)}\n\n"
            f"📊 *Tafsilot:*\n\n"
            f"📋 Reja: {details['reja']['bajarildi']}/{details['reja']['jami']} — *{details['reja']['ball']}/40 ball*\n"
            f"🕌 Namoz: {details['namoz']['oqildi']}/5 — *{details['namoz']['ball']}/30 ball*\n"
            f"🎯 Odatlar: {details['odatlar']['bajarildi']}/{details['odatlar']['jami']} — *{details['odatlar']['ball']}/20 ball*\n"
            f"🔥 Streak: {details['streak']['kun']} kun — *{details['streak']['ball']}/10 ball*\n")

    if score >= 90:
        text += "\n🌟 *A'LO! Siz bugun ulug'vor harakat qildingiz!*"
    elif score >= 75:
        text += "\n✅ *Yaxshi natija! Yana biroz qo'shsangiz — mukammal!*"
    elif score >= 50:
        text += "\n💪 *O'rtacha. Ertaga ko'proq harakat qiling!*"
    else:
        text += "\n⚠️ *Past natija. Kichik qadamlardan boshlang!*"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 Haftalik intizom", callback_data="weekly_intizom"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "weekly_intizom")

def cb_weekly_intizom(call):
    uid = call.from_user.id
    now = uz_time()
    text = "📊 *HAFTALIK INTIZOM INDEKSI*\n\n"
    total = 0
    count = 0
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        score, _ = calculate_intizom(uid, d)
        bar = "█" * int(score/10) + "░" * (10-int(score/10))
        weekday = (now - timedelta(days=i)).strftime("%d-%b")
        text += f"📅 {weekday}: [{bar}] {score}/100\n"
        total += score
        count += 1
    avg = int(total / count) if count else 0
    text += f"\n📌 *O'rtacha: {avg}/100* {intizom_rang(avg)}"
    bot.answer_callback_query(call.id)
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🗺 HEATMAP KALENDAR
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "🗺 Heatmap")

def show_heatmap(message):
    uid = message.from_user.id
    now = uz_time()
    text = "🗺 *30 KUNLIK FAOLIYAT XARITASI*\n\n"
    text += "⬛ = 0%  🟫 = 1-40%  🟨 = 41-70%  🟩 = 71-100%\n\n"

    weeks = {}
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i))
        ds = d.strftime("%Y-%m-%d")
        week_num = i // 7
        if week_num not in weeks:
            weeks[week_num] = []

        conn = get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=?",
            (uid, ds)).fetchone()
        conn.close()
        j = row['j'] or 0
        b = row['b'] or 0
        foiz = int(b/j*100) if j else 0
        date_label = d.strftime("%d")

        if foiz == 0 and j == 0:
            cell = "⬛"
        elif foiz <= 40:
            cell = "🟫"
        elif foiz <= 70:
            cell = "🟨"
        else:
            cell = "🟩"
        weeks[week_num].append((date_label, cell))

    for week_idx in sorted(weeks.keys()):
        week_days = weeks[week_idx]
        line = ""
        for date_label, cell in week_days:
            line += cell
        # Hafta sanasi
        first_day = week_days[0][0]
        last_day = week_days[-1][0]
        text += f"`{first_day}-{last_day}` {line}\n"

    text += f"\n📅 So'nggi 30 kun ko'rsatilmoqda"
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🤖 AI HISOBOT
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "🤖 AI Hisobot")

def show_ai_report(message):
    uid = message.from_user.id
    bot.send_message(uid, "🤖 AI tahlil qilinmoqda...", parse_mode="Markdown")
    report = generate_ai_report(uid)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 AI Reja Optimizatori", callback_data="ai_optimizer"))
    bot.send_message(uid, report, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "ai_optimizer")

def cb_ai_optimizer(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id, "🤖 Tahlil qilinmoqda...")

    conn = get_conn()
    # So'nggi 7 kunlik ma'lumot
    week_start = (uz_time() - timedelta(days=6)).strftime("%Y-%m-%d")
    week_data = conn.execute(
        """SELECT sana,
           COUNT(*) as j,
           SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b,
           SUM(CASE WHEN priority='shoshilinch' AND status=1 THEN 1 ELSE 0 END) as urgent_done,
           SUM(CASE WHEN priority='shoshilinch' THEN 1 ELSE 0 END) as urgent_total
           FROM daily_tasks WHERE user_id=? AND sana>=?
           GROUP BY sana ORDER BY sana""",
        (uid, week_start)).fetchall()

    cat_data = conn.execute(
        """SELECT category,
           COUNT(*) as j,
           SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b
           FROM daily_tasks WHERE user_id=? AND sana>=?
           GROUP BY category ORDER BY b/j DESC""",
        (uid, week_start)).fetchall()

    habits_7 = conn.execute(
        """SELECT h.name, h.emoji,
           SUM(COALESCE(hl.done,0)) as done_cnt
           FROM habits h
           LEFT JOIN habit_logs hl ON h.id=hl.habit_id AND hl.sana>=?
           WHERE h.user_id=? AND h.active=1
           GROUP BY h.id ORDER BY done_cnt""",
        (week_start, uid)).fetchall()
    conn.close()

    text = "🤖 *AI REJA OPTIMIZATORI*\n\n"
    text += "_So'nggi 7 kun tahlili asosida tavsiyalar:_\n\n"

    # Eng yaxshi va yomon kunlar
    if week_data:
        foizlar = [(wd['b'] or 0) / wd['j'] * 100 if wd['j'] else 0 for wd in week_data]
        avg = sum(foizlar) / len(foizlar)

        text += f"📈 *Haftalik o'rtacha: {int(avg)}%*\n"
        if avg >= 80:
            text += "✅ Juda yaxshi natijalarga erishyapsiz!\n"
        elif avg >= 60:
            text += "🟡 O'rtacha natija. Optimallashtirishni tavsiya etamiz.\n"
        else:
            text += "🔴 Natijalar past. Reja hajmini kamaytiring.\n"

        # Eng qiyin kun
        worst_idx = foizlar.index(min(foizlar))
        worst_day = week_data[worst_idx]
        text += f"\n📉 *Eng qiyin kun:* {worst_day['sana'][5:]}\n"

    # Kategoriya tahlili
    if cat_data:
        text += "\n📂 *Kategoriya samaradorligi:*\n"
        for cat in cat_data[:5]:
            cat_foiz = int((cat['b'] or 0) / cat['j'] * 100) if cat['j'] else 0
            icon = "✅" if cat_foiz >= 70 else ("🟡" if cat_foiz >= 40 else "🔴")
            text += f"  {icon} {cat['category']}: {cat_foiz}%\n"

    # Odat tavsiyalari
    if habits_7:
        weak_habits = [h for h in habits_7 if h['done_cnt'] < 3]
        if weak_habits:
            text += "\n⚠️ *Zaif odatlar (haftada 3 martadan kam):*\n"
            for h in weak_habits[:3]:
                text += f"  {h['emoji']} {h['name']}: {h['done_cnt']}/7\n"

    # Tavsiyalar
    text += "\n💡 *AI Tavsiyalari:*\n"
    if week_data:
        avg_tasks = sum(wd['j'] for wd in week_data) / len(week_data)
        if avg_tasks > 8:
            text += "  → Kunlik reja hajmini 5-7 ta ga kamaytiring\n"
        elif avg_tasks < 3:
            text += "  → Kamida 3-5 ta reja qo'shing\n"
        else:
            text += "  → Reja hajmi optimal, sifatga e'tibor bering\n"

    foiz_list = [int((wd['b'] or 0)/wd['j']*100) for wd in week_data if wd['j']] if week_data else []
    if foiz_list and max(foiz_list) - min(foiz_list) > 40:
        text += "  → Natijalaringiz o'zgaruvchan. Eng ko'p bajariladigan vaqtni toping\n"
    text += "  → Shoshilinch rejalarni kunning 1-yarmida bajaring\n"
    text += "  → Habit Marketplace'dan yangi odat paketlari sinab ko'ring\n"

    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 👥 DO'STLAR REYTINGI
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "👥 Reyting")

def show_rating(message):
    uid = message.from_user.id
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📅 Haftalik TOP", callback_data="rating_weekly"),
        types.InlineKeyboardButton("🏆 Umumiy TOP", callback_data="rating_all"))
    markup.add(types.InlineKeyboardButton("📊 Mening o'rnim", callback_data="my_rating"))
    bot.send_message(uid, "👥 *DO'STLAR REYTINGI*\n\nQaysi reytingni ko'rmoqchisiz?",
                     reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "rating_weekly")

def cb_rating_weekly(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    week_start = (uz_time() - timedelta(days=6)).strftime("%Y-%m-%d")
    conn = get_conn()
    # Haftalik ball hisoblash (bajarilgan rejalar asosida)
    rows = conn.execute(
        """SELECT u.user_id, u.name, u.ball,
           COALESCE(SUM(CASE WHEN dt.status=1 AND dt.sana>=? THEN 15 ELSE 0 END),0) +
           COALESCE(SUM(CASE WHEN ns.holat='oqildi' AND ns.sana>=? THEN 10 ELSE 0 END),0) as week_ball
           FROM users u
           LEFT JOIN daily_tasks dt ON u.user_id=dt.user_id
           LEFT JOIN namoz_stats ns ON u.user_id=ns.user_id
           WHERE u.registered=1
           GROUP BY u.user_id
           ORDER BY week_ball DESC LIMIT 10""",
        (week_start, week_start)).fetchall()
    conn.close()

    text = f"📅 *HAFTALIK TOP 10*\n_{week_start} dan bugun gacha_\n\n"
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    my_pos = None
    for i, row in enumerate(rows):
        icon = medals[i] if i < len(medals) else f"{i+1}."
        name = row['name'][:15]
        you = " ← Siz" if row['user_id'] == uid else ""
        text += f"{icon} *{name}* — {row['week_ball']} ball{you}\n"
        if row['user_id'] == uid:
            my_pos = i + 1

    if not my_pos:
        text += f"\n_Siz TOP 10 da yo'qsiz_"
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "rating_all")

def cb_rating_all(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id,name,ball FROM users WHERE registered=1 ORDER BY ball DESC LIMIT 10").fetchall()
    conn.close()

    text = "🏆 *UMUMIY TOP 10*\n_(Jami to'plangan ball bo'yicha)_\n\n"
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for i, row in enumerate(rows):
        icon = medals[i] if i < len(medals) else f"{i+1}."
        name = row['name'][:15]
        unvon = get_unvon(row['ball'])
        you = " ← Siz" if row['user_id'] == uid else ""
        text += f"{icon} *{name}* — {row['ball']} ball\n   {unvon}{you}\n"
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "my_rating")

def cb_my_rating(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    conn = get_conn()
    pos_row = conn.execute(
        "SELECT COUNT(*)+1 as pos FROM users WHERE ball > (SELECT ball FROM users WHERE user_id=?) AND registered=1",
        (uid,)).fetchone()
    total_row = conn.execute("SELECT COUNT(*) as total FROM users WHERE registered=1").fetchone()
    conn.close()
    ball = get_ball(uid)
    pos = pos_row['pos'] if pos_row else 0
    total = total_row['total'] if total_row else 0
    text = (f"📊 *MENING O'RNIM*\n\n"
            f"👤 {get_name(uid)}\n"
            f"💰 Ball: {ball}\n"
            f"🏆 O'rin: {pos}/{total}\n"
            f"{get_unvon(ball)}\n\n"
            f"_Ko'proq ball yig'ib reytingni oshiring!_")
    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 🏁 CHALLENGE TIZIMI
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "🏁 Challenge")

def show_challenges(message):
    uid = message.from_user.id
    conn = get_conn()
    active_user_challenges = conn.execute(
        """SELECT uc.*, c.title, c.emoji, c.duration_days, c.ball_reward
           FROM user_challenges uc
           JOIN challenges c ON uc.challenge_id=c.id
           WHERE uc.user_id=? AND uc.status='active'""",
        (uid,)).fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🆕 Yangi challenge", callback_data="new_challenge"),
        types.InlineKeyboardButton("✅ Tugatilganlar", callback_data="done_challenges"))

    text = "🏁 *CHALLENGE TIZIMI*\n\n"
    if active_user_challenges:
        text += f"*Faol challengelar ({len(active_user_challenges)}):*\n\n"
        for ch in active_user_challenges:
            now = uz_time()
            end = datetime.strptime(ch['end_date'], "%Y-%m-%d")
            qoldi = (end.date() - now.date()).days
            text += (f"{ch['emoji']} *{ch['title']}*\n"
                     f"  📅 Tugaydi: {ch['end_date']} ({qoldi} kun qoldi)\n"
                     f"  💰 Mukofot: {ch['ball_reward']} ball\n\n")
    else:
        text += "_Faol challenge yo'q. Yangi boshlang!_\n"

    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "new_challenge")

def cb_new_challenge(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    conn = get_conn()
    all_challenges = conn.execute("SELECT * FROM challenges WHERE active=1 ORDER BY duration_days").fetchall()
    my_active = {r['challenge_key'] for r in conn.execute(
        "SELECT challenge_key FROM user_challenges WHERE user_id=? AND status='active'", (uid,)).fetchall()}
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in all_challenges:
        if ch['key'] in my_active:
            markup.add(types.InlineKeyboardButton(
                f"⏳ {ch['emoji']} {ch['title']} (Allaqachon faol)",
                callback_data=f"already_challenge_{ch['id']}"))
        else:
            markup.add(types.InlineKeyboardButton(
                f"{ch['emoji']} {ch['title']} — {ch['duration_days']} kun (+{ch['ball_reward']} ball)",
                callback_data=f"start_challenge_{ch['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_challenges"))

    try:
        bot.edit_message_text("🏁 *Challenge tanlang:*", call.message.chat.id,
                              call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "🏁 *Challenge tanlang:*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("start_challenge_"))

def cb_start_challenge(call):
    uid = call.from_user.id
    ch_id = int(call.data.replace("start_challenge_", ""))
    conn = get_conn()
    ch = conn.execute("SELECT * FROM challenges WHERE id=?", (ch_id,)).fetchone()
    if not ch:
        conn.close()
        bot.answer_callback_query(call.id, "❌ Topilmadi!"); return

    end_date = (uz_time() + timedelta(days=ch['duration_days'])).strftime("%Y-%m-%d")
    conn.execute("""INSERT INTO user_challenges (user_id,challenge_id,challenge_key,start_date,end_date,status)
                    VALUES (?,?,?,?,?,'active')""",
                 (uid, ch_id, ch['key'], today_str(), end_date))
    conn.commit(); conn.close()

    bot.answer_callback_query(call.id, f"🎯 Challenge boshlandi!")
    bot.send_message(uid,
        f"🏁 *Challenge boshlandi!*\n\n"
        f"{ch['emoji']} *{ch['title']}*\n"
        f"📝 {ch['description']}\n\n"
        f"📅 Boshlanish: {today_str()}\n"
        f"📅 Tugash: {end_date}\n"
        f"💰 Mukofot: {ch['ball_reward']} ball\n\n"
        f"_Har kuni rejalarni bajaring va challenge'ni tugatting!_",
        parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "done_challenges")

def cb_done_challenges(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    conn = get_conn()
    done = conn.execute(
        """SELECT uc.*, c.title, c.emoji, c.ball_reward
           FROM user_challenges uc JOIN challenges c ON uc.challenge_id=c.id
           WHERE uc.user_id=? AND uc.status='completed' ORDER BY uc.id DESC""",
        (uid,)).fetchall()
    conn.close()
    if not done:
        bot.send_message(uid, "Hali tugallangan challenge yo'q."); return
    text = "✅ *TUGALLANGAN CHALLENGELAR:*\n\n"
    for ch in done:
        text += f"{ch['emoji']} *{ch['title']}*\n  💰 +{ch['ball_reward']} ball | {ch['end_date']}\n\n"
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("already_challenge_"))

def cb_already_challenge(call):
    bot.answer_callback_query(call.id, "⏳ Bu challenge allaqachon faol!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "back_challenges")

def cb_back_challenges(call):
    bot.answer_callback_query(call.id)
    show_challenges(call.message)

# -----------------------------------------------------------------------
# 📿 ZIKR TRACKERI
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "📿 Zikr")

def section_zikr(message):
    show_zikr_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Zikr qo'shish")

def zikr_add(message):
    msg = bot.send_message(message.chat.id,
        "📿 Zikr nomini yozing:\nMisol: Subhanalloh, Alhamdulilloh, Alloh akbar",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_zikr_name)

def step_zikr_name(message):
    msg = bot.send_message(message.chat.id,
        "🔢 Maqsad soni kiriting:\nMisol: 33, 100, 500",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_zikr_count, message.text.strip())

def step_zikr_count(message, name):
    uid = message.from_user.id
    try: count = int(message.text.strip())
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "❌ Faqat raqam kiriting!")
        show_zikr_menu(uid); return
    msg = bot.send_message(uid,
        "⏰ Eslatish vaqtini kiriting (HH:MM) yoki o'tkazib yuborish uchun '0' yozing:\nMisol: `08:00`",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_zikr_time, name, count)

def step_zikr_time(message, name, target_count):
    uid = message.from_user.id
    t = message.text.strip()
    reminder_time = ""
    if t != '0':
        try: datetime.strptime(t, "%H:%M"); reminder_time = t
        except Exception as e:
            log.debug("Xatolik: %s", e)
            bot.send_message(uid, "❌ Vaqt noto'g'ri! HH:MM yoki 0:")
            show_zikr_menu(uid); return
    conn = get_conn()
    conn.execute("INSERT INTO zikrs (user_id,name,emoji,target_count,reminder_time,created) VALUES (?,?,?,?,?,?)",
                 (uid, name, "📿", target_count, reminder_time, today_str()))
    conn.commit(); conn.close()
    reminder_txt = f"⏰ Eslatish: {reminder_time}" if reminder_time else "⏰ Eslatish yo'q"
    bot.send_message(uid,
        f"✅ *Zikr qo'shildi!*\n\n"
        f"📿 *{name}*\n"
        f"🎯 Maqsad: {target_count} marta\n"
        f"{reminder_txt}",
        parse_mode="Markdown")
    add_ball(uid, 3)
    show_zikr_menu(uid)

@bot.message_handler(func=lambda m: m.text == "📿 Zikrlarim")

def view_zikrs(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute("SELECT id,name,emoji,target_count,reminder_time FROM zikrs WHERE user_id=? AND active=1", (uid,)).fetchall()
    conn.close()
    if not rows:
        bot.send_message(uid, "📿 Hali zikr qo'shilmagan."); return
    text = "📿 *ZIKRLARIM:*\n\n"
    markup = types.InlineKeyboardMarkup()
    for z in rows:
        reminder_txt = f" | ⏰{z['reminder_time']}" if z['reminder_time'] else ""
        text += f"• {z['emoji']} *{z['name']}* — {z['target_count']} marta{reminder_txt}\n"
        markup.add(types.InlineKeyboardButton(f"🗑 {z['name']}", callback_data=f"del_zikr_{z['id']}"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_zikr_"))

def cb_del_zikr(call):
    zid = int(call.data.split("_")[2])
    uid = call.from_user.id
    conn = get_conn()
    conn.execute("UPDATE zikrs SET active=0 WHERE id=? AND user_id=?", (zid, uid))
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "✅ O'chirildi!")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        log.debug("Xatolik (e'tiborga olinmadi): %s", e)

@bot.message_handler(func=lambda m: m.text == "✅ Zikr sanash")

def zikr_counting(message):
    uid = message.from_user.id
    conn = get_conn()
    rows = conn.execute("SELECT id,name,emoji,target_count FROM zikrs WHERE user_id=? AND active=1", (uid,)).fetchall()
    conn.close()
    if not rows:
        bot.send_message(uid, "📿 Avval zikr qo'shing."); return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for z in rows:
        conn = get_conn()
        today_log = conn.execute(
            "SELECT count FROM zikr_logs WHERE zikr_id=? AND sana=?", (z['id'], today_str())).fetchone()
        conn.close()
        today_count = today_log['count'] if today_log else 0
        foiz = int(today_count / z['target_count'] * 100) if z['target_count'] else 0
        bar = "█" * int(foiz/10) + "░" * (10-int(foiz/10))
        markup.add(types.InlineKeyboardButton(
            f"{z['emoji']} {z['name']}: {today_count}/{z['target_count']} [{bar[:5]}]",
            callback_data=f"zikr_count_menu_{z['id']}"))

    bot.send_message(uid, f"📿 *Bugungi Zikrlar — {today_str()}:*",
                     reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("zikr_count_menu_"))

def cb_zikr_count_menu(call):
    uid = call.from_user.id
    zid = int(call.data.replace("zikr_count_menu_", ""))
    conn = get_conn()
    z = conn.execute("SELECT * FROM zikrs WHERE id=? AND user_id=?", (zid, uid)).fetchone()
    today_log = conn.execute("SELECT count FROM zikr_logs WHERE zikr_id=? AND sana=?", (zid, today_str())).fetchone()
    conn.close()
    if not z:
        bot.answer_callback_query(call.id, "❌ Topilmadi!"); return

    today_count = today_log['count'] if today_log else 0
    foiz = int(today_count / z['target_count'] * 100) if z['target_count'] else 0
    bar = "█" * int(foiz/10) + "░" * (10-int(foiz/10))

    text = (f"📿 *{z['name']}*\n\n"
            f"Bugun: *{today_count}/{z['target_count']}*\n"
            f"[{bar}] {foiz}%\n")

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.row(
        types.InlineKeyboardButton("+1", callback_data=f"zikr_add_{zid}_1"),
        types.InlineKeyboardButton("+10", callback_data=f"zikr_add_{zid}_10"),
        types.InlineKeyboardButton("+33", callback_data=f"zikr_add_{zid}_33"))
    markup.row(
        types.InlineKeyboardButton("+100", callback_data=f"zikr_add_{zid}_100"),
        types.InlineKeyboardButton("🔄 Nollash", callback_data=f"zikr_reset_{zid}"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_zikr_list"))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("zikr_add_"))

def cb_zikr_add(call):
    uid = call.from_user.id
    parts = call.data.split("_")
    zid = int(parts[2])
    amount = int(parts[3])
    conn = get_conn()
    z = conn.execute("SELECT * FROM zikrs WHERE id=?", (zid,)).fetchone()
    existing = conn.execute("SELECT id,count FROM zikr_logs WHERE zikr_id=? AND sana=?", (zid, today_str())).fetchone()
    if existing:
        new_count = existing['count'] + amount
        conn.execute("UPDATE zikr_logs SET count=?, updated_at=? WHERE id=?", (new_count, time.time(), existing['id']))
    else:
        new_count = amount
        conn.execute("INSERT INTO zikr_logs (zikr_id,user_id,sana,count,updated_at) VALUES (?,?,?,?,?)",
                     (zid, uid, today_str(), amount, time.time()))

    # Maqsadga yetganda ball berish
    target = z['target_count'] if z else 33
    old_count = (existing['count'] if existing else 0)
    if old_count < target <= new_count:
        add_ball_conn(conn, uid, 5)
        conn.commit(); conn.close()
        bot.answer_callback_query(call.id, f"🎉 Maqsad {target} ga yetdi! +5 ball!")
    else:
        conn.commit(); conn.close()
        bot.answer_callback_query(call.id, f"+{amount} qo'shildi | Jami: {new_count}")

    # Xabarni yangilash
    call.data = f"zikr_count_menu_{zid}"
    cb_zikr_count_menu(call)

@bot.callback_query_handler(func=lambda c: c.data.startswith("zikr_reset_"))

def cb_zikr_reset(call):
    uid = call.from_user.id
    zid = int(call.data.replace("zikr_reset_", ""))
    conn = get_conn()
    conn.execute("UPDATE zikr_logs SET count=0 WHERE zikr_id=? AND sana=?", (zid, today_str()))
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "🔄 Nollandi!")
    call.data = f"zikr_count_menu_{zid}"
    cb_zikr_count_menu(call)

@bot.callback_query_handler(func=lambda c: c.data == "back_zikr_list")

def cb_back_zikr(call):
    bot.answer_callback_query(call.id)
    zikr_counting(call.message)

@bot.message_handler(func=lambda m: m.text == "📊 Zikr statistikasi")

def zikr_stats(message):
    uid = message.from_user.id
    now = uz_time()
    start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
    conn = get_conn()
    zikrs = conn.execute("SELECT id,name,emoji,target_count FROM zikrs WHERE user_id=? AND active=1", (uid,)).fetchall()
    conn.close()
    if not zikrs:
        bot.send_message(uid, "📿 Hali zikr yo'q."); return

    text = f"📊 *ZIKR STATISTIKASI (7 kun)*\n\n"
    for z in zikrs:
        conn = get_conn()
        logs = conn.execute(
            "SELECT sana, count FROM zikr_logs WHERE zikr_id=? AND sana>=? ORDER BY sana",
            (z['id'], start)).fetchall()
        conn.close()
        total = sum(l['count'] for l in logs)
        days_done = len([l for l in logs if l['count'] >= z['target_count']])
        text += f"{z['emoji']} *{z['name']}*\n"
        text += f"  🔢 Jami: {total} | 🎯 Maqsad bajarildi: {days_done}/7 kun\n"

        # Kunlik ko'rsatkich
        line = ""
        for i in range(6, -1, -1):
            d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_log = next((l for l in logs if l['sana'] == d), None)
            day_count = day_log['count'] if day_log else 0
            if day_count == 0:
                line += "⬛"
            elif day_count < z['target_count']:
                line += "🟨"
            else:
                line += "🟩"
        text += f"  {line}\n\n"

    bot.send_message(uid, text, parse_mode="Markdown")

# -----------------------------------------------------------------------
# 📦 HABIT MARKETPLACE
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "📦 Habit Marketplace")

def habit_marketplace(message):
    uid = message.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, pack in HABIT_PACKAGES.items():
        markup.add(types.InlineKeyboardButton(
            f"{pack['name']} ({len(pack['habits'])} ta odat)",
            callback_data=f"habit_pack_{key}"))
    bot.send_message(uid,
        "📦 *HABIT MARKETPLACE*\n\n"
        "_Tayyor odat paketlari. Bir tugmada qo'shing!_\n\n"
        "Paket tanlang:",
        reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("habit_pack_"))

def cb_habit_pack(call):
    uid = call.from_user.id
    pack_key = call.data.replace("habit_pack_", "")
    pack = HABIT_PACKAGES.get(pack_key)
    if not pack:
        bot.answer_callback_query(call.id, "❌ Topilmadi!"); return

    text = f"📦 *{pack['name']}*\n_{pack['description']}_\n\n*Odatlar:*\n"
    for h in pack['habits']:
        text += f"  {h['emoji']} {h['name']}\n"
    text += f"\n_Jami {len(pack['habits'])} ta odat qo'shiladi._"

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Paketni qo'shish", callback_data=f"install_pack_{pack_key}"),
        types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_marketplace"))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("install_pack_"))

def cb_install_pack(call):
    uid = call.from_user.id
    pack_key = call.data.replace("install_pack_", "")
    pack = HABIT_PACKAGES.get(pack_key)
    if not pack:
        bot.answer_callback_query(call.id, "❌ Topilmadi!"); return

    conn = get_conn()
    added = 0
    for h in pack['habits']:
        existing = conn.execute(
            "SELECT id FROM habits WHERE user_id=? AND name=? AND active=1",
            (uid, h['name'])).fetchone()
        if not existing:
            conn.execute("INSERT INTO habits (user_id,name,emoji,created) VALUES (?,?,?,?)",
                         (uid, h['name'], h['emoji'], today_str()))
            added += 1
    conn.commit(); conn.close()

    add_ball(uid, added * 3)
    bot.answer_callback_query(call.id, f"✅ {added} ta yangi odat qo'shildi!")
    bot.send_message(uid,
        f"✅ *{pack['name']} o'rnatildi!*\n\n"
        f"➕ {added} ta yangi odat qo'shildi\n"
        f"💰 +{added*3} ball\n\n"
        f"_Odatlar → Bugungi odatlar orqali bajaring!_",
        parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "back_marketplace")

def cb_back_marketplace(call):
    bot.answer_callback_query(call.id)
    habit_marketplace(call.message)

# -----------------------------------------------------------------------
# 🕌 NAMOZ BO'LIMI (mavjud)
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
        except Exception as e:
            log.debug("Xatolik: %s", e)
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

@bot.message_handler(func=lambda m: m.text == "🧭 Qibla aniqlash")

def qibla_start(message):
    msg = bot.send_message(message.chat.id,
        "🧭 Shahar nomini yozing:\n📌 Misol: `Toshkent`, `Samarqand`",
        reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_qibla)

def step_qibla(message):
    uid = message.from_user.id
    city = message.text.strip()
    try:
        city_encoded = urllib.parse.quote(city)
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city_encoded}&format=json&limit=1"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "ShaxsiyNazoratchiBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if not data:
            bot.send_message(uid, "❌ Shahar topilmadi.")
            show_namoz_menu(message.chat.id); return
        lat = float(data[0]['lat']); lon = float(data[0]['lon'])
        display_name = data[0]['display_name'].split(',')[0]
        kaba_lat = 21.4225; kaba_lon = 39.8262
        lat1 = math.radians(lat); lat2 = math.radians(kaba_lat)
        dlon = math.radians(kaba_lon - lon)
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(x, y))
        qibla = (bearing + 360) % 360
        def direction_text(deg):
            dirs = ["Shimol ⬆️","Shimoli-sharq ↗️","Sharq ➡️","Janubi-sharq ↘️",
                    "Janub ⬇️","Janubi-g'arb ↙️","G'arb ⬅️","Shimoli-g'arb ↖️"]
            return dirs[round(deg / 45) % 8]
        bot.send_message(uid,
            f"🧭 *Qibla yo'nalishi*\n\n"
            f"📍 Shahar: *{display_name}*\n"
            f"🕋 Qibla burchagi: *{qibla:.1f}°*\n"
            f"🧭 Yo'nalish: *{direction_text(qibla)}*",
            parse_mode="Markdown")
    except Exception as e:
        bot.send_message(uid, f"❌ Xatolik: {e}")
    show_namoz_menu(message.chat.id)

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
    parts = call.data.split("_", 3)
    holat = parts[1]; uid = int(parts[2])
    nom_key = parts[3] if len(parts) > 3 else ""
    nom = nom_key.replace("__", " ")
    conn = get_conn()
    conn.execute("INSERT INTO namoz_stats (user_id,namoz_nomi,sana,holat) VALUES (?,?,?,?)",
                 (uid, nom, today_str(), holat))
    conn.commit(); conn.close()
    if holat == "oqildi":
        text = f"✅ Barakalla! *{nom}* o'qildi! +10 ball"; add_ball(uid, 10)
    elif holat == "endi_oqiyman":
        text = f"⏳ *{nom}* namozini o'qing!"; add_ball(uid, 3)
    else:
        text = f"🔄 *{nom}* qazo sifatida belgilandi."; add_ball(uid, 2)
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    except Exception as e:
        log.debug("Xatolik: %s", e)
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
    except Exception as e:
        log.debug("Xatolik: %s", e)
        msg = bot.send_message(uid, "❌ Vaqt noto'g'ri! HH:MM formatda:")
        bot.register_next_step_handler(msg, step_daily_time, task_name); return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for k in KATEGORIYALAR:
        markup.add(types.InlineKeyboardButton(k, callback_data=f"cat_{k}_{task_name}_{t}"))
    bot.send_message(uid, "📂 Kategoriyani tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))

def cb_category(call):
    parts = call.data.split("_", 3)
    cat = parts[1]; task_name = parts[2]; t = parts[3]
    uid = call.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=3)
    for label, val in MUHIMLIK.items():
        markup.add(types.InlineKeyboardButton(label, callback_data=f"pri_{val}_{cat}_{task_name}_{t}"))
    try: bot.edit_message_text("⚡ Muhimlik darajasini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "⚡ Muhimlik darajasini tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pri_"))

def cb_priority(call):
    parts = call.data.split("_", 4)
    priority = parts[1]; cat = parts[2]; task_name = parts[3]; t = parts[4]
    uid = call.from_user.id
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
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, f"✅ Reja saqlandi!\n📌 *{task_name}*\n⏰ {t} | {cat} | {pri_icon}", parse_mode="Markdown")
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
    bajarildi = sum(1 for r in rows if r['status']==1)
    text = f"📋 *Bugungi rejalar — {today_str()}:*\n"
    text += f"✅ {bajarildi}/{len(rows)} bajarildi\n\n"
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
    except Exception as e:
        log.debug("Xatolik: %s", e)
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
    except Exception as e:
        log.debug("Xatolik (e'tiborga olinmadi): %s", e)

# -----------------------------------------------------------------------
# 🎯 ODATLAR (HABIT TRACKER)
# -----------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "🎯 Odatlar")

def section_habits(message):
    show_habits_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "➕ Odat qo'shish")

def habit_add(message):
    msg = bot.send_message(message.chat.id,
        "🎯 Odat nomini yozing:\nMisol: Suv ichish, Kitob o'qish",
        reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_habit_name)

def step_habit_name(message):
    uid = message.from_user.id; name = message.text.strip()
    msg = bot.send_message(uid, "Emoji tanlang (1 ta emoji yoki Enter):\nMisol: 💧 📚 🏃")
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
    except Exception as e:
        log.debug("Xatolik (e'tiborga olinmadi): %s", e)

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
    done_count = 0
    for h in habits:
        done = conn.execute("SELECT done FROM habit_logs WHERE habit_id=? AND sana=?", (h['id'], today_str())).fetchone()
        is_done = done and done['done']
        if is_done: done_count += 1
        status = "✅" if is_done else "⬜"
        markup.add(types.InlineKeyboardButton(
            f"{status} {h['emoji']} {h['name']}",
            callback_data=f"habit_toggle_{h['id']}"))
    conn.close()
    bot.send_message(uid,
        f"📅 *Bugungi odatlar — {today_str()}:*\n✅ {done_count}/{len(habits)} bajarildi",
        reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("habit_toggle_"))

def cb_habit_toggle(call):
    hid = int(call.data.split("_")[2]); uid = call.from_user.id
    conn = get_conn()
    existing = conn.execute("SELECT id,done FROM habit_logs WHERE habit_id=? AND sana=?", (hid, today_str())).fetchone()
    if existing:
        new_done = 0 if existing['done'] else 1
        conn.execute("UPDATE habit_logs SET done=? WHERE id=?", (new_done, existing['id']))
        if new_done: add_ball_conn(conn, uid, 5)
        else: add_ball_conn(conn, uid, -5)
    else:
        conn.execute("INSERT INTO habit_logs (habit_id,user_id,sana,done) VALUES (?,?,?,1)", (hid, uid, today_str()))
        add_ball_conn(conn, uid, 5)
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
    msg = bot.send_message(message.chat.id, "🏆 Maqsad nomini yozing:",
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, step_goal_title)

def step_goal_title(message):
    msg = bot.send_message(message.chat.id, "📅 Muddat (kun soni):\nMisol: `30`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_goal_deadline, message.text.strip())

def step_goal_deadline(message, title):
    uid = message.from_user.id
    try: days = int(message.text.strip())
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "❌ Faqat raqam!"); return
    deadline = (uz_time() + timedelta(days=days)).strftime("%Y-%m-%d")
    msg = bot.send_message(uid, "🎁 Maqsad bajarilib mukofot nima?")
    bot.register_next_step_handler(msg, step_goal_reward, title, deadline)

def step_goal_reward(message, title, deadline):
    uid = message.from_user.id
    conn = get_conn()
    conn.execute("INSERT INTO goals (user_id,title,deadline,reward,created,ball_reward) VALUES (?,?,?,?,?,?)",
                 (uid, title, deadline, message.text.strip(), today_str(), 100))
    conn.commit(); conn.close()
    bot.send_message(uid,
        f"✅ *Maqsad qo'shildi!*\n🎯 *{title}*\n📅 Muddat: {deadline}\n💰 +100 ball",
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
            f"🎉 *TABRIKLAYMIZ!*\n✅ *{goal['title']}* bajarildi!\n"
            f"🎁 {goal['reward']}\n💰 +{goal['ball_reward']} ball!",
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
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎁 O'zimga mukofot berish", callback_data="add_reward"))
    bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "add_reward")

def cb_add_reward(call):
    uid = call.from_user.id
    msg = bot.send_message(uid, f"🎁 Mukofot nomi:\n💰 Joriy ball: {get_ball(uid)}")
    bot.register_next_step_handler(msg, step_reward_name)

def step_reward_name(message):
    uid = message.from_user.id
    msg = bot.send_message(uid, f"Necha ball sarflaysiz? (Joriy: {get_ball(uid)} ball)")
    bot.register_next_step_handler(msg, step_reward_ball, message.text.strip())

def step_reward_ball(message, name):
    uid = message.from_user.id
    try: cost = int(message.text.strip())
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, "❌ Faqat raqam!"); return
    ball = get_ball(uid)
    if cost > ball:
        bot.send_message(uid, f"❌ Yetarli ball yo'q! Sizda {ball} ball bor."); return
    conn = get_conn()
    conn.execute("INSERT INTO rewards (user_id,title,ball_cost,created) VALUES (?,?,?,?)", (uid, name, cost, today_str()))
    conn.execute("UPDATE users SET ball = ball - ? WHERE user_id=?", (cost, uid))
    conn.commit(); conn.close()
    bot.send_message(uid, f"🎉 *Mukofot!*\n🎁 {name}\n💰 -{cost} ball\nQoldi: {ball-cost}", parse_mode="Markdown")
    show_goals_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "💰 Ballarim")

def show_balls(message):
    uid = message.from_user.id
    ball = get_ball(uid)
    unvon = get_unvon(ball)
    level = get_level(ball)
    keyingi_b, keyingi_n = keyingi_unvon(ball)
    text = (f"💰 *BALL TIZIMI*\n\n"
            f"💰 Joriy ball: *{ball}*\n"
            f"🏅 Unvon: {unvon}\n"
            f"⭐ Daraja: {level}/8\n")
    if keyingi_b:
        text += f"⬆️ Keyingi: {keyingi_n} ({keyingi_b-ball} ball qoldi)\n"
    text += ("\n*Ball qanday yig'iladi:*\n"
             "✅ Namoz o'qildi: +10 ball\n"
             "📝 Reja bajarildi: +15 ball\n"
             "🎯 Odat bajarildi: +5 ball\n"
             "📿 Zikr maqsadiga yetdi: +5 ball\n"
             "🏆 Maqsad bajarildi: +100 ball\n"
             "📅 Haftalik 100%: +50 ball\n"
             "\n*Jarima tizimi:*\n"
             "❌ Bajarilmagan reja: -5 ball\n"
             "🔴 Streak buzildi: ogohlantirish\n")
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
    if gtype == "weekly":   send_weekly_chart(uid)
    elif gtype == "monthly": send_monthly_chart(uid)
    elif gtype == "namoz":   send_namoz_chart(uid)

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
        bar = "🟩"*int(foiz/10) + "⬜"*(10-int(foiz/10))
        kun = datetime.strptime(d, "%Y-%m-%d").strftime("%d-%b")
        text += f"📅 {kun}\n{bar} {foiz}% ({b}/{j})\n\n"
    conn.close()
    bot.send_message(uid, text, parse_mode="Markdown")

def send_monthly_chart(uid):
    now = uz_time()
    text = "🗓 *OYLIK REJA GRAFIGI (4 hafta)*\n\n"
    conn = get_conn()
    for w in range(3, -1, -1):
        end_d = (now - timedelta(days=w*7)).strftime("%Y-%m-%d")
        start_d = (now - timedelta(days=w*7+6)).strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana>=? AND sana<=?",
            (uid, start_d, end_d)).fetchone()
        j = row['j'] or 0; b = row['b'] or 0
        foiz = int(b/j*100) if j else 0
        bar = "🟦"*int(foiz/10) + "⬜"*(10-int(foiz/10))
        text += f"📆 {4-w}-hafta ({start_d[5:]} — {end_d[5:]})\n{bar} {foiz}% ({b}/{j})\n\n"
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
    for row in rows: d[row['holat']] = row['cnt']
    total = sum(d.values())
    if not total:
        bot.send_message(uid, "Namoz ma'lumoti yo'q."); return
    oq_f = int(d['oqildi']/total*100) if total else 0
    en_f = int(d['endi_oqiyman']/total*100) if total else 0
    qaz_f = int(d['qazo']/total*100) if total else 0
    text = "🕌 *NAMOZ GRAFIGI (7 kun)*\n\n"
    text += f"✅ O'qildi:     {'🟩'*int(oq_f/10)}{'⬛'*(10-int(oq_f/10))} {oq_f}% ({d['oqildi']} ta)\n\n"
    text += f"⏳ Endi:       {'🟨'*int(en_f/10)}{'⬛'*(10-int(en_f/10))} {en_f}% ({d['endi_oqiyman']} ta)\n\n"
    text += f"🔄 Qazo:       {'🟥'*int(qaz_f/10)}{'⬛'*(10-int(qaz_f/10))} {qaz_f}% ({d['qazo']} ta)\n\n"
    text += f"📌 Jami: {total} ta namoz belgilandi"
    bot.send_message(uid, text, parse_mode="Markdown")

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
    namoz_d = _namoz_block(uid, start, end)
    score, _ = calculate_intizom(uid)
    text = f"📈 *KUNLIK HISOBOT — {today_str()}*\n\n"
    text += f"💯 Intizom indeksi: *{score}/100* {intizom_rang(score)}\n\n"
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
        bar = "█"*int(f/10) + "░"*(10-int(f/10))
        text += f"  ✅ {b}/{j} ({f}%)\n  [{bar}]\n"
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
    score, _ = calculate_intizom(uid)
    text = f"🗓 *OYLIK HISOBOT — {now.strftime('%B %Y')}*\n_{start} — {end}_\n\n"
    text += f"💯 Intizom: *{score}/100*\n\n"
    t_b = sum((r['bajardi'] or 0) for r in task_rows)
    t_j = sum(r['jami'] for r in task_rows)
    foiz = int(t_b/t_j*100) if t_j else 0
    text += f"📋 *Rejalar:* {t_b}/{t_j} ({foiz}%)\n"
    if task_rows:
        best = max(task_rows, key=lambda r: (r['bajardi'] or 0)/r['jami'] if r['jami'] else 0)
        worst = min(task_rows, key=lambda r: (r['bajardi'] or 0)/r['jami'] if r['jami'] else 1)
        text += f"  🌟 Eng yaxshi kun: {best['sana']}\n"
        text += f"  📉 Eng kam kun: {worst['sana']}\n"
    text += "\n🕌 *Namoz:*\n"
    if namoz_d:
        jami_n = sum(namoz_d.values()); oq = namoz_d.get('oqildi',0)
        foiz_n = int(oq/jami_n*100) if jami_n else 0
        text += f"  ✅ O'qildi: {oq} ({foiz_n}%)\n"
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
        # Jarima: -5 ball
        add_ball(uid, -5)
        text = "❌ Vazifa bajarilmadi. -5 ball. Ertaga urinib ko'ring!"
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except Exception as e:
        log.debug("Xatolik: %s", e)
        bot.send_message(uid, text)

# -----------------------------------------------------------------------
# ⏰ TAYMER
# -----------------------------------------------------------------------

def schedule_checker():
    last_minute = ""
    while True:
        conn = None
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
                    except Exception as e:
                        log.debug("Xatolik (e'tiborga olinmadi): %s", e)
                    conn.execute("DELETE FROM namoz_times WHERE user_id=?", (uid,))
                    conn.commit(); continue
                NAMOZ_MAP = {'Bomdod ☁️':nrow['bomdod'],'Peshin 🌞':nrow['peshin'],'Asr 🌤':nrow['asr'],'Shom 🌆':nrow['shom'],'Xufton 🌃':nrow['xufton']}
                if is_cycle_day(conn, uid, today_str()):
                    continue  # 🌙 Bu kunlar — namoz eslatmalari yuborilmaydi
                for nom, vaqt in NAMOZ_MAP.items():
                    if vaqt == current_time:
                        try:
                            bot.send_message(uid, f"🕌 *Namoz vaqti: {nom}*\n⏰ {vaqt}", parse_mode="Markdown")
                            conn.execute("INSERT INTO namoz_notify (user_id,namoz_nomi,notified_at) VALUES (?,?,?)", (uid, nom, time.time()))
                            conn.commit()
                        except Exception as e:
                            log.debug("Xatolik (e'tiborga olinmadi): %s", e)

            # 2. NAMOZ 20 DAQIQA TEKSHIRUVI
            notify_rows = conn.execute("SELECT id,user_id,namoz_nomi FROM namoz_notify WHERE asked=0 AND notified_at<?", (time.time()-20*60,)).fetchall()
            for nr in notify_rows:
                uid = nr['user_id']; nom = nr['namoz_nomi']
                if is_cycle_day(conn, uid, today_str()):
                    conn.execute("UPDATE namoz_notify SET asked=1 WHERE id=?", (nr['id'],))
                    conn.commit(); continue
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
                except Exception as e:
                    log.debug("Xatolik (e'tiborga olinmadi): %s", e)

            # 3. KUNLIK REJA ESLATMALARI
            daily_remind = conn.execute(
                "SELECT id,user_id,task_name,priority FROM daily_tasks WHERE sana=? AND task_time=? AND notified=0",
                (today_str(), current_time)).fetchall()
            for dr in daily_remind:
                pri_icon = {"shoshilinch":"🔴","orta":"🟡","oddiy":"🟢"}.get(dr['priority'],"🟢")
                try:
                    bot.send_message(dr['user_id'],
                        f"🔔 *Eslatma!* {pri_icon}\n📌 {dr['task_name']} vaqti bo'ldi!",
                        parse_mode="Markdown")
                    conn.execute("UPDATE daily_tasks SET notified=1, notified_at=? WHERE id=?", (time.time(), dr['id']))
                    conn.commit()
                except Exception as e:
                    log.debug("Xatolik (e'tiborga olinmadi): %s", e)

            # 4. HAFTALIK REJA ESLATMALARI
            weekly_rows = conn.execute("SELECT user_id,task_name,task_time FROM weekly_tasks WHERE active=1 AND task_time=?", (current_time,)).fetchall()
            for wr in weekly_rows:
                uid = wr['user_id']
                existing = conn.execute("SELECT id FROM daily_tasks WHERE user_id=? AND task_name=? AND sana=? AND source='weekly'", (uid, wr['task_name'], today_str())).fetchone()
                if not existing:
                    conn.execute("INSERT INTO daily_tasks (user_id,task_name,task_time,sana,source,notified,notified_at) VALUES (?,?,?,?,'weekly',1,?)", (uid, wr['task_name'], wr['task_time'], today_str(), time.time()))
                    conn.commit()
                try: bot.send_message(uid, f"📅 *Haftalik reja:*\n📌 {wr['task_name']}", parse_mode="Markdown")
                except Exception as e:
                    log.debug("Xatolik (e'tiborga olinmadi): %s", e)

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
                    bot.send_message(cr['user_id'],
                        f"❓ 45 daqiqa o'tdi.\n*'{cr['task_name']}'* bajarildimi?\n\n"
                        f"⚠️ *Yo'q* deb javob bersangiz -5 ball jarima!",
                        reply_markup=markup, parse_mode="Markdown")
                    conn.execute("UPDATE daily_tasks SET verified=1 WHERE id=?", (cr['id'],))
                    conn.commit()
                except Exception as e:
                    log.debug("Xatolik (e'tiborga olinmadi): %s", e)

            # 6. ZIKR ESLATMALARI
            zikr_reminders = conn.execute(
                "SELECT DISTINCT z.user_id, z.name, z.emoji FROM zikrs z WHERE z.active=1 AND z.reminder_time=? AND z.reminder_time != ''",
                (current_time,)).fetchall()
            for zr in zikr_reminders:
                try:
                    bot.send_message(zr['user_id'],
                        f"📿 *Zikr vaqti!*\n{zr['emoji']} *{zr['name']}* aytish vaqti!\n\n_📿 Zikr → ✅ Zikr sanash_",
                        parse_mode="Markdown")
                except Exception as e:
                    log.debug("Xatolik (e'tiborga olinmadi): %s", e)

            # 7. CHALLENGE TEKSHIRUVI
            expired_challenges = conn.execute(
                "SELECT uc.id, uc.user_id, c.title, c.emoji, c.ball_reward, uc.start_date, uc.end_date "
                "FROM user_challenges uc JOIN challenges c ON uc.challenge_id=c.id "
                "WHERE uc.status='active' AND uc.end_date<?",
                (today_str(),)).fetchall()
            for ch in expired_challenges:
                uid = ch['user_id']
                # Challenge tugadi — natijani tekshirish
                start = ch['start_date']; end = ch['end_date']
                task_rows = conn.execute(
                    "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana>=? AND sana<=?",
                    (uid, start, end)).fetchone()
                j = task_rows['j'] or 0; b = task_rows['b'] or 0
                foiz = int(b/j*100) if j else 0
                if foiz >= 70:  # 70% bajarildi = challenge muvaffaqiyatli
                    conn.execute("UPDATE user_challenges SET status='completed' WHERE id=?", (ch['id'],))
                    add_ball_conn(conn, uid, ch['ball_reward'])
                    conn.commit()
                    try:
                        bot.send_message(uid,
                            f"🎉 *CHALLENGE YAKUNLANDI!*\n\n"
                            f"{ch['emoji']} *{ch['title']}*\n"
                            f"📊 Natija: {b}/{j} ({foiz}%)\n"
                            f"💰 *+{ch['ball_reward']} ball qo'shildi!*",
                            parse_mode="Markdown")
                    except Exception as e:
                        log.debug("Xatolik (e'tiborga olinmadi): %s", e)
                else:
                    conn.execute("UPDATE user_challenges SET status='failed' WHERE id=?", (ch['id'],))
                    conn.commit()
                    try:
                        bot.send_message(uid,
                            f"😔 *Challenge tugadi*\n\n"
                            f"{ch['emoji']} *{ch['title']}*\n"
                            f"📊 Natija: {b}/{j} ({foiz}%)\n"
                            f"_(Muvaffaqiyat uchun 70% kerak edi)_\n\n"
                            f"💪 Qaytadan boshlashingiz mumkin!",
                            parse_mode="Markdown")
                    except Exception as e:
                        log.debug("Xatolik (e'tiborga olinmadi): %s", e)

            # 8. AVTOMATIK HISOBOTLAR — har bir foydalanuvchi o'zi belgilagan
            # "kun yakuni" vaqtiga ko'ra (sozlamada o'zgartirilishi mumkin)
            all_users = conn.execute("SELECT user_id, day_end_time FROM users WHERE registered=1").fetchall()

            for u in all_users:
                day_end = u['day_end_time'] or '22:00'

                # Kechki AI hisobot — foydalanuvchining kun yakuni vaqtida
                if current_time == day_end:
                    try:
                        report = generate_ai_report(u['user_id'])
                        bot.send_message(u['user_id'], report, parse_mode="Markdown")
                    except Exception as e:
                        log.debug("Xatolik (e'tiborga olinmadi): %s", e)

                    # Haftalik hisobot — yakshanba kuni, xuddi shu vaqtda
                    if now.weekday() == 6:
                        try: send_weekly_report(u['user_id'])
                        except Exception as e:
                            log.debug("Xatolik (e'tiborga olinmadi): %s", e)

                    # Oylik hisobot — oyning oxirgi kuni, xuddi shu vaqtda
                    tomorrow = now + timedelta(days=1)
                    if tomorrow.month != now.month:
                        try: send_monthly_report(u['user_id'])
                        except Exception as e:
                            log.debug("Xatolik (e'tiborga olinmadi): %s", e)

                # 9. JARIMA TIZIMI — kun yakunidan 1.5 soat o'tib, bajarilmagan
                # rejalar uchun ball jarimasi (har bir foydalanuvchi uchun shaxsiy vaqtda)
                if current_time == hhmm_plus(day_end, 90):
                    uid = u['user_id']
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM daily_tasks "
                        "WHERE user_id=? AND sana=? AND status IS NULL AND notified=1",
                        (uid, today_str())).fetchone()
                    cnt = row['cnt'] or 0
                    if cnt > 0:
                        penalty = min(cnt * 5, 50)  # Max 50 ball jarima
                        add_ball_conn(conn, uid, -penalty)
                        conn.commit()
                        try:
                            bot.send_message(uid,
                                f"⚠️ *JARIMA TIZIMI*\n\n"
                                f"❌ Bugun {cnt} ta reja bajarilmadi\n"
                                f"💰 -{penalty} ball jarima qo'llanildi\n\n"
                                f"_Ertaga barcha rejalarni bajaring!_",
                                parse_mode="Markdown")
                        except Exception as e:
                            log.debug("Xatolik (e'tiborga olinmadi): %s", e)

            time.sleep(5)
        except Exception as e:
            log.exception("[TAYMER] kutilmagan xatolik")
            time.sleep(10)
        finally:
            if conn:
                conn.close()

# -----------------------------------------------------------------------
# 🌐 WEB API (Mini App uchun)
# -----------------------------------------------------------------------
from urllib.parse import parse_qsl, urlparse

api = Flask(__name__, static_folder='.', static_url_path='')

# 🔒 CORS — frontend (index.html) shu serverning o'zidan xizmat qiladi,
# shuning uchun aslida CORS shart emas. Faqat MINI_APP_URL domeniga
# ruxsat beramiz (wildcard "*" o'rniga), tashqi saytlar API'ga
# to'g'ridan-to'g'ri murojaat qilolmasin.
_allowed_origin = "*"
if MINI_APP_URL:
    _p = urlparse(MINI_APP_URL)
    if _p.scheme and _p.netloc:
        _allowed_origin = f"{_p.scheme}://{_p.netloc}"
CORS(api, resources={r"/api/*": {"origins": _allowed_origin}})

# 🔌 Har bir HTTP so'rovi uchun BITTA baza ulanishi — so'rov tugagach
# (xatolik chiqsa ham) avtomatik yopiladi. Bu oldingi versiyadagi "agar
# funksiya o'rtasida xato chiqsa, ulanish hech qachon yopilmaydi" muammosini
# butunlay bartaraf etadi.

def request_db():
    if 'db' not in g:
        g.db = get_conn()
    return g.db

@api.teardown_request

def close_request_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

NAMOZ_KEY_MAP = {
    'bomdod': 'Bomdod ☁️', 'peshin': 'Peshin 🌞', 'asr': 'Asr 🌤',
    'shom': 'Shom 🌆', 'xufton': 'Xufton 🌃'
}
NAMOZ_KEY_MAP_REV = {v: k for k, v in NAMOZ_KEY_MAP.items()}
NAMOZ_HOLAT_TO_DB  = {'oqildi': 'oqildi', 'endi': 'endi_oqiyman', 'qazo': 'qazo'}
NAMOZ_HOLAT_TO_APP = {'oqildi': 'oqildi', 'endi_oqiyman': 'endi', 'qazo': 'qazo'}
NAMOZ_BALL = {'oqildi': 10, 'endi_oqiyman': 3, 'qazo': 2}

INIT_DATA_MAX_AGE = 24 * 60 * 60  # 24 soat — shundan eski initData rad etiladi

def validate_init_data(init_data_str):
    try:
        if not init_data_str: return None
        parsed = dict(parse_qsl(init_data_str, keep_blank_values=True))
        hash_received = parsed.pop('hash', None)
        if not hash_received: return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", API_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if computed_hash != hash_received: return None
        auth_date = parsed.get('auth_date')
        if not auth_date or (time.time() - int(auth_date)) > INIT_DATA_MAX_AGE:
            return None
        user_json = parsed.get('user')
        if not user_json: return None
        return json.loads(user_json)
    except Exception:
        return None

def ensure_user(uid, name):
    conn = request_db()
    row = conn.execute("SELECT user_id FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row:
        conn.execute("INSERT INTO users (user_id,name,registered,ball) VALUES (?,?,1,0)", (uid, name))
        conn.execute("INSERT OR IGNORE INTO avatar (user_id) VALUES (?)", (uid,))
        conn.commit()

def get_request_user():
    if request.method == 'GET':
        init_data = request.args.get('init_data')
    else:
        body = request.get_json(silent=True) or {}
        init_data = body.get('init_data')
    user = validate_init_data(init_data)
    if not user: return None
    uid = user['id']
    name = user.get('first_name', 'Foydalanuvchi')
    ensure_user(uid, name)
    return uid

@api.route('/')

def serve_index():
    from flask import send_file
    return send_file('index.html')

@api.route('/health')

def health():
    return "Bot ishlayapti! ✅"

@api.route('/api/data')

def api_data():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    urow = conn.execute("SELECT name,ball,gender,theme,day_end_time FROM users WHERE user_id=?", (uid,)).fetchone()
    name = urow['name']; ball = urow['ball']
    unvon = get_unvon(ball)
    level = get_level(ball)
    next_ball, next_unvon = keyingi_unvon(ball)

    # Barcha og'ir hisob-kitoblar bitta ulanish orqali
    score, _ = calculate_intizom(uid, conn=conn)
    av = get_avatar(uid, conn=conn)

    daily = conn.execute(
        "SELECT id,task_name,task_time,status,category,priority FROM daily_tasks WHERE user_id=? AND sana=? ORDER BY task_time",
        (uid, today_str())).fetchall()
    weekly = conn.execute(
        "SELECT id,task_name,task_time,category,priority FROM weekly_tasks WHERE user_id=? AND active=1 ORDER BY task_time",
        (uid,)).fetchall()
    nt = conn.execute("SELECT bomdod,peshin,asr,shom,xufton,saved_at FROM namoz_times WHERE user_id=?", (uid,)).fetchone()
    namoz_times = None; namoz_days_left = None
    if nt:
        namoz_times = {k: nt[k] for k in ['bomdod','peshin','asr','shom','xufton']}
        saved = datetime.strptime(nt['saved_at'], "%Y-%m-%d")
        namoz_days_left = max(0, 7-(uz_time().date()-saved.date()).days)
    today_namoz_rows = conn.execute("SELECT namoz_nomi,holat FROM namoz_stats WHERE user_id=? AND sana=?", (uid, today_str())).fetchall()
    namoz_today = {}
    for r in today_namoz_rows:
        key = NAMOZ_KEY_MAP_REV.get(r['namoz_nomi'])
        if key: namoz_today[key] = NAMOZ_HOLAT_TO_APP.get(r['holat'], r['holat'])
    start7 = (uz_time()-timedelta(days=6)).strftime("%Y-%m-%d")
    week_rows = conn.execute("SELECT holat, COUNT(*) as cnt FROM namoz_stats WHERE user_id=? AND sana>=? GROUP BY holat", (uid, start7)).fetchall()
    namoz_week = {'oqildi':0,'endi':0,'qazo':0}
    for r in week_rows:
        k = NAMOZ_HOLAT_TO_APP.get(r['holat'], r['holat'])
        if k in namoz_week: namoz_week[k] = r['cnt']
    namoz_streak = compute_namoz_streak(conn, uid)
    cycle_today = is_cycle_day(conn, uid, today_str())

    # Odatlar + streak — BITTA SQL so'rov bilan (oldin har odat uchun
    # alohida while loop bor edi, u O(odatlar × kunlar) edi)
    habit_rows = conn.execute(
        "SELECT id,name,emoji FROM habits WHERE user_id=? AND active=1", (uid,)).fetchall()
    habits = []
    if habit_rows:
        # So'nggi 30 kun uchun barcha loglarni bir martada yuklaymiz
        start30 = (uz_time().date() - timedelta(days=29)).strftime("%Y-%m-%d")
        logs_raw = conn.execute(
            "SELECT habit_id, sana, done FROM habit_logs "
            "WHERE user_id=? AND sana>=? ORDER BY habit_id, sana DESC",
            (uid, start30)).fetchall()
        # Odat → kun → done lug'ati
        from collections import defaultdict
        log_map = defaultdict(dict)
        for lr in logs_raw:
            log_map[lr['habit_id']][lr['sana']] = lr['done']

        today_s = today_str()
        for h in habit_rows:
            hid = h['id']
            done_today = bool(log_map[hid].get(today_s))
            # Streak: ketma-ket kunlarni sanab chiqamiz
            streak = 0
            d = uz_time().date()
            for _ in range(30):
                ds = d.strftime("%Y-%m-%d")
                if log_map[hid].get(ds):
                    streak += 1
                else:
                    break
                d -= timedelta(days=1)
            habits.append({"id": hid, "name": h['name'], "emoji": h['emoji'],
                           "done": done_today, "streak": streak})

    goal_rows = conn.execute("SELECT id,title,deadline,reward,status,created,ball_reward FROM goals WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    reward_rows = conn.execute("SELECT id,title,ball_cost,created FROM rewards WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    zikr_rows = conn.execute("SELECT z.id,z.name,z.emoji,z.target_count,COALESCE(zl.count,0) as today_count FROM zikrs z LEFT JOIN zikr_logs zl ON z.id=zl.zikr_id AND zl.sana=? WHERE z.user_id=? AND z.active=1", (today_str(), uid)).fetchall()
    active_challenges = conn.execute(
        "SELECT uc.id,c.title,c.emoji,c.ball_reward,uc.start_date,uc.end_date FROM user_challenges uc JOIN challenges c ON uc.challenge_id=c.id WHERE uc.user_id=? AND uc.status='active'",
        (uid,)).fetchall()
    return jsonify({
        "user": {"id": uid, "name": name, "ball": ball, "gender": urow['gender'],
                  "theme": urow['theme'] or 'dark', "day_end_time": urow['day_end_time'] or '22:00'},
        "unvon": unvon, "level": level, "next_unvon": next_unvon, "next_ball": next_ball,
        "intizom_score": score, "intizom_rang": intizom_rang(score),
        "avatar": dict(av),
        "today": today_str(),
        "daily_tasks": [dict(t) for t in daily],
        "weekly_tasks": [dict(t) for t in weekly],
        "namoz_times": namoz_times, "namoz_days_left": namoz_days_left,
        "namoz_today": namoz_today, "namoz_week": namoz_week,
        "namoz_streak": namoz_streak, "cycle_today": cycle_today,
        "habits": habits,
        "goals": [dict(g) for g in goal_rows],
        "rewards": [dict(r) for r in reward_rows],
        "zikrs": [dict(z) for z in zikr_rows],
        "active_challenges": [dict(c) for c in active_challenges],
    })

@api.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    if request.method == 'GET':
        row = conn.execute("SELECT gender,theme,day_end_time FROM users WHERE user_id=?", (uid,)).fetchone()
        return jsonify(dict(row) if row else {})

    body = request.get_json(force=True) or {}
    updates = []
    params = []
    if 'gender' in body and body['gender'] in ('erkak', 'ayol'):
        updates.append("gender=?"); params.append(body['gender'])
    if 'theme' in body and body['theme'] in ('dark', 'light'):
        updates.append("theme=?"); params.append(body['theme'])
    if 'day_end_time' in body:
        t = str(body['day_end_time'])
        if re.match(r'^\d{2}:\d{2}$', t):
            h, m = int(t[:2]), int(t[3:])
            if 0 <= h <= 23 and 0 <= m <= 59:
                updates.append("day_end_time=?"); params.append(t)
    if not updates:
        return jsonify({"error": "invalid"}), 400
    params.append(uid)
    conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id=?", params)
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/cycle/toggle', methods=['POST'])
def api_cycle_toggle():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    sana = today_str()
    if is_cycle_day(conn, uid, sana):
        conn.execute("DELETE FROM cycle_days WHERE user_id=? AND sana=?", (uid, sana))
        conn.commit()
        return jsonify({"ok": True, "cycle_today": False})
    conn.execute("INSERT OR IGNORE INTO cycle_days (user_id, sana) VALUES (?,?)", (uid, sana))
    conn.commit()
    return jsonify({"ok": True, "cycle_today": True})

@api.route('/api/stats/trend')
def api_stats_trend():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    days_n = 14
    out = []
    d = uz_time().date()
    for i in range(days_n - 1, -1, -1):
        ds = (d - timedelta(days=i)).strftime("%Y-%m-%d")
        trow = conn.execute(
            "SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=?",
            (uid, ds)).fetchone()
        vazifa_foiz = round((trow['b'] or 0) / trow['j'] * 100) if trow['j'] else None
        if is_cycle_day(conn, uid, ds):
            namoz_foiz = None
        else:
            nrow = conn.execute(
                "SELECT COUNT(*) as cnt FROM namoz_stats WHERE user_id=? AND sana=? AND holat='oqildi'",
                (uid, ds)).fetchone()
            namoz_foiz = round((nrow['cnt'] or 0) / 5 * 100)
        score, _ = calculate_intizom(uid, ds, conn=conn)
        out.append({"sana": ds, "vazifa_foiz": vazifa_foiz, "namoz_foiz": namoz_foiz, "intizom": score})
    return jsonify({"days": out})

@api.route('/api/task/add', methods=['POST'])

def api_task_add():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    name = (body.get('name') or '').strip()
    task_time = (body.get('time') or '').strip()
    category = body.get('category') or 'Umumiy'
    priority = body.get('priority') or 'oddiy'
    if not name or not task_time: return jsonify({"error": "invalid"}), 400
    conn = request_db()
    conn.execute("INSERT INTO daily_tasks (user_id,task_name,task_time,sana,source,category,priority) VALUES (?,?,?,?,'daily',?,?)",
                 (uid, name, task_time, today_str(), category, priority))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/task/toggle', methods=['POST'])

def api_task_toggle():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    tid = body.get('id')
    conn = request_db()
    row = conn.execute("SELECT status FROM daily_tasks WHERE id=? AND user_id=?", (tid, uid)).fetchone()
    if not row: return jsonify({"error": "not_found"}), 404
    if row['status'] == 1:
        conn.execute("UPDATE daily_tasks SET status=NULL WHERE id=?", (tid,))
        add_ball_conn(conn, uid, -15)
    else:
        conn.execute("UPDATE daily_tasks SET status=1, verified=1 WHERE id=?", (tid,))
        add_ball_conn(conn, uid, 15)
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/task/delete', methods=['POST'])

def api_task_delete():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    tid = (request.get_json(force=True) or {}).get('id')
    conn = request_db()
    conn.execute("DELETE FROM daily_tasks WHERE id=? AND user_id=?", (tid, uid))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/namoz/times', methods=['POST'])

def api_namoz_times():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    names = ['bomdod','peshin','asr','shom','xufton']
    vals = {}
    for n in names:
        v = (body.get(n) or '').strip()
        if not v: return jsonify({"error": "invalid"}), 400
        vals[n] = v
    conn = request_db()
    conn.execute("INSERT OR REPLACE INTO namoz_times (user_id,bomdod,peshin,asr,shom,xufton,saved_at) VALUES (?,?,?,?,?,?,?)",
                 (uid, vals['bomdod'],vals['peshin'],vals['asr'],vals['shom'],vals['xufton'], today_str()))
    add_ball_conn(conn, uid, 5)
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/namoz/mark', methods=['POST'])

def api_namoz_mark():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    key = body.get('namoz'); holat_app = body.get('holat')
    if key not in NAMOZ_KEY_MAP: return jsonify({"error": "invalid"}), 400
    namoz_nomi = NAMOZ_KEY_MAP[key]
    conn = request_db()
    existing = conn.execute("SELECT id,holat FROM namoz_stats WHERE user_id=? AND namoz_nomi=? AND sana=?",
                            (uid, namoz_nomi, today_str())).fetchone()
    if existing:
        add_ball_conn(conn, uid, -NAMOZ_BALL.get(existing['holat'], 0))
        conn.execute("DELETE FROM namoz_stats WHERE id=?", (existing['id'],))
    if holat_app:
        holat_db = NAMOZ_HOLAT_TO_DB.get(holat_app)
        if holat_db:
            conn.execute("INSERT INTO namoz_stats (user_id,namoz_nomi,sana,holat) VALUES (?,?,?,?)",
                         (uid, namoz_nomi, today_str(), holat_db))
            add_ball_conn(conn, uid, NAMOZ_BALL.get(holat_db, 0))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/habit/add', methods=['POST'])

def api_habit_add():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    name = (body.get('name') or '').strip()
    emoji = body.get('emoji') or '✅'
    if not name: return jsonify({"error": "invalid"}), 400
    conn = request_db()
    conn.execute("INSERT INTO habits (user_id,name,emoji,created) VALUES (?,?,?,?)", (uid, name, emoji, today_str()))
    add_ball_conn(conn, uid, 5)
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/habit/toggle', methods=['POST'])

def api_habit_toggle():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    hid = (request.get_json(force=True) or {}).get('id')
    conn = request_db()
    habit = conn.execute("SELECT id FROM habits WHERE id=? AND user_id=? AND active=1", (hid, uid)).fetchone()
    if not habit:
        return jsonify({"error": "not_found"}), 404
    existing = conn.execute("SELECT id,done FROM habit_logs WHERE habit_id=? AND user_id=? AND sana=?",
                            (hid, uid, today_str())).fetchone()
    if existing:
        new_done = 0 if existing['done'] else 1
        conn.execute("UPDATE habit_logs SET done=? WHERE id=?", (new_done, existing['id']))
        add_ball_conn(conn, uid, 5 if new_done else -5)
    else:
        conn.execute("INSERT INTO habit_logs (habit_id,user_id,sana,done) VALUES (?,?,?,1)", (hid, uid, today_str()))
        add_ball_conn(conn, uid, 5)
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/goal/add', methods=['POST'])

def api_goal_add():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    title = (body.get('title') or '').strip(); reward = (body.get('reward') or '').strip()
    try: days = int(body.get('days'))
    except (ValueError, TypeError): days = 0
    if not title or not reward or days <= 0: return jsonify({"error": "invalid"}), 400
    deadline = (uz_time() + timedelta(days=days)).strftime("%Y-%m-%d")
    conn = request_db()
    conn.execute("INSERT INTO goals (user_id,title,deadline,reward,created,ball_reward) VALUES (?,?,?,?,?,100)",
                 (uid, title, deadline, reward, today_str()))
    add_ball_conn(conn, uid, 10)
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/goal/complete', methods=['POST'])

def api_goal_complete():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    gid = (request.get_json(force=True) or {}).get('id')
    conn = request_db()
    goal_row = conn.execute("SELECT ball_reward,status FROM goals WHERE id=? AND user_id=?", (gid, uid)).fetchone()
    if not goal_row or goal_row['status'] == 'done': return jsonify({"error": "not_found"}), 404
    conn.execute("UPDATE goals SET status='done' WHERE id=?", (gid,))
    add_ball_conn(conn, uid, goal_row['ball_reward'])
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/intizom')

def api_intizom():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    score, details = calculate_intizom(uid, conn=conn)
    return jsonify({"score": score, "rang": intizom_rang(score), "details": details})

@api.route('/api/rating')

def api_rating():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    rows = conn.execute("SELECT user_id,name,ball FROM users WHERE registered=1 ORDER BY ball DESC LIMIT 10").fetchall()
    result = []
    for i, row in enumerate(rows):
        result.append({"pos": i+1, "name": row['name'], "ball": row['ball'], "is_me": row['user_id']==uid})
    return jsonify({"leaderboard": result})

@api.route('/api/report')

def api_report():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    period = request.args.get('period', 'daily')
    now = uz_time()
    if period == 'daily':
        days = [today_str()]
    elif period == 'weekly':
        days = [(now-timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6,-1,-1)]
    else:
        first = now.strftime("%Y-%m-01"); days = []
        d = datetime.strptime(first, "%Y-%m-%d")
        while d.date() <= now.date():
            days.append(d.strftime("%Y-%m-%d")); d += timedelta(days=1)
    conn = request_db()
    chart = []; total_t = done_t = namoz_t = 0
    for ds in days:
        row = conn.execute("SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=?", (uid,ds)).fetchone()
        j = row['j'] or 0; b = row['b'] or 0; total_t += j; done_t += b
        nm = conn.execute("SELECT COUNT(*) FROM namoz_stats WHERE user_id=? AND sana=? AND holat='oqildi'", (uid,ds)).fetchone()[0]
        namoz_t += nm
        chart.append({"label": ds[5:], "total": j, "done": b})
    return jsonify({"total": total_t, "done": done_t, "namoz": namoz_t, "chart": chart})

@api.route('/api/weekly/add', methods=['POST'])

def api_weekly_add():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    name = (body.get('name') or '').strip()
    task_time = (body.get('time') or '').strip()
    category = body.get('category') or 'Umumiy'
    priority = body.get('priority') or 'oddiy'
    if not name or not task_time: return jsonify({"error": "invalid"}), 400
    conn = request_db()
    conn.execute("INSERT INTO weekly_tasks (user_id,task_name,task_time,category,priority,active) VALUES (?,?,?,?,?,1)",
                 (uid, name, task_time, category, priority))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/weekly/delete', methods=['POST'])

def api_weekly_delete():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    tid = (request.get_json(force=True) or {}).get('id')
    conn = request_db()
    conn.execute("UPDATE weekly_tasks SET active=0 WHERE id=? AND user_id=?", (tid, uid))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/zikr/add', methods=['POST'])

def api_zikr_add():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    name = (body.get('name') or '').strip()
    emoji = body.get('emoji') or '📿'
    try: target = int(body.get('target') or 33)
    except (ValueError, TypeError): target = 33
    if not name: return jsonify({"error": "invalid"}), 400
    conn = request_db()
    conn.execute("INSERT INTO zikrs (user_id,name,emoji,target_count,active) VALUES (?,?,?,?,1)",
                 (uid, name, emoji, target))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/zikr/click', methods=['POST'])

def api_zikr_click():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True)
    zid = body.get('id')
    try: amount = int(body.get('amount') or 1)
    except (ValueError, TypeError): amount = 1
    if amount not in [1, 10, 33, 100]: amount = 1
    conn = request_db()
    z = conn.execute("SELECT id FROM zikrs WHERE id=? AND user_id=? AND active=1", (zid, uid)).fetchone()
    if not z: return jsonify({"error": "not_found"}), 404
    existing = conn.execute("SELECT id,count FROM zikr_logs WHERE zikr_id=? AND sana=?", (zid, today_str())).fetchone()
    if existing:
        new_count = existing['count'] + amount
        conn.execute("UPDATE zikr_logs SET count=? WHERE id=?", (new_count, existing['id']))
    else:
        conn.execute("INSERT INTO zikr_logs (zikr_id,user_id,sana,count) VALUES (?,?,?,?)", (zid, uid, today_str(), amount))
    if amount >= 33:
        add_ball_conn(conn, uid, 2)
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/challenge/list')

def api_challenge_list():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    challenges = conn.execute("SELECT id,title,emoji,description,duration_days,ball_reward FROM challenges WHERE active=1").fetchall()
    joined = {r['challenge_id'] for r in conn.execute("SELECT challenge_id FROM user_challenges WHERE user_id=? AND status='active'", (uid,)).fetchall()}
    result = []
    for c in challenges:
        result.append({**dict(c), "joined": c['id'] in joined})
    return jsonify({"challenges": result})

@api.route('/api/challenge/join', methods=['POST'])

def api_challenge_join():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    cid = (request.get_json(force=True) or {}).get('id')
    conn = request_db()
    c = conn.execute("SELECT id,duration_days FROM challenges WHERE id=? AND active=1", (cid,)).fetchone()
    if not c: return jsonify({"error": "not_found"}), 404
    already = conn.execute("SELECT id FROM user_challenges WHERE user_id=? AND challenge_id=? AND status='active'", (uid, cid)).fetchone()
    if already: return jsonify({"error": "already_joined"}), 400
    start = today_str()
    end = (uz_time() + timedelta(days=c['duration_days'])).strftime("%Y-%m-%d")
    conn.execute("INSERT INTO user_challenges (user_id,challenge_id,start_date,end_date,status) VALUES (?,?,?,?,'active')",
                 (uid, cid, start, end))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/store/list')

def api_store_list():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    items = conn.execute(
        "SELECT id,name,emoji,description,ball_cost AS price,item_type,required_level "
        "FROM store_items WHERE active=1 ORDER BY ball_cost").fetchall()
    bought = {r['item_id'] for r in conn.execute("SELECT item_id FROM user_items WHERE user_id=?", (uid,)).fetchall()}
    urow = conn.execute("SELECT ball FROM users WHERE user_id=?", (uid,)).fetchone()
    my_level = get_level(urow['ball'] if urow else 0)
    result = []
    for item in items:
        d = dict(item)
        d["owned"] = item['id'] in bought
        d["locked"] = my_level < (item['required_level'] or 1)
        result.append(d)
    return jsonify({"items": result})

@api.route('/api/store/buy', methods=['POST'])

def api_store_buy():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    item_id = (request.get_json(force=True) or {}).get('id')
    conn = request_db()
    item = conn.execute(
        "SELECT id,name,ball_cost AS price,item_type,required_level "
        "FROM store_items WHERE id=? AND active=1", (item_id,)).fetchone()
    if not item: return jsonify({"error": "not_found"}), 404
    already = conn.execute("SELECT id FROM user_items WHERE user_id=? AND item_id=?", (uid, item_id)).fetchone()
    if already: return jsonify({"error": "already_owned"}), 400
    urow = conn.execute("SELECT ball FROM users WHERE user_id=?", (uid,)).fetchone()
    if not urow: return jsonify({"error": "not_found"}), 404
    if get_level(urow['ball']) < (item['required_level'] or 1):
        return jsonify({"error": "level_too_low"}), 400
    if urow['ball'] < item['price']:
        return jsonify({"error": "insufficient_ball"}), 400
    add_ball_conn(conn, uid, -item['price'])
    conn.execute("INSERT INTO user_items (user_id,item_id,bought_at) VALUES (?,?,?)", (uid, item_id, today_str()))
    if item['item_type'] == 'avatar_style':
        conn.execute("UPDATE avatar SET style=? WHERE user_id=?", (item['name'], uid))
    elif item['item_type'] == 'frame':
        conn.execute("UPDATE avatar SET frame=? WHERE user_id=?", (item['name'], uid))
    elif item['item_type'] == 'badge':
        conn.execute("UPDATE avatar SET badge=? WHERE user_id=?", (item['name'], uid))
    conn.commit()
    return jsonify({"ok": True})

@api.route('/api/heatmap')

def api_heatmap():
    uid = get_request_user()
    if uid is None: return jsonify({"error": "unauthorized"}), 401
    conn = request_db()
    days = []
    now = uz_time()
    for i in range(29, -1, -1):
        ds = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        row = conn.execute("SELECT COUNT(*) as j, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as b FROM daily_tasks WHERE user_id=? AND sana=?", (uid, ds)).fetchone()
        total = row['j'] or 0; done = row['b'] or 0
        pct = round(done / total * 100) if total > 0 else 0
        days.append({"date": ds, "total": total, "done": done, "pct": pct})
    return jsonify({"days": days})

def run_bot_polling():
    """Bot polling — alohida daemon thread'da ishlaydi."""
    while True:
        try:
            log.info("🤖 Bot polling boshlandi...")
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            log.warning("[POLLING] %s — 10 soniyadan keyin qayta uriniladi", e)
            time.sleep(10)

# -----------------------------------------------------------------------
# 🎬 ISHGA TUSHIRISH
# -----------------------------------------------------------------------
if __name__ == "__main__":
    log.info("✅ Shaxsiy Nazoratchi bot ishga tushmoqda (UTC+5)")

    # 1) Scheduler — fon thread'i
    t_sched = threading.Thread(target=schedule_checker, daemon=True, name="scheduler")
    t_sched.start()
    log.info("⏰ Taymer (scheduler) ishga tushdi")

    # 2) Bot polling — fon thread'i
    t_bot = threading.Thread(target=run_bot_polling, daemon=True, name="bot-polling")
    t_bot.start()
    log.info("🤖 Bot polling thread ishga tushdi")

    # 3) Flask (Mini App API) — ASOSIY JARAYON
    # Render health check (/health) uchun Flask asosiy jarayonda ishlashi kerak.
    # flask.run() bloklovchi — shuning uchun eng oxirida chaqiriladi.
    port = int(os.environ.get("PORT", 8080))
    log.info("🌐 Flask API server port=%d da ishga tushmoqda...", port)
    api.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)
