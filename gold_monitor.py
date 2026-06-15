import requests
import re
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
PRICE_FILE = "last_price.json"
THRESHOLD = 2.0

def get_gold_price():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en;q=0.9",
        "Referer": "https://www.tgju.org/"
    }

    # روش اول: scraping صفحه tgju
    try:
        url = "https://www.tgju.org/profile/geram18"
        r = requests.get(url, headers=headers, timeout=15)
        text = r.text

        # الگوی اصلی
        match = re.search(
            r'در حال حاضر قیمت هر طلای 18 عیار[^\d]+([\d,٬]+)\s*ریال',
            text
        )
        if match:
            price_str = match.group(1).replace(',', '').replace('٬', '')
            price = int(price_str)
            if 50_000_000 < price < 600_000_000:
                print(f"✅ قیمت پیدا شد: {price:,} ریال")
                return price

        # الگوی دوم: همه اعداد بین 50 تا 600 میلیون
        all_numbers = re.findall(r'(1[0-9]{8})', text)
        print(f"اعداد پیدا شده: {all_numbers[:5]}")
        for num in all_numbers:
            price = int(num)
            if 50_000_000 < price < 600_000_000:
                print(f"✅ قیمت (روش دوم): {price:,} ریال")
                return price

    except Exception as e:
        print(f"خطا روش اول: {e}")

    # روش دوم: navasan API
    try:
        r = requests.get(
            "https://api.navasan.tech/latest/?api_key=free&item=gold18",
            timeout=15
        )
        print(f"Navasan: {r.text[:200]}")
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            price = int(str(data[0].get('value', 0)).replace(',', ''))
            if 50_000_000 < price < 600_000_000:
                return price
    except Exception as e:
        print(f"خطا Navasan: {e}")

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
        send_telegram("⚠️ خطا در دریافت قیمت طلا از tgju.org")
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
