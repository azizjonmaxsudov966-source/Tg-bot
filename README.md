# 🤖 Shaxsiy Nazoratchi Bot

## 📁 Fayllar
```
bot.py           — Asosiy bot kodi
requirements.txt — Python kutubxonalari
render.yaml      — Render konfiguratsiyasi
README.md        — Bu fayl
```

---

## 🚀 GitHub + Render orqali ishga tushirish

### 1️⃣ GitHub'ga yuklash
```bash
git init
git add .
git commit -m "Initial bot deploy"
git remote add origin https://github.com/SIZNING_USERNAME/bot-repo.git
git push -u origin main
```

### 2️⃣ Render.com'da sozlash
1. https://render.com — Ro'yxatdan o'ting
2. **New → Background Worker** tanlang
3. GitHub reponi ulang
4. Quyidagi sozlamalarni kiriting:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`

### 3️⃣ Environment Variables (Render Dashboard → Environment)
| Key | Value |
|-----|-------|
| `BOT_TOKEN` | `Telegram botingiz tokeni` |
| `KANAL_ID` | `@kanal_username` |
| `KANAL_LINKI` | `https://t.me/kanal_username` |
| `DB_PATH` | `/var/data/bot_data.db` |

### 4️⃣ Disk qo'shish (ma'lumotlar o'chmasligi uchun)
Render Dashboard → **Disks** → **Add Disk**:
- **Mount Path:** `/var/data`
- **Size:** 1 GB

---

## ✨ Bot imkoniyatlari

| Bo'lim | Imkoniyat |
|--------|-----------|
| 📝 Kunlik reja | Reja qo'shish, ko'rish, 45 daqiqa tekshiruv |
| 📅 Haftalik reja | 1 marta kiritiladi, har kuni eslatiladi |
| 🕌 Namoz | Vaqt kiritish (7 kun), 20 daqiqa tekshiruv, 3 javob varianti |
| 📊 Hisobotlar | Kunlik/Haftalik/Oylik — reja + namoz statistikasi |

## ⏰ Avtomatik hisobotlar
- **22:00** — Kunlik hisobot
- **Yakshanba 21:00** — Haftalik hisobot  
- **Oy oxirgi kuni 21:30** — Oylik hisobot

> Barcha vaqtlar O'zbekiston vaqti (UTC+5) bilan ishlaydi.
