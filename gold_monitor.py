import requests
import json
import os
import csv
import time
import xml.etree.ElementTree as ET
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID        = os.environ.get("CHAT_ID", "")
GOLDAPI_KEY    = os.environ.get("GOLDAPI_KEY", "")          # اگر کلید جدید گرفتی
METAL_PRICE_API_KEY  = os.environ.get("METAL_PRICE_API_KEY", "")   # اختیاری
COMMODITIES_API_KEY  = os.environ.get("COMMODITIES_API_KEY", "")   # اختیاری

PRICE_FILE   = "last_prices.json"
NEWS_FILE    = "last_news.json"
HISTORY_FILE = "daily_history.json"
TREND_FILE   = "price_history.json"
ARCHIVE_FILE = "price_archive.csv"
THRESHOLD    = 2.0

TROY_OUNCE_TO_GRAM = 31.1035
KARAT_18_FACTOR    = 0.75

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

# ===================== دریافت نرخ دلار =====================

def get_usd_to_rial():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        data = r.json()
        rate = data['rates'].get('IRR', 0)
        if rate > 100000:
            print(f"[USD/IRR] {rate:,.0f} ریال")
            return float(rate)
    except Exception as e:
        print(f"خطا نرخ دلار (er-api): {e}")

    # Fallback
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=15)
        data = r.json()
        rate = data['rates'].get('IRR', 0)
        if rate > 100000:
            print(f"[USD/IRR fallback] {rate:,.0f} ریال")
            return float(rate)
    except Exception as e:
        print(f"خطا نرخ دلار (fallback): {e}")

    return 1_100_000   # مقدار پیش‌فرض اضطراری

# ===================== دریافت اونس طلا — چند منبع =====================

def _get_xau_from_metals_live():
    """منبع ۱: metals.live — بدون کلید"""
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=10)
        if r.status_code == 200:
            data = r.json()
            price = (data[0].get("price") or data[0].get("gold")) if isinstance(data, list) \
                    else (data.get("price") or data.get("gold"))
            if price and 500 < float(price) < 20000:
                print(f"[metals.live] اونس: ${float(price):,.2f}")
                return float(price)
    except Exception as e:
        print(f"[metals.live] خطا: {e}")
    return None

def _get_xau_from_metalpriceapi():
    """منبع ۲: metalpriceapi.com — کلید رایگان اختیاری"""
    if not METAL_PRICE_API_KEY:
        return None
    try:
        r = requests.get(
            f"https://api.metalpriceapi.com/v1/latest"
            f"?api_key={METAL_PRICE_API_KEY}&base=XAU&currencies=USD",
            timeout=10
        )
        if r.status_code == 200:
            price = float(r.json()["rates"]["USD"])
            if 500 < price < 20000:
                print(f"[metalpriceapi] اونس: ${price:,.2f}")
                return price
    except Exception as e:
        print(f"[metalpriceapi] خطا: {e}")
    return None

def _get_xau_from_commodities():
    """منبع ۳: commodities-api.com — کلید رایگان اختیاری"""
    if not COMMODITIES_API_KEY:
        return None
    try:
        r = requests.get(
            f"https://commodities-api.com/api/latest"
            f"?access_key={COMMODITIES_API_KEY}&base=USD&symbols=XAU",
            timeout=10
        )
        if r.status_code == 200:
            xau_per_usd = r.json()["data"]["rates"].get("XAU")
            if xau_per_usd:
                price = 1.0 / float(xau_per_usd)
                if 500 < price < 20000:
                    print(f"[commodities-api] اونس: ${price:,.2f}")
                    return price
    except Exception as e:
        print(f"[commodities-api] خطا: {e}")
    return None

def _get_xau_from_goldapi():
    """منبع ۴: goldapi.io — اگر کلید جدید داری"""
    if not GOLDAPI_KEY:
        return None
    try:
        headers = {"x-access-token": GOLDAPI_KEY, "Content-Type": "application/json"}
        r = requests.get("https://www.goldapi.io/api/XAU/USD", headers=headers, timeout=15)
        if r.status_code == 200:
            price = float(r.json().get("price", 0))
            if 500 < price < 20000:
                print(f"[goldapi.io] اونس: ${price:,.2f}")
                return price
        else:
            print(f"[goldapi.io] خطای {r.status_code}")
    except Exception as e:
        print(f"[goldapi.io] خطا: {e}")
    return None

