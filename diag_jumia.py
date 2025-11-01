# diag_jumia.py
import os, time, sys, re, requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

# config from .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; TgodDiag/1.0)")
HEADERS = {"User-Agent": USER_AGENT}
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
BASE_SEARCH = "https://www.jumia.com.ng/catalog/?q={query}"

TREASURE_MAP = {
    "Hisense Inverter Air Conditioner": 4379,
    "Nexus 4 Burner Gas Cooker": 1487,
    "Hisense 20 Litre Microwave": 770,
    "Syinix Swallow Maker": 1120,
    'TCL 55" UHD 4K Smart TV': 4600,
    "Aeon 90 Litres Chest Freezer": 1799,
}

def ok_env():
    missing = []
    if not TELEGRAM_BOT_TOKEN: missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID: missing.append("TELEGRAM_CHAT_ID")
    if missing:
        print("❌ Missing env vars:", ", ".join(missing))
        return False
    print("✅ Env vars present.")
    return True

def extract_price(text):
    if not text: return None
    m = re.search(r"₦\s*([\d,]+)", text)
    if not m:
        m = re.search(r"NGN\s*([\d,]+)", text, re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))

def parse_search_results(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article.prd, article.c-prd, article.prd._fb")
    results = []
    for card in cards[:10]:
        title_el = card.select_one("h3.name") or card.select_one(".name")
        price_el = card.select_one(".prc") or card.select_one(".price")
        link_el = card.select_one("a.core") or card.select_one("a")
        img_el = card.select_one("img")
        if not (title_el and price_el and link_el): continue
        title = title_el.get_text(strip=True)
        price = extract_price(price_el.get_text(strip=True))
        href = link_el.get("href")
        url = ("https://www.jumia.com.ng" + href) if href and href.startswith("/") else href
        img = img_el.get("data-src") or img_el.get("src") if img_el else None
        results.append({"title": title, "price": price, "url": url, "img": img})
    return results

def try_search(term):
    q = quote_plus(term)
    url = BASE_SEARCH.format(query=q)
    print(f"\n🔎 Searching: {term}")
    print("URL:", url)
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
    except Exception as e:
        print("❌ Network/search error:", e)
        return None
    items = parse_search_results(r.text)
    print(f"Found {len(items)} items (showing up to 3):")
    for i, it in enumerate(items[:3], 1):
        print(f" {i}) {it['title'][:80]} — ₦{it['price'] if it['price'] else 'N/A'}")
        print("    link:", it['url'])
        print("    img:", it['img'])
    return items

def test_telegram():
    print("\n📨 Testing Telegram send...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": "Diag: Telegram test from your watcher"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        print("✅ Telegram send succeeded.")
    except Exception as e:
        print("❌ Telegram send failed:", e)

def main():
    if not ok_env():
        print("Fix .env then re-run.")
        sys.exit(1)
    print("Note: If your ISP blocks Telegram API, run this with VPN ON.")
    for term in TREASURE_MAP.keys():
        items = try_search(term)
        time.sleep(1)
    # attempt telegram last to avoid spamming while debugging network issues
    test_telegram()
    print("\n✅ Diagnostic complete.")

if __name__ == "__main__":
    main()
