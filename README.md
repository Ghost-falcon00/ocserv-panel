# OCServ Panel

<div align="center">
  <img src="https://img.shields.io/badge/OCServ-Panel-6366f1?style=for-the-badge" alt="OCServ Panel">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</div>

<div align="center">
  <h3>🌐 پنل مدیریت حرفه‌ای OCServ VPN</h3>
  <p>مدیریت آسان کاربران، محدودیت حجم و زمان، با رابط کاربری مدرن</p>
</div>

---

## ✨ امکانات

- 🔐 **مدیریت کاربران**: ایجاد، ویرایش، حذف و مدیریت کاربران VPN
- 📊 **محدودیت حجم**: تعیین حجم ترافیک برای هر کاربر با قطع خودکار
- ⏰ **محدودیت زمان**: تنظیم تاریخ انقضا برای هر کاربر
- 👥 **اتصال همزمان**: محدود کردن تعداد دستگاه‌های همزمان
- 📈 **داشبورد**: آمار real-time با نمودارهای زیبا
- 📝 **لاگ‌ها**: مشاهده تاریخچه اتصالات
- ⚙️ **تنظیمات**: مدیریت کامل تنظیمات OCServ با راهنمای فارسی
- 🌙 **تم تیره/روشن**: رابط کاربری مدرن با پشتیبانی از حالت تاریک
- 🔒 **SSL رایگان**: دریافت خودکار گواهی Let's Encrypt

---

## 🚀 نصب سریع

```bash
bash <(curl -sL https://raw.githubusercontent.com/Ghost-falcon00/ocserv-panel/main/install.sh)
```

### پیش‌نیازها
- Ubuntu 20.04+ یا Debian 11+
- دسترسی root
- یک IP عمومی
- (اختیاری) دامنه متصل به سرور

---

## 📸 تصاویر

### داشبورد
![Dashboard](docs/screenshots/dashboard.png)

### مدیریت کاربران
![Users](docs/screenshots/users.png)

### تنظیمات
![Settings](docs/screenshots/settings.png)

---

## 🔧 دستورات

```bash
# شروع پنل
systemctl start ocserv-panel

# توقف پنل
systemctl stop ocserv-panel

# راه‌اندازی مجدد
systemctl restart ocserv-panel

# مشاهده لاگ
journalctl -u ocserv-panel -f
```

---

## 🌐 اتصال کلاینت

### Android
1. نصب برنامه **Cisco AnyConnect** از Google Play
2. وارد کردن آدرس سرور
3. ورود با نام کاربری و رمز عبور

### iOS
1. نصب برنامه **Cisco AnyConnect** از App Store
2. اضافه کردن اتصال جدید با آدرس سرور
3. ورود با اطلاعات کاربری

### Windows
1. دانلود **OpenConnect GUI** از [اینجا](https://github.com/openconnect/openconnect-gui/releases)
2. اضافه کردن پروفایل جدید
3. وارد کردن آدرس سرور و اتصال

### Linux
```bash
sudo openconnect --protocol=anyconnect YOUR_SERVER_IP
```

---

## 📁 ساختار پروژه

```
ocserv-panel/
├── install.sh          # اسکریپت نصب
├── panel/
│   ├── app.py          # اپلیکیشن FastAPI
│   ├── config.py       # تنظیمات
│   ├── models/         # مدل‌های دیتابیس
│   ├── services/       # سرویس‌ها
│   ├── api/            # API endpoints
│   ├── templates/      # قالب‌های HTML
│   └── static/         # فایل‌های استاتیک
└── README.md
```

---

## 🛠️ توسعه

```bash
# Clone repository
git clone https://github.com/Ghost-falcon00/ocserv-panel.git
cd ocserv-panel/panel

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app:app --reload --port 8443
```

---

## 🤝 مشارکت

مشارکت‌ها مورد استقبال هستند! لطفاً:

1. Fork کنید
2. یک branch جدید بسازید
3. تغییرات خود را اعمال کنید
4. Pull Request بفرستید

---

## 📄 مجوز

این پروژه تحت مجوز MIT منتشر شده است.

---

## ⭐ حمایت

اگر این پروژه برایتان مفید بود، لطفاً یک ستاره بدهید!

---

<div align="center">
  <p>ساخته شده با ❤️ برای جامعه فارسی‌زبان</p>
</div>
