import requests
import os
import time
import json
import xml.etree.ElementTree as ET
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

HISTORY_FILE = "/tmp/price_history.json"

RSS_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.investing.com/rss/news_25.rss",
]
KEYWORDS = [
    "federal reserve", "fed", "interest rate", "rate hike", "rate cut",
    "oil", "crude", "opec", "gold", "inflation", "cpi",
    "recession", "gdp", "dollar", "bitcoin", "crypto"
]

# ===================== قیمت‌ها =====================

def get_gold_price():
    try:
        headers = {"x-access-token": GOLDAPI_KEY}
        r = requests.get("https://www.goldapi.io/api/XAU/IRR", headers=headers, timeout=15)
        data = r.json()
        price_18k = float(data.get('price_gram_24k', 0)) * 0.75
        if 50_000_000 < price_18k < 600_000_000:
            return int(price_18k)
    except Exception as e:
        print(f"خطا طلا: {e}")
    return None

def get_usd_to_rial():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        data = r.json()
        rate = data['rates'].get('IRR', 0)
        if rate > 100000:
            return rate
    except Exception as e:
        print(f"خطا نرخ دلار: {e}")
    return 1_100_000

def get_crypto_prices_usd():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,tether", "vs_currencies": "usd"},
            timeout=15
        )
        data = r.json()
        btc = data.get('bitcoin', {}).get('usd')
        usdt = data.get('tether', {}).get('usd')
        return btc, usdt
    except Exception as e:
        print(f"خطا CoinGecko: {e}")
    return None, None

# ===================== تاریخچه برای محاسبه روند =====================

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def update_and_get_trend(key, current_price):
    """
    قیمت فعلی را ذخیره می‌کند و روند را نسبت به ~24 ساعت قبل برمی‌گرداند.
    خروجی: (درصد تغییر یا None, برچسب روند)
    """
    history = load_history()
    now = time.time()
    entries = history.get(key, [])

    # قیمت قدیمی‌ترین رکورد که حداقل ۲۰ ساعت قبل ثبت شده
    old_price = None
    for ts, price in entries:
        if now - ts >= 20 * 3600:
            old_price = price
        else:
            break

    # رکورد جدید را اضافه کن
    entries.append([now, current_price])
    # فقط رکوردهای ۳۰ ساعت اخیر را نگه دار
    entries = [e for e in entries if now - e[0] <= 30 * 3600]
    history[key] = entries
    save_history(history)

    if old_price is None:
        return None, "داده کافی برای روند ۲۴ ساعته هنوز ثبت نشده"

    change = ((current_price - old_price) / old_price) * 100
    if change > 1:
        label = f"📈 روند صعودی (نسبت به دیروز {change:+.2f}%)"
    elif change < -1:
        label = f"📉 روند نزولی (نسبت به دیروز {change:+.2f}%)"
    else:
        label = f"➡️ روند نسبتاً خنثی ({change:+.2f}%)"
    return change, label

# ===================== اخبار =====================

def get_relevant_news(limit=2):
    titles = []
    for feed_url in RSS_FEEDS:
        try:
            r = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            root = ET.fromstring(r.content)
            for item in root.findall('.//item')[:15]:
                title = item.findtext('title', '')
                if any(kw in title.lower() for kw in KEYWORDS):
                    titles.append(title)
        except Exception as e:
            print(f"خطا RSS: {e}")
    return titles[:limit]

def translate_title(title):
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|fa"},
            timeout=10
        )
        data = r.json()
        translated = data.get('responseData', {}).get('translatedText', '')
        if translated and translated.lower() != title.lower():
            return translated
    except Exception as e:
        print(f"خطا ترجمه: {e}")
    return title

# ===================== ساخت پیام تحلیل =====================

def build_price_message():
    gold = get_gold_price()
    usd_rial = get_usd_to_rial()
    btc_usd, usdt_usd = get_crypto_prices_usd()

    lines = ["💰 <b>قیمت لحظه‌ای و تحلیل روند</b>\n"]

    if gold:
        _, trend = update_and_get_trend("gold", gold)
        lines.append(f"🟡 <b>طلای ۱۸ عیار:</b> {gold:,} ریال")
        lines.append(f"   {trend}")
    else:
        lines.append("🟡 طلا: دریافت نشد")

    if btc_usd:
        _, trend = update_and_get_trend("bitcoin", btc_usd)
        lines.append(f"\n₿ <b>بیت‌کوین:</b> {btc_usd:,.0f} دلار")
        lines.append(f"   {trend}")
    else:
        lines.append("\n₿ بیت‌کوین: دریافت نشد")

    if usdt_usd:
        tether_rial = int(usdt_usd * usd_rial)
        _, trend = update_and_get_trend("tether", tether_rial)
        lines.append(f"\n💵 <b>تتر:</b> {tether_rial:,} ریال")
        lines.append(f"   {trend}")
    else:
        lines.append("\n💵 تتر: دریافت نشد")

    # اخبار مرتبط
    news = get_relevant_news(limit=2)
    if news:
        lines.append("\n\n📰 <b>اخبار مرتبط با بازار:</b>")
        for n in news:
            lines.append(f"• {translate_title(n)}")

    lines.append(
        "\n\n⚠️ <i>این تحلیل صرفاً نشان‌دهنده روند ۲۴ ساعت گذشته است و "
        "پیش‌بینی قیمت آینده نیست. تصمیم خرید/فروش بر عهده شماست.</i>"
    )
    lines.append(f"\n🕐 {time.strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)

# ===================== تلگرام =====================

def send_telegram(chat_id, message):
    url = f"{TELEGRAM_API}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    print(f"Update: {update}")

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/price":
            msg = build_price_message()
            send_telegram(chat_id, msg)
        elif text == "/start":
            send_telegram(chat_id, "🤖 سلام! برای دریافت قیمت و تحلیل روند بازار، دستور /price رو بفرست.")

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
