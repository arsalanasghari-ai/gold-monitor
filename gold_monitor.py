import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")
PRICE_FILE = "last_price.json"
THRESHOLD = 2.0

def get_gold_price():
    """قیمت طلای ۱۸ عیار به ریال از goldapi.io"""
    try:
        headers = {
            "x-access-token": GOLDAPI_KEY,
            "Content-Type": "application/json"
        }
        r = requests.get(
            "https://www.goldapi.io/api/XAU/IRR",
            headers=headers,
            timeout=15
        )
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:300]}")
        
        data = r.json()
        
        # قیمت هر اونس به ریال
        price_per_oz = float(data.get('price', 0))
        
        # تبدیل به گرم طلای ۱۸ عیار
        # هر اونس = 31.1035 گرم، طلای ۱۸ عیار = 75%
        price_per_gram_18k = (price_per_oz * 0.75) / 31.1035
        
        print(f"✅ اونس به ریال: {price_per_oz:,.0f}")
        print(f"✅ گرم ۱۸ عیار: {price_per_gram_18k:,.0f} ریال")
        
        if 50_000_000 < price_per_gram_18k < 600_000_000:
            return int(price_per_gram_18k)
            
    except Exception as e:
        print(f"خطا goldapi: {e}")
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
