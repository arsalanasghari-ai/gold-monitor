import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
PRICE_FILE = "last_price.json"
THRESHOLD = 2.0

def get_gold_price():
    """
    قیمت طلای ۱۸ عیار را محاسبه میکنه:
    قیمت اونس جهانی (دلار) × نرخ دلار (ریال) × 0.5833 / 31.1035
    """
    try:
        # قیمت اونس طلا از frankfurter (رایگان و بدون نیاز به key)
        r1 = requests.get(
            "https://api.frankfurter.app/latest?from=XAU&to=USD",
            timeout=15
        )
        data1 = r1.json()
        print(f"Frankfurter: {data1}")
        # این قیمت XAU/USD هست، باید برعکس کنیم
        usd_per_xau = 1 / data1['rates']['USD']  # اشتباه، درستش اینه:
        xau_price_usd = 1 / data1['rates']['USD']
    except Exception as e:
        print(f"خطا frankfurter: {e}")
        # قیمت ثابت پشتیبان (تقریبی)
        xau_price_usd = 3300

    try:
        # نرخ دلار به ریال از exchangerate-api (رایگان)
        r2 = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=15
        )
        data2 = r2.json()
        usd_to_rial = data2['rates'].get('IRR', 0)
        print(f"USD/IRR: {usd_to_rial}")

        if not usd_to_rial or usd_to_rial < 100000:
            # نرخ دلار آزاد ایران (تقریبی اگه API نداد)
            usd_to_rial = 1700000  # تقریبی
            print(f"استفاده از نرخ پیش‌فرض: {usd_to_rial}")

    except Exception as e:
        print(f"خطا exchange rate: {e}")
        usd_to_rial = 1700000

    try:
        # قیمت اونس از metalpriceapi (رایگان)
        r3 = requests.get(
            "https://api.metalpriceapi.com/v1/latest?api_key=free&base=USD&currencies=XAU",
            timeout=15
        )
        data3 = r3.json()
        print(f"MetalPrice: {data3}")
        if 'rates' in data3 and 'USDXAU' in data3['rates']:
            xau_price_usd = 1 / data3['rates']['USDXAU']
    except Exception as e:
        print(f"خطا metalpriceapi: {e}")

    # محاسبه قیمت طلای ۱۸ عیار به ریال
    # هر اونس = 31.1035 گرم
    # طلای ۱۸ عیار = 75% طلا (18/24 = 0.75)
    # قیمت هر گرم طلای ۱۸ عیار = (قیمت اونس × نرخ دلار × 0.75) / 31.1035
    price_per_gram_18k = (xau_price_usd * usd_to_rial * 0.75) / 31.1035

    print(f"اونس: ${xau_price_usd:.2f} | دلار: {usd_to_rial:,} ریال")
    print(f"قیمت محاسبه‌شده هر گرم ۱۸ عیار: {price_per_gram_18k:,.0f} ریال")

    if 50_000_000 < price_per_gram_18k < 600_000_000:
        return int(price_per_gram_18k)

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
