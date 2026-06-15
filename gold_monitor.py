import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
PRICE_FILE = "last_price.json"
THRESHOLD = 2.0

def get_gold_price():
    """دریافت قیمت طلای ۱۸ عیار از BrsApi"""
    try:
        # API key آزمایشی رایگان
        api_key = "FreeSV0E1LSgB9RDjuf0QorSLViX8pPG"
        url = f"https://Api.BrsApi.ir/Market/Gold_Currency.php?key={api_key}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:300]}")
        
        data = r.json()
        
        # پیدا کردن طلای ۱۸ عیار در response
        if isinstance(data, list):
            for item in data:
                name = str(item.get('name', '') or item.get('title', ''))
                if '18' in name or 'geram18' in str(item).lower():
                    price_str = str(item.get('price', '') or item.get('value', '')).replace(',', '')
                    if price_str.isdigit():
                        price = int(price_str)
                        if 50_000_000 < price < 600_000_000:
                            print(f"✅ قیمت: {price:,} ریال - {name}")
                            return price
        elif isinstance(data, dict):
            # شاید کلید مستقیم داشته باشه
            for key, val in data.items():
                if '18' in str(key):
                    price_str = str(val).replace(',', '')
                    if price_str.isdigit():
                        price = int(price_str)
                        if 50_000_000 < price < 600_000_000:
                            return price

    except Exception as e:
        print(f"خطا BrsApi: {e}")
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

    print(f"💰 قیمت: {current_price:,} ریال")
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
