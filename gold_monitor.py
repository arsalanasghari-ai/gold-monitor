import requests
import json
import os
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "")
PRICE_FILE = "last_price.json"
NEWS_FILE = "last_news.json"
THRESHOLD = 2.0

# کلمات کلیدی اخبار مهم اقتصادی
KEYWORDS = [
    "federal reserve", "Fed rate", "interest rate",
    "oil price", "crude oil", "OPEC",
    "gold price", "XAU",
    "inflation", "CPI",
    "dollar", "USD",
    "recession", "GDP",
    "Iran sanctions"
]

def get_gold_price():
    try:
        headers = {"x-access-token": GOLDAPI_KEY}
        r = requests.get("https://www.goldapi.io/api/XAU/IRR", headers=headers, timeout=15)
        data = r.json()
        price_gram_24k = float(data.get('price_gram_24k', 0))
        price_18k = price_gram_24k * 0.75
        if 50_000_000 < price_18k < 600_000_000:
            return int(price_18k)
    except Exception as e:
        print(f"خطا قیمت طلا: {e}")
    return None

def get_important_news():
    try:
        # جستجوی اخبار اقتصادی مهم
        query = "federal reserve OR oil price OR gold price OR inflation OR OPEC OR recession"
        yesterday = (datetime.now() - timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%S')
        
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "from": yesterday,
                "pageSize": 10,
                "apiKey": NEWSAPI_KEY
            },
            timeout=15
        )
        data = r.json()
        print(f"NewsAPI status: {data.get('status')} | تعداد: {data.get('totalResults', 0)}")
        
        articles = data.get('articles', [])
        if not articles:
            return None
            
        # ساخت لیست عناوین
        titles = [f"- {a['title']}" for a in articles[:5]]
        return "\n".join(titles)
        
    except Exception as e:
        print(f"خطا اخبار: {e}")
    return None

def summarize_with_claude(news_text):
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages": [{
                    "role": "user",
                    "content": f"""از این اخبار اقتصادی، فقط مهم‌ترین خبر را در یک جمله کوتاه فارسی خلاصه کن.
فقط اگه خبر واقعاً مهمه (فدرال رزرو، نفت، طلا، تورم، رکود) خلاصه بده.
اگه خبر مهمی نیست، فقط بنویس: مهم نیست

اخبار:
{news_text}

خلاصه (یک جمله):"""
                }]
            },
            timeout=30
        )
        data = r.json()
        summary = data['content'][0]['text'].strip()
        print(f"خلاصه Claude: {summary}")
        return summary
    except Exception as e:
        print(f"خطا Claude: {e}")
    return None

def load_last_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_summary", "")
    return ""

def save_news(summary):
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_summary": summary, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}, f)

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

    # بخش ۱: قیمت طلا
    current_price = get_gold_price()
    if current_price:
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
        else:
            change_percent = ((current_price - last_price) / last_price) * 100
            print(f"📊 تغییر: {change_percent:.2f}%")
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
            save_price(current_price)

    # بخش ۲: اخبار اقتصادی
    print("\n📰 بررسی اخبار...")
    news = get_important_news()
    if news:
        summary = summarize_with_claude(news)
        if summary and summary != "مهم نیست" and summary != load_last_news():
            send_telegram(f"📰 <b>خبر مهم اقتصادی:</b>\n\n{summary}")
            save_news(summary)
            print("✅ خبر ارسال شد")
        else:
            print("✅ خبر مهمی نیست یا قبلاً ارسال شده")

if __name__ == "__main__":
    main()
