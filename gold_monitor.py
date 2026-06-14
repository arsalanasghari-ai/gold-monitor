import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

# ===== تنظیمات =====
TELEGRAM_TOKEN = "6731449392:AAFxOdUbYCbNPUyn7D2QtJbAVukuB32aHgI"
CHAT_ID = "6253650988"
PRICE_FILE = "last_price.json"
THRESHOLD = 2.0  # درصد نوسان

def get_gold_price():
    """دریافت قیمت طلای ۱۸ عیار از tala.ir"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get("https://www.tala.ir/", headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # پیدا کردن قیمت طلای ۱۸ عیار
        items = soup.find_all("div", class_="item")
        for item in items:
            title = item.find("div", class_="title")
            if title and "۱۸" in title.text:
                price_div = item.find("div", class_="price")
                if price_div:
                    price_text = price_div.text.strip().replace(",", "").replace("٬", "")
                    # تبدیل اعداد فارسی به انگلیسی
                    persian_nums = "۰۱۲۳۴۵۶۷۸۹"
                    english_nums = "0123456789"
                    for p, e in zip(persian_nums, english_nums):
                        price_text = price_text.replace(p, e)
                    return int(''.join(filter(str.isdigit, price_text)))
    except Exception as e:
        print(f"خطا در دریافت قیمت: {e}")
    return None

def load_last_price():
    """خواندن قیمت قبلی از فایل"""
    if os.path.exists(PRICE_FILE):
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return data.get("price"), data.get("date")
    return None, None

def save_price(price):
    """ذخیره قیمت فعلی در فایل"""
    with open(PRICE_FILE, "w") as f:
        json.dump({
            "price": price,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }, f)

def send_telegram(message):
    """ارسال پیام به تلگرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    response = requests.post(url, data=data, timeout=10)
    return response.json()

def main():
    print(f"⏰ بررسی قیمت طلا - {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # دریافت قیمت فعلی
    current_price = get_gold_price()
    if not current_price:
        print("❌ خطا در دریافت قیمت طلا")
        return

    print(f"💰 قیمت فعلی طلای ۱۸ عیار: {current_price:,} تومان")

    # خواندن قیمت قبلی
    last_price, last_date = load_last_price()

    if last_price is None:
        # اولین بار اجرا میشه
        save_price(current_price)
        send_telegram(
            f"🤖 <b>مانیتور طلا فعال شد!</b>\n\n"
            f"💰 قیمت طلای ۱۸ عیار: <b>{current_price:,} تومان</b>\n"
            f"📊 هشدار نوسان بیش از {THRESHOLD}% فعاله\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        print("✅ قیمت اول ذخیره شد و پیام فعال‌سازی ارسال شد")
        return

    # محاسبه درصد تغییر
    change_percent = ((current_price - last_price) / last_price) * 100

    print(f"📊 قیمت قبلی: {last_price:,} تومان (در {last_date})")
    print(f"📈 تغییر: {change_percent:.2f}%")

    if abs(change_percent) >= THRESHOLD:
        # تعیین نوع نوسان
        if change_percent > 0:
            emoji = "📈🔴"
            direction = "رشد"
        else:
            emoji = "📉🟢"
            direction = "ریزش"

        message = (
            f"{emoji} <b>هشدار نوسان طلا!</b>\n\n"
            f"💰 قیمت فعلی: <b>{current_price:,} تومان</b>\n"
            f"💰 قیمت قبلی: <b>{last_price:,} تومان</b>\n"
            f"📊 میزان {direction}: <b>{abs(change_percent):.2f}%</b>\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        send_telegram(message)
        print(f"✅ هشدار ارسال شد! تغییر: {change_percent:.2f}%")

        # ذخیره قیمت جدید
        save_price(current_price)
    else:
        print(f"✅ نوسان در حد نرمال ({change_percent:.2f}%) - هشدار ارسال نشد")
        # هر بار قیمت رو آپدیت کن
        save_price(current_price)

if __name__ == "__main__":
    main()
