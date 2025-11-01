import time, os, re, requests, logging, difflib
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; TgodHunter/3.0)")
HEADERS = {"User-Agent": USER_AGENT}
BASE_SEARCH = "https://www.jumia.com.ng/catalog/?q={query}"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

# Your actual treasure list (names + your target prices in ₦)
TREASURE_MAP = {
"Hisense Inverter Air Conditioner": 4379,
    "Nexus 4 Burner Gas Cooker": 1487,
    "Hisense 20 Litre Microwave": 770,
    "Syinix Swallow Maker": 1120,
    'TCL 55" UHD 4K Smart TV': 4600,
    "Aeon 90 Litres Chest Freezer": 1799,
}

logging.basicConfig(filename="hunter.log", level=logging.INFO)

def extract_price(text):
    if not text: return None
    m = re.search(r"₦\s*([\d,]+)", text)
    if not m: return None
    return int(m.group(1).replace(",", ""))

def parse_search_results(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article.prd, article.c-prd, article.prd._fb")
    results = []
    for card in cards:
        title_el = card.select_one("h3.name") or card.select_one(".name")
        price_el = card.select_one(".prc") or card.select_one(".price")
        link_el = card.select_one("a.core") or card.select_one("a")
        img_el = card.select_one("img")
        if not (title_el and price_el and link_el): continue
        title = title_el.get_text(strip=True)
        price = extract_price(price_el.get_text(strip=True))
        href = link_el.get("href")
        url = (os.getenv("TARGET_URL") + href) if href and href.startswith("/") else href
        img = img_el.get("data-src") or img_el.get("src") if img_el else None
        results.append({"title": title, "price": price, "url": url, "img": img})
    return results

def dynamic_tolerance(p):
    """Automatically adjusts allowed price difference."""
    if p < 50000: return max(5000, int(p * 0.15))
    elif p < 200000: return int(p * 0.20)
    else: return int(p * 0.25)

def is_name_similar(a, b, threshold=0.6):
    """Returns True if titles are roughly the same (using fuzzy ratio)."""
    ratio = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return ratio >= threshold

def send_telegram_photo(photo_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url, "caption": caption}
    try:
        requests.post(url, data=payload, timeout=12)
    except Exception as e:
        print("⚠️ Telegram photo error:", e)

def send_telegram_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, data=payload, timeout=12)
    except Exception as e:
        print("⚠️ Telegram text error:", e)

def main():
    print("🔥 Treasure Hunter is now LIVE! Press Ctrl+C to stop.\n")
    seen = set()

    while True:
        for target_name, target_price in TREASURE_MAP.items():
            query = quote_plus(target_name)
            url = BASE_SEARCH.format(query=query)
            print(f"🔎 Searching for {target_name} (target ₦{target_price})")
            try:
                res = requests.get(url, headers=HEADERS, timeout=12)
                res.raise_for_status()
            except Exception as e:
                print(f"❌ Error fetching {target_name}: {e}")
                continue

            items = parse_search_results(res.text)
            tol = dynamic_tolerance(target_price)
            print(f"Found {len(items)} items (price tolerance ±₦{tol})")

            for it in items:
                if not it["price"]:
                    continue
                # Check name similarity and price closeness
                if is_name_similar(target_name, it["title"]) and abs(it["price"] - target_price) <= tol:
                    uid = f"{target_name}|{it['title']}|{it['price']}"
                    if uid in seen: continue
                    seen.add(uid)
                    cap = f"🎯 Match Found: {it['title']}\nPrice: ₦{it['price']}\n{it['url']}"
                    if it["img"]:
                        send_telegram_photo(it["img"], cap)
                    else:
                        send_telegram_text(cap)
                    print("✅ Sent alert to Telegram!")
            print("Sleeping before next treasure...\n")
            time.sleep(5)
        print("⏳ Round complete. Waiting before next full scan...\n")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
