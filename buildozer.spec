[app]

# نام اپلیکیشن
title = Hokm Iranian

# نام پکیج
package.name = hokmirani

# دامنه پکیج
package.domain = org.irangames.hokm

# مسیر کد منبع
source.dir = .

# فایل‌های شامل شونده
source.include_exts = py,png,jpg,kv,atlas,ttf

# نسخه برنامه
version = 1.0.0

# وابستگی‌های پایتون برای اندروید
requirements = python3==3.11,kivy==2.3.1

# جهت صفحه
orientation = landscape

# تمام‌صفحه
fullscreen = 0

# مجوزهای اندروید
android.permissions = INTERNET

# نسخه API اندروید
android.api = 34
android.minapi = 21

# معماری‌های پردازنده اندروید
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
