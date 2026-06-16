import requests
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")
PRICE_FILE = "last_price.json"
NEWS_FILE = "last_news.json"
THRESHOLD = 2.0

RSS_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.investing.com/rss/news_25.rss",
]

KEYWORDS = [
    "federal reserve", "fed", "interest rate", "rate hike", "rate cut",
    "oil", "crude", "opec", "brent", "wti",
    "gold", "inflation", "cpi", "pce",
    "recession", "gdp", "dollar", "treasury",
    "market", "stock", "economy", "economic",
    "bank", "debt", "bond", "yield"
]

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

def get_news_from_rss():
    important_titles = []
    for feed_url in RSS_FEEDS:
        try:
            r = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            print(f"✅ {feed_url.split('/')[2]}: {len(items)} خبر")
            for item in items[:20]:
                title = item.findtext('title', '').lower()
                if any(kw in title for kw in KEYWORDS):
                    original_title = item.findtext('title', '')
                    important_titles.append(original_title)
                    print(f"  📌 {original_title}")
        except Exception as e:
            print(f"خطا RSS {feed_url}: {e}")
    return important_titles
    
def translate_title(title):
    # روش اول: MyMemory (رایگان، بدون نیاز به key)
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|fa"},
            timeout=15
        )
        data = r.json()
        print(f"MyMemory: {data.get('responseStatus')}")
        translated = data.get('responseData', {}).get('translatedText', '')
        if translated and translated.lower() != title.lower():
            return translated
    except Exception as e:
        print(f"خطا MyMemory: {e}")

    # روش دوم: LibreTranslate (پشتیبان)
    try:
        r = requests.post(
            "https://libretranslate.com/translate",
            json={"q": title, "source": "en", "target": "fa", "format": "text"},
            timeout=15
        )
        data = r.json()
        print(f"LibreTranslate: {data}")
        if 'translatedText' in data:
            return data['translatedText']
    except Exception as e:
        print(f"خطا LibreTranslate: {e}")

    # اگه هیچی جواب نداد
    return f"📌 {title}"

def load_last_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_summary", "")
    return ""

def save_news(summary):
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_summary": summary, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}, f, ensure_ascii=False)

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
        last_price, _ = load_last_price()
        if last_price is None:
            save_price(current_price)
            send_telegram(
                f"🤖 <b>مانیتور فعال شد!</b>\n\n"
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
                    f"💰 فعلی: <b>{current_price:,} ریال</b>\n"
                    f"💰 قبلی: <b>{last_price:,} ریال</b>\n"
                    f"📊 {direction}: <b>{abs(change_percent):.2f}%</b>\n"
                    f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            save_price(current_price)

    # بخش ۲: اخبار اقتصادی
    print("\n📰 بررسی اخبار RSS...")
    titles = get_news_from_rss()
    print(f"تعداد اخبار مهم: {len(titles)}")

    if titles:
        summary = translate_title(titles[0])
        last_news = load_last_news()
        if summary and summary != last_news:
            send_telegram(f"📰 <b>خبر مهم اقتصادی:</b>\n\n{summary}")
            save_news(summary)
            print("✅ خبر ارسال شد")
        else:
            print("✅ خبر تکراریه")
    else:
        print("✅ خبر مهمی نیست")

if __name__ == "__main__":
    main()
