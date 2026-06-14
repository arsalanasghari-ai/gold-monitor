import requests
import json
import os
from datetime import datetime

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "6731449392:AAFxOdUbYCbNPUyn7D2QtJbAVukuB32aHgI")
CHAT_ID = os.environ.get("CHAT_ID", "6253650988")
PRICE_FILE = "last_price.json"
THRESHOLD = 2.0

def get_gold_price():
    """دریافت قیمت طلای ۱۸ عیار از tgju.org"""
    try:
        url = "https://www.tgju.org/profile/geram18"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        # استخراج قیمت از JSON داخل صفحه
        import re
        # دنبال عدد قیمت در صفحه میگردیم
        pattern = r'"last_trade_price"\s*:\s*"?([\d,]+)"?'
        match = re.search(pattern, response.text)
        
        if match:
            price_str = match.group(1).replace(',', '').replace('٬', '')
            return int(price_str)
        
        # روش دوم: استخراج از meta یا title
        pattern2 = r'geram18.*?(\d{8,12})'
        match2 = re.search(pattern2, response.text)
        if match2:
            return int(match2.group(1))
            
    except Exception as e:
        print(f"خطا در دریافت قیمت: {e}")
    return None

def get_gold_price_api():
    """روش دوم: API مستقیم tgju"""
    try:
        url = "https://www.tgju.org/json/indicator/geram18"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.tgju.org/"
        }
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        
        if 'last_trade_price' in data:
            price = data['last_trade_price']
            return int(str(price).replace(',', ''))
        
        # روش سوم: endpoint دیگر
        if 'p' in data:
            return int(str(data['p']).replace(',', ''))
            
    except Exception as e:
        print(f"خطا در API: {e}")
    return None

def load_last_price():
    if os.path.exists(PRICE_FILE):
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
            return data.get("price"), data.get("date")
    return None, None

def save_price(price):
    with open(PRICE_FILE, "w") as f:
        json.dump({
            "price": price,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }, f)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    response = requests.post(url, data=data, timeout=10)
    result = response.json()
    print(f"تلگرام: {result}")
    return result

def main():
    print(f"⏰ بررسی قیمت طلا - {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ابتدا API مستقیم، سپس scraping
    current_price = get_gold_price_api()
    if not current_price:
        current_price = get_gold_price()
    
    if not current_price:
        print("❌ خطا در دریافت قیمت طلا")
        send_telegram("⚠️ خطا در دریافت قیمت طلا از tgju.org")
        return

    print(f"💰 قیمت فعلی طلای ۱۸ عیار: {current_price:,} ریال")

    last_price, last_date = load_last_price()

    if last_price is None:
        save_price(current_price)
        send_telegram(
            f"🤖 <b>مانیتور طلا فعال شد!</b>\n\n"
            f"💰 قیمت طلای ۱۸ عیار: <b>{current_price:,} ریال</b>\n"
            f"📊 هشدار نوسان بیش از {THRESHOLD}% فعاله\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        print("✅ قیمت اول ذخیره شد")
        return

    change_percent = ((current_price - last_price) / last_price) * 100
    print(f"📊 قیمت قبلی: {last_price:,} ریال | تغییر: {change_percent:.2f}%")

    if abs(change_percent) >= THRESHOLD:
        if change_percent > 0:
            emoji = "📈🔴"
            direction = "رشد"
        else:
            emoji = "📉🟢"
            direction = "ریزش"

        message = (
            f"{emoji} <b>هشدار نوسان طلا!</b>\n\n"
            f"💰 قیمت فعلی: <b>{current_price:,} ریال</b>\n"
            f"💰 قیمت قبلی: <b>{last_price:,} ریال</b>\n"
            f"📊 میزان {direction}: <b>{abs(change_percent):.2f}%</b>\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        send_telegram(message)
        print(f"✅ هشدار ارسال شد!")
    else:
        print(f"✅ نوسان نرمال ({change_percent:.2f}%)")

    save_price(current_price)

if __name__ == "__main__":
    main()