def _get_xau_from_coingecko():
    """منبع ۵: CoinGecko PAXG — بدون کلید، آخرین راه"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=pax-gold&vs_currencies=usd",
            timeout=10
        )
        if r.status_code == 200:
            price = r.json().get("pax-gold", {}).get("usd")
            if price and 500 < float(price) < 20000:
                print(f"[CoinGecko/PAXG] اونس (تقریبی): ${float(price):,.2f}")
                return float(price)
    except Exception as e:
        print(f"[CoinGecko/PAXG] خطا: {e}")
    return None

def get_gold_price_and_ounce():
    """
    قیمت اونس XAU/USD را از چند منبع رایگان دریافت می‌کند،
    سپس طلای ۱۸ عیار به ریال را محاسبه می‌کند.
    خروجی: (gold_18k_rial, ounce_usd)
    """
    xau_usd = (
        _get_xau_from_metals_live()      or
        _get_xau_from_metalpriceapi()    or
        _get_xau_from_commodities()      or
        _get_xau_from_goldapi()          or
        _get_xau_from_coingecko()
    )

    if not xau_usd:
        print("❌ هیچ منبعی برای اونس طلا کار نکرد")
        return None, None

    usd_rial = get_usd_to_rial()
    gold_18k = int((xau_usd / TROY_OUNCE_TO_GRAM) * KARAT_18_FACTOR * usd_rial)

    # اعتبارسنجی بازه منطقی
    if not (50_000_000 < gold_18k < 600_000_000):
        print(f"⚠️ قیمت محاسبه‌شده خارج از بازه: {gold_18k:,} ریال")
        gold_18k = None

    if gold_18k:
        print(f"✅ طلای ۱۸ عیار: {gold_18k:,} ریال  |  اونس: ${xau_usd:,.2f}")

    return gold_18k, round(xau_usd, 2)

# ===================== کریپتو =====================

def get_crypto_prices_usd():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,tether", "vs_currencies": "usd"},
            timeout=15
        )
        data = r.json()
        print(f"CoinGecko: {data}")
        btc  = data.get('bitcoin', {}).get('usd')
        usdt = data.get('tether',  {}).get('usd')
        return btc, usdt
    except Exception as e:
        print(f"خطا CoinGecko: {e}")
    return None, None

def get_all_prices():
    prices = {}
    gold_18k, ounce_usd = get_gold_price_and_ounce()
    if gold_18k:
        prices['gold_18k']   = gold_18k
    if ounce_usd:
        prices['gold_ounce'] = round(ounce_usd, 2)

    usd_rial = get_usd_to_rial()
    btc_usd, usdt_usd = get_crypto_prices_usd()

    if btc_usd:
        prices['bitcoin'] = round(btc_usd, 2)
    if usdt_usd:
        prices['tether']  = int(usdt_usd * usd_rial)

    return prices

# ===================== ذخیره/بارگذاری =====================

def load_last_prices():
    if os.path.exists(PRICE_FILE):
        with open(PRICE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_prices(prices):
    data = {**prices, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with open(PRICE_FILE, "w") as f:
        json.dump(data, f)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def load_last_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_summary", "")
    return ""

def save_news(summary):
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_summary": summary,
                   "date": datetime.now().strftime("%Y-%m-%d %H:%M")},
                  f, ensure_ascii=False)

def update_trend_file(current_prices):
    now = time.time()
    trend_data = {}
    if os.path.exists(TREND_FILE):
        try:
            with open(TREND_FILE, "r") as f:
                trend_data = json.load(f)
        except Exception:
            trend_data = {}
    for key, price in current_prices.items():
        entries = trend_data.get(key, [])
        entries.append([now, price])
        entries = [e for e in entries if now - e[0] <= 30 * 3600]
        trend_data[key] = entries
    with open(TREND_FILE, "w") as f:
        json.dump(trend_data, f)

def update_csv_archive(prices):
    now = datetime.now()
    fieldnames = ["date","time","gold_18k_rial","gold_ounce_usd","bitcoin_usd","tether_rial"]
    row = {
        "date":           now.strftime("%Y-%m-%d"),
        "time":           now.strftime("%H:%M"),
        "gold_18k_rial":  prices.get("gold_18k", ""),
        "gold_ounce_usd": prices.get("gold_ounce", ""),
        "bitcoin_usd":    prices.get("bitcoin", ""),
        "tether_rial":    prices.get("tether", ""),
    }
    file_exists = os.path.exists(ARCHIVE_FILE)
    with open(ARCHIVE_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    print(f"✅ آرشیو CSV: {row}")

# ===================== اخبار =====================

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
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|fa"},
            timeout=15
        )
        data = r.json()
        translated = data.get('responseData', {}).get('translatedText', '')
        if translated and translated.lower() != title.lower():
            return translated
    except Exception as e:
        print(f"خطا MyMemory: {e}")
    try:
        r = requests.post(
            "https://libretranslate.com/translate",
            json={"q": title, "source": "en", "target": "fa", "format": "text"},
            timeout=15
        )
        data = r.json()
        if 'translatedText' in data:
            return data['translatedText']
    except Exception as e:
        print(f"خطا LibreTranslate: {e}")
    return f"📌 {title}"

# ===================== تلگرام =====================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    r = requests.post(url, data=data, timeout=10)
    print(f"تلگرام: {r.json().get('ok')}")

def fa_name(key):
    return {
        "gold_18k":   "طلای ۱۸ عیار",
        "gold_ounce": "اونس طلای جهانی",
        "bitcoin":    "بیت‌کوین",
        "tether":     "تتر",
    }.get(key, key)

def fa_unit(key):
    if key in ("bitcoin", "gold_ounce"):
        return "دلار"
    return "ریال"

# ===================== بررسی قیمت و هشدار =====================

def check_prices_and_alert():
    current = get_all_prices()
    if not current:
        print("❌ هیچ قیمتی دریافت نشد")
        return

    last = load_last_prices()

    if not last:
        save_prices(current)
        lines = [f"💰 {fa_name(k)}: <b>{v:,} {fa_unit(k)}</b>" for k, v in current.items()]
        send_telegram(
            "🤖 <b>مانیتور بازار فعال شد!</b>\n\n" + "\n".join(lines) +
            f"\n\n📊 هشدار نوسان بیش از {THRESHOLD}%\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    else:
        for key, price in current.items():
            old_price = last.get(key)
            if not old_price:
                continue
            change = ((price - old_price) / old_price) * 100
            print(f"📊 {key}: {old_price:,} → {price:,} ({change:+.2f}%)")
            if abs(change) >= THRESHOLD:
                emoji     = "📈🔴" if change > 0 else "📉🟢"
                direction = "رشد" if change > 0 else "ریزش"
                send_telegram(
                    f"{emoji} <b>هشدار نوسان {fa_name(key)}!</b>\n\n"
                    f"💰 فعلی: <b>{price:,} {fa_unit(key)}</b>\n"
                    f"💰 قبلی: <b>{old_price:,} {fa_unit(key)}</b>\n"
                    f"📊 {direction}: <b>{abs(change):.2f}%</b>\n"
                    f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
        save_prices(current)

    today   = datetime.now().strftime("%Y-%m-%d")
    history = load_history()
    if today not in history:
        history = {today: {}}
    for key, price in current.items():
        if key not in history[today]:
            history[today][key] = []
        history[today][key].append(price)
    save_history(history)

    update_trend_file(current)
    update_csv_archive(current)

# ===================== اخبار =====================

def check_news():
    print("\n📰 بررسی اخبار RSS...")
    titles = get_news_from_rss()
    print(f"تعداد اخبار مهم: {len(titles)}")

    if not titles:
        print("✅ خبر مهمی نیست")
        return

    last_sent    = load_last_news()
    already_sent = last_sent.split("|||") if last_sent else []
    new_titles   = [t for t in titles if t not in already_sent][:3]

    if not new_titles:
        print("✅ خبرها تکراری بودن")
        return

    lines = ["📰 <b>اخبار مهم اقتصادی:</b>\n"]
    for t in new_titles:
        lines.append(f"• {translate_title(t)}")

    send_telegram("\n\n".join(lines))
    save_news("|||".join(titles[:10]))
    print(f"✅ {len(new_titles)} خبر ارسال شد")

# ===================== گزارش روزانه تلگرام =====================

def send_daily_report():
    today    = datetime.now().strftime("%Y-%m-%d")
    history  = load_history()
    day_data = history.get(today, {})

    if not day_data:
        print("⚠️ داده‌ای برای گزارش امروز موجود نیست")
        return

    results = {}
    for key, prices_list in day_data.items():
        if len(prices_list) >= 2:
            first  = prices_list[0]
            last   = prices_list[-1]
            change = ((last - first) / first) * 100
            results[key] = {"first": first, "last": last, "change": change}

    if not results:
        print("⚠️ داده کافی برای محاسبه تغییرات نیست")
        return

    best  = max(results.items(), key=lambda x: x[1]['change'])
    worst = min(results.items(), key=lambda x: x[1]['change'])

    lines = ["📊 <b>گزارش پایان روز بازار</b>\n"]
    for key, val in results.items():
        emoji = "📈" if val['change'] > 0 else "📉"
        lines.append(f"{emoji} {fa_name(key)}: {val['change']:+.2f}%  ({val['last']:,} {fa_unit(key)})")

    lines.append(f"\n🏆 بیشترین رشد: <b>{fa_name(best[0])}</b> ({best[1]['change']:+.2f}%)")
    lines.append(f"🔻 بیشترین ریزش: <b>{fa_name(worst[0])}</b> ({worst[1]['change']:+.2f}%)")
    lines.append(f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    send_telegram("\n".join(lines))
    print("✅ گزارش روزانه ارسال شد")

    history = {today: day_data}
    save_history(history)

# ===================== اجرای اصلی =====================

def main():
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    mode = os.environ.get("RUN_MODE", "hourly")

    if mode == "daily_report":
        send_daily_report()
    else:
        check_prices_and_alert()
        check_news()

if __name__ == "__main__":
    main()
