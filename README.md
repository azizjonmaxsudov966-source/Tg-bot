# 🤖 Shaxsiy Nazoratchi Bot

## 📁 Fayllar
```
bot.py           — Asosiy bot kodi
index.html       — Mini App (Telegram WebApp) frontendi
requirements.txt — Python kutubxonalari
render.yaml      — Render konfiguratsiyasi
README.md        — Bu fayl
```

---

## 🔐 Xavfsizlik — MUHIM

- **Bot tokenini hech qachon kodga yozmang.** U faqat Render Dashboard → Environment
  qismida `BOT_TOKEN` sifatida saqlanadi. Agar oldin tokenni `bot.py` ichiga
  yozib GitHub'ga (hatto private repo bo'lsa ham) yuklagan bo'lsangiz, u allaqachon
  oshkor bo'lgan hisoblanadi — @BotFather'da `/revoke` qilib yangi token oling.
- `/reset_db` kabi xavfli buyruqlar endi faqat `ADMIN_IDS`'da ko'rsatilgan
  Telegram ID'larga ruxsat beradi (pastga qarang).

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
2. **New → Web Service** tanlang (render.yaml shu turga mos sozlangan)
3. GitHub reponi ulang
4. Quyidagi sozlamalarni kiriting:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`

> ⚠️ **Bepul (Free) tarif haqida:** Bot Telegramga webhook orqali emas,
> doimiy so'rov (`long polling`) orqali ulanadi, ya'ni Telegram bu xizmatga
> hech qachon HTTP so'rov yubormaydi. Render'ning bepul Web Service'lari esa
> 15 daqiqa davomida tashqi HTTP trafik kelmasa "uxlab qoladi" — shu sabab
> eslatmalar va navbatchi (scheduler) vaqti-vaqti bilan to'xtab qolishi mumkin.
> Doimiy ishlashi uchun pullik (Starter va undan yuqori) tarifga o'tish tavsiya
> etiladi. Bepul tarifda qolish kerak bo'lsa, tashqi "uptime monitor" xizmati
> orqali `/health`'ni har 10-15 daqiqada chaqirib turish vaqtincha yordam beradi
> (lekin pastdagi disk cheklovini bartaraf etmaydi).

### 3️⃣ Environment Variables (Render Dashboard → Environment)
| Key | Value |
|-----|-------|
| `BOT_TOKEN` | Telegram botingiz tokeni (BotFather'dan) |
| `ADMIN_IDS` | Sizning Telegram ID'ingiz (bir nechta bo'lsa vergul bilan: `123,456`) |
| `KANAL_ID` | `@kanal_username` |
| `KANAL_LINKI` | `https://t.me/kanal_username` |
| `DB_PATH` | `/var/data/bot_data.db` |
| `MINI_APP_URL` | Mini App ochiladigan to'liq URL (masalan: `https://your-app.onrender.com`) |

> 🆔 O'z Telegram ID'ingizni bilish uchun [@userinfobot](https://t.me/userinfobot)
> ga `/start` yozing.

### 4️⃣ Disk qo'shish (ma'lumotlar o'chmasligi uchun)
Render Dashboard → **Disks** → **Add Disk**:
- **Mount Path:** `/var/data`
- **Size:** 1 GB

> ⚠️ **Diqqat:** Render'ning rasmiy hujjatlariga ko'ra, doimiy disk (persistent
> disk) faqat **pullik** instance turlariga ulanadi. Bepul (Free) Web Service'da
> disk ulash imkoni yo'q — shu sababli SQLite bazasi har bir qayta deploy/restartda
> butunlay tozalanadi. Ma'lumotlarni doimiy saqlash uchun pullik tarifga o'tish shart.

---

## ✨ Bot imkoniyatlari

| Bo'lim | Imkoniyat |
|--------|-----------|
| 📝 Kunlik reja | Reja qo'shish, ko'rish, 45 daqiqa tekshiruv |
| 📅 Haftalik reja | 1 marta kiritiladi, har kuni eslatiladi |
| 🕌 Namoz | Vaqt kiritish (7 kun), 20 daqiqa tekshiruv, 3 javob varianti |
| 📊 Hisobotlar | Kunlik/Haftalik/Oylik — reja + namoz statistikasi |
| 🛒 Do'kon | Avatar/ramka/nishon — ball va daraja asosida |
| 🏁 Challenge | 7/21/30 kunlik challengelar |

## ⏰ Avtomatik hisobotlar
- **22:00** — Kunlik hisobot
- **Yakshanba 21:00** — Haftalik hisobot  
- **Oy oxirgi kuni 21:30** — Oylik hisobot

> Barcha vaqtlar O'zbekiston vaqti (UTC+5) bilan ishlaydi.

---

## 🛠️ Bu versiyada tuzatilgan kamchiliklar
- Bot tokeni kodga yozilmaydi, faqat `BOT_TOKEN` muhit o'zgaruvchisidan o'qiladi (token bo'lmasa, bot aniq xato bilan ishga tushmaydi).
- `/reset_db` endi faqat `ADMIN_IDS`'dagi foydalanuvchilarga ruxsat beradi.
- Mini App'dagi **Do'kon** va **Challenge** bo'limlarini "no such column" xatosidan tuzatildi (ustun nomlari bazaga moslashtirildi).
- `habit/toggle` endi haqiqatan mavjud va foydalanuvchiga tegishli odatni tekshiradi (avval ixtiyoriy `id` bilan ball "ishlab olish" mumkin edi).
- Do'kondagi `required_level` talabi endi haqiqatan tekshiriladi.
- Telegram WebApp `initData`'ning eskirgan (24 soatdan ortiq) nusxalari endi rad etiladi.
- API CORS sozlamasi `*` o'rniga faqat `MINI_APP_URL` domeniga cheklandi.
- Barcha "jim yutilgan" xatoliklar (`except: pass`) loglanadigan qilindi, shuningdek baza ulanishlari xatolik yuz berganda ham to'g'ri yopiladi (`try/finally`).

