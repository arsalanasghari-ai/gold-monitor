import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
PRICE_FILE = "last_price.json"
THRESHOLD = 2.0

def get_xau_price_usd():
    """قیمت اونس طلا به دلار"""

    # روش اول: gold-api.com (رایگان، بدون key)
    try:
        r = requests.get(
            "https://gold-api.com/price/XAU",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        print(f"gold-api: {r.text[:200]}")
        data = r.json()
        price = float(data.get('price', 0))
        if 1000 < price < 10000:
            print(f"✅ اونس طلا: ${price}")
            return price
    except Exception as e:
        print(f"خطا gold-api: {e}")

    # روش دوم: freegoldapi.com (CSV)
    try:
        r = requests.get(
            "https://freegoldapi.com/data/latest.csv",
            timeout=15
        )
        lines = r.text.strip().split('\n')
        last_line = lines[-1]
        price = float(last_line.split(',')[1])
        if 1000 < price < 10000:
            print(f"✅ اونس طلا (freegoldapi): ${price}")
            return price
    except Exception as e:
        print(f"خطا freegoldapi: {e}")

    # روش سوم: مقدار ثابت تقریبی
    print("⚠️ استفاده از قیمت پیش‌فرض اونس: $3300")
    return 3300.0

def get_usd_to_rial():
    """نرخ دلار به ریال"""
    try:
        r = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=15
        )
        data = r.json()
        rate = data['rates'].get('IRR', 0)
        if rate > 100000:
            print(f"✅ نرخ دلار: {rate:,.0f} ریال")
            return rate
    except Exception as e:
        print(f"خطا exchange rate: {e}")
    
    print("⚠️ استفاده از نرخ پیش‌فرض دلار: 900,000 ریال")
    return 900000.0

def get_gold_price():
    """قیمت طلای ۱۸ عیار به ریال"""
    xau_usd = get_xau_price_usd()
    usd_rial = get_usd_to_rial()
    
    # هر گرم طلای ۱۸ عیار = (اونس × نرخ دلار × 0.75) / 31.1035
    price = (xau_usd * usd_rial * 0.75) / 31.1035
    print(f"📊 اونس: ${xau_usd} | دلار: {usd_rial:,.0f} | گرم ۱۸ عیار: {price:,.0f} ریال")
    
    if 50_000_000 < price < 600_000_000:
        return int(price)
    return None

def load_last_price():
    if os.path.exists(PRICE_FILE):
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return data.get("price"), data.get("date")
    return None, None

def save_price(price):
    with open(PRICE_FILE, "w") as f:
        json.dump({"price": price, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}, f)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    r = requests.post(url, data=data, timeout=10)
    print(f"تلگرام: {r.json().get('ok')}")

def main():
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    current_price = get_gold_price()

    if not current_price:
        print("❌ خطا در دریافت قیمت")
        send_telegram("⚠️ خطا در دریافت قیمت طلا")
        return

    print(f"💰 قیمت نهایی: {current_price:,} ریال")
    last_price, last_date = load_last_price()

    if last_price is None:
        save_price(current_price)
        send_telegram(
            f"🤖 <b>مانیتور طلا فعال شد!</b>\n\n"
            f"💰 طلای ۱۸ عیار: <b>{current_price:,} ریال</b>\n"
            f"📊 هشدار نوسان بیش از {THRESHOLD}%\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        print("✅ قیمت اول ذخیره شد")
        return

    change_percent = ((current_price - last_price) / last_price) * 100
    print(f"📊 قبلی: {last_price:,} | تغییر: {change_percent:.2f}%")

    if abs(change_percent) >= THRESHOLD:
        emoji = "📈🔴" if change_percent > 0 else "📉🟢"
        direction = "رشد" if change_percent > 0 else "ریزش"
        send_telegram(
            f"{emoji} <b>هشدار نوسان طلا!</b>\n\n"
            f"💰 قیمت فعلی: <b>{current_price:,} ریال</b>\n"
            f"💰 قیمت قبلی: <b>{last_price:,} ریال</b>\n"
            f"📊 {direction}: <b>{abs(change_percent):.2f}%</b>\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        print("✅ هشدار ارسال شد!")
    else:
        print("✅ نوسان نرمال")

    save_price(current_price)

if __name__ == "__main__":
    main()
