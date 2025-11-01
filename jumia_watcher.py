import time
import re
import requests
import logging
import difflib
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv 
from urllib.parse import quote_plus

# --------- load config ----------
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; TgodWatcher/2.0; +https://github.com/tgodmuna)")
HEADERS = {"User-Agent": USER_AGENT}
BASE_SEARCH = "https://www.jumia.com.ng/catalog/?q={query}"
logging.basicConfig(filename="watcher.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# === TREASURES (exact items + treasure prices taken from your screenshot) ===
TREASURE_MAP = {
    "Hisense Inverter Air Conditioner": 4379,
    "Nexus 4 Burner Gas Cooker": 1487,
    "Hisense 20 Litre Microwave": 770,
    "Syinix Swallow Maker": 1120,
    'TCL 55" UHD 4K Smart TV': 4600,
    "Aeon 90 Litres Chest Freezer": 1799,
}
# ===================================================================


def send_telegram_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=12)
        r.raise_for_status()
        logging.info("Sent text to Telegram: %s", text.splitlines()[0])
    except Exception as e:
        logging.exception("Failed to send Telegram text: %s", e)

def send_telegram_photo(photo_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=12)
        r.raise_for_status()
        logging.info("Sent photo to Telegram: %s", caption.splitlines()[0])
    except Exception as e:
        logging.exception("Failed to send Telegram photo: %s", e)

def extract_price(text):
    if not text:
        return None
    m = re.search(r"₦\s*([\d,]+)", text)
    if not m:
        m = re.search(r"NGN\s*([\d,]+)", text, re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except:
        return None

def parse_search_results(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article.prd, article.c-prd, article.prd._fb, .sku")
    results = []
    for card in cards:
        title_el = card.select_one("h3.name") or card.select_one(".name")
        price_el = card.select_one(".prc") or card.select_one(".price")
        link_el = card.select_one("a.core") or card.select_one("a")
        img_el = card.select_one("img")
        if not (title_el and price_el and link_el):
            continue
        title = title_el.get_text(strip=True)
        price = extract_price(price_el.get_text(strip=True))
        href = link_el.get("href")
        if href and href.startswith("/"):
            url = os.getenv('TARGET_URL') + href
        else:
            url = href or None
        img = None
        if img_el:
            img = img_el.get("data-src") or img_el.get("data-srcset") or img_el.get("src")
        if title and price:
            results.append({"title": title, "price": price, "url": url, "img": img})
    return results

def dynamic_tolerance(price):
    
    if price < 5000:
        return max(200, int(price * 0.10))     # for treasures below ₦5k
    elif price < 20000:
        return int(price * 0.15)               # for ₦5k–₦20k items
    elif price < 100000:
        return int(price * 0.20)               # for ₦20k–₦100k
    else:
        return int(price * 0.25)               # for anything expensive


def name_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

def likely_match(title, target_name, sim_threshold=0.55):
    sim = name_similarity(title, target_name)
    if sim < sim_threshold:
        return False
    def toks(s):
        return [t for t in re.split(r"[\s\-/,:\"']+", s.lower()) if len(t) > 2]
    tset = set(toks(target_name))
    title_set = set(toks(title))
    if not tset:
        return False
    common = tset.intersection(title_set)
    # require at least 50% of target meaningful tokens present
    return (len(common) / len(tset)) >= 0.5


def run_once_round(seen):
    for target_name, target_price in TREASURE_MAP.items():
        q = quote_plus(target_name)
        url = BASE_SEARCH.format(query=q)
        print(f"🔎 Searching for: {target_name} — target ₦{target_price:,}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
        except Exception as e:
            print(f"⚠️ Network/search error for '{target_name}': {e}")
            logging.exception("search error for %s: %s", target_name, e)
            time.sleep(1)
            continue

        items = parse_search_results(r.text)
        tol = dynamic_tolerance(target_price)
        print(f"  found {len(items)} items; price tolerance ±₦{tol:,}")

        for it in items:
            title = it["title"]
            price = it["price"]
            link = it["url"]
            img = it["img"]

            if price is None:
                continue

            name_ok = likely_match(title, target_name)
            price_ok = abs(price - target_price) <= tol

            if name_ok and price_ok:
                uid = f"{target_name}|{title}|{price}"
                if uid in seen:
                    continue
                seen.add(uid)

                caption = (
                    f"*TREASURE MATCH*\n\n"
                    f"*Target:* {target_name} — ₦{target_price:,}\n"
                    f"*Found:* {title}\n"
                    f"*Price:* ₦{price:,}\n"
                    f"*Link:* {link if link else 'N/A'}"
                )
                print("  ✅ Match →", title, f"₦{price:,}")
                if img:
                    send_telegram_photo(img, caption)
                else:
                    send_telegram_text(caption)
                logging.info("Alerted: %s -> %s (₦%s)", target_name, title, price)

            else:
                # Detailed diagnostic reason
                reasons = []
                if not name_ok:
                    reasons.append(("name not close enough", title))
                if not price_ok:
                    reasons.append(("price too far", price))
                reason_text = ", ".join(f"{desc}: {value}" for desc, value in reasons) if reasons else "unknown reason"
                print(f"  ❌ Skipped → {title[:60]} ({reason_text})")
                logging.info("Skipped: %s (%s)", title, reason_text)

        # short polite delay between target searches
        time.sleep(2)


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env")

    print("🚀 Jumia treasure watcher (improved) starting. Press Ctrl+C to stop.")
    print("Note: If Telegram API is blocked on your network, run with VPN ON.")
    seen = set()

    try:
        while True:
            run_once_round(seen)
            print(f"⏳ Round complete. Sleeping {POLL_INTERVAL_SECONDS}s before next round...\n")
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Stopped by user.")
    except Exception as e:
        logging.exception("Unexpected error in main loop: %s", e)
        print("Unexpected error:", e)


if __name__ == "__main__":
    main()
