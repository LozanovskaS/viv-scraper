import requests
from bs4 import BeautifulSoup
import json
import time
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9",
}

BASE_URL = "https://webshop.viv.nl"
DOMAIN   = "webshop.viv.nl"

# URLs кои НЕ се категории со производи
SKIP_URLS = {
    f"{BASE_URL}/contact-webshop",
    f"{BASE_URL}/retourneren-service",
    f"{BASE_URL}/verzending",
    f"{BASE_URL}/bedrukte-verpakkingen",
}


# ─── ЧЕКОР 1: Земи ги сите категории од менито ────────────────────────────────
def get_category_urls():
    print("Fetching categories from menu...")
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "lxml")

    seen       = set()
    categories = []

    for a in soup.select("#store\\.menu a"):
        href = a.get("href", "")
        name = a.get_text(strip=True)

        if not href or not name:
            continue
        if href.startswith("/"):
            href = f"{BASE_URL}{href}"
        if "webshop.viv.nl" not in href:
            continue
        if href in SKIP_URLS:
            continue
        if any(x in href for x in ["customer", "wishlist", "blog", "media"]):
            continue
        if href in seen:
            continue

        seen.add(href)
        categories.append({"name": name, "url": href})

    print(f"Found {len(categories)} categories")
    return categories


# ─── ЧЕКОР 2: Земи product URLs од категорија (со пагинација) ─────────────────
def get_product_urls_from_category(category_url):
    product_urls = []
    page         = 1

    while True:
        url = f"{category_url}?product_list_limit=100&p={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(resp.text, "lxml")

            links = soup.select("a.product-card__image")
            if not links:
                break

            for a in links:
                href = a.get("href", "")
                if href and href not in product_urls:
                    product_urls.append(href)

            # Следна страница?
            if not soup.select_one("a.action.next"):
                break

            page += 1
            time.sleep(0.5)

        except Exception as e:
            print(f"    ❌ Error on page {page}: {e}")
            break

    return product_urls


# ─── ЧЕКОР 3: Scrape индивидуален производ ────────────────────────────────────
def scrape_product(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "lxml")

        # Ime
        name_el = soup.select_one("h1.page-title span")
        if not name_el:
            return None

        # SKU
        sku    = None
        sku_el = soup.select_one("[itemprop='sku']")
        if sku_el:
            sku = sku_el.get_text(strip=True)
        else:
            m = re.search(r"Artikelnr[:\s]+(\d+)", soup.get_text())
            if m:
                sku = m.group(1)
        if not sku:
            return None

        # JSON-LD
        ld_by_type = {}
        for ld_tag in soup.find_all("script", type="application/ld+json"):
            if not ld_tag.string:
                continue
            try:
                obj = json.loads(ld_tag.string)
                if isinstance(obj, list):
                    obj = obj[0] if obj else {}
                t = obj.get("@type", "")
                if t:
                    ld_by_type[t] = obj
            except Exception:
                pass

        product_ld = ld_by_type.get("Product", {})

        # Merk
        brand     = None
        brand_raw = product_ld.get("brand")
        if isinstance(brand_raw, str):
            brand = brand_raw
        elif isinstance(brand_raw, dict):
            brand = brand_raw.get("name")

        # Rating
        rating       = None
        review_count = 0
        agg = product_ld.get("aggregateRating", {})
        if isinstance(agg, dict):
            try:
                rating = float(agg.get("ratingValue", 0)) or None
            except (ValueError, TypeError):
                pass
            try:
                review_count = int(agg.get("reviewCount", 0))
            except (ValueError, TypeError):
                pass

        if rating is None:
            rating_el = soup.select_one("div.rating-result")
            if rating_el:
                try:
                    pct    = float(rating_el.get("title", "0%").replace("%", ""))
                    rating = round(pct / 20, 2)
                except (ValueError, TypeError):
                    pass

        if not review_count:
            reviews_el = soup.select_one("span.reviews-actions__review-count")
            if reviews_el:
                try:
                    review_count = int(reviews_el.get_text(strip=True))
                except (ValueError, TypeError):
                    pass

        # Prijs excl BTW
        price    = None
        price_el = soup.select_one("span.price-wrapper.price-excluding-tax")
        if price_el:
            try:
                price = float(price_el.get("data-price-amount", 0))
            except (ValueError, TypeError):
                pass

        # Prijs incl BTW
        price_incl_tax    = None
        price_incl_el     = soup.select_one("span.price-wrapper.price-including-tax")
        if price_incl_el:
            try:
                price_incl_tax = float(price_incl_el.get("data-price-amount", 0))
            except (ValueError, TypeError):
                pass
        if price_incl_tax is None:
            offers = product_ld.get("offers", {})
            if isinstance(offers, dict):
                try:
                    price_incl_tax = round(float(offers.get("price", 0)), 2) or None
                except (ValueError, TypeError):
                    pass
        elif price_incl_tax is not None:
            price_incl_tax = round(price_incl_tax, 2)

        # Min qty
        min_qty = None
        qty_el  = soup.select_one("input[name='qty']")
        if qty_el:
            try:
                min_qty = int(qty_el.get("value", 1))
            except (ValueError, TypeError):
                pass

        # Залиха
        in_stock    = False
        stock_label = None
        stock_el    = soup.select_one("div.stock span")
        if stock_el:
            stock_label = stock_el.get_text(strip=True)
            in_stock    = "voorraad" in stock_label.lower()

        # Afbeelding
        image_url  = None
        ld_images  = product_ld.get("image")
        if isinstance(ld_images, list) and ld_images:
            image_url = ld_images[0]
        elif isinstance(ld_images, str) and ld_images:
            image_url = ld_images
        else:
            img_el = soup.select_one("img.gallery-placeholder__image, .fotorama__img")
            if img_el:
                image_url = img_el.get("src")

        # Categorie
        category    = []
        product_name = name_el.get_text(strip=True)
        breadcrumbs  = soup.select(".breadcrumbs li")
        if breadcrumbs:
            crumbs   = [b.get_text(strip=True) for b in breadcrumbs]
            category = [
                c for c in crumbs
                if c.lower() not in ("home", "") and c != product_name
            ]

        # Omschrijving
        description  = None
        desc_block   = soup.select_one(".product-attribute--description")
        if desc_block:
            title_el = desc_block.select_one(".product-attribute__title, .element-title")
            if title_el:
                title_el.decompose()
            description = desc_block.get_text(" ", strip=True)[:2000]
        if not description:
            ld_desc = product_ld.get("description")
            if ld_desc and isinstance(ld_desc, str):
                description = ld_desc.strip()[:2000]

        # Price unit
        price_unit = None
        unit_el    = soup.select_one(".price-label")
        if unit_el:
            price_unit = unit_el.get_text(strip=True)

        # Staffelprijzen
        price_tiers = []
        tier_match  = re.search(r'"tierPrices"\s*:\s*', resp.text)
        if tier_match and price:
            try:
                decoder    = json.JSONDecoder()
                raw_tiers, _ = decoder.raw_decode(resp.text, tier_match.end())
                base_excl  = price  # min-qty price excl. used for discount %
                for t in raw_tiers:
                    qty_t  = int(t.get("qty", 0))
                    p_excl = round(float(t.get("basePrice", 0)), 4)
                    p_incl = round(float(t.get("price", 0)), 4)
                    disc   = round((1 - p_excl / base_excl) * 100) if base_excl else 0
                    price_tiers.append({
                        "qty":          qty_t,
                        "price_excl":   p_excl,
                        "price_incl":   p_incl,
                        "discount_pct": disc,
                    })
                price_tiers.sort(key=lambda x: x["qty"])
            except Exception:
                pass

        # Specificaties
        attributes = {}
        for item in soup.select(".product-attributes__item"):
            label = item.select_one(".product-attributes__item-label")
            value = item.select_one(".product-attributes__item-value")
            if label and value:
                key = label.get_text(strip=True)
                val = value.get_text(strip=True)
                if key and val:
                    attributes[key] = val

        return {
            "source_domain":        DOMAIN,
            "source_url":           url,
            "sku":                  sku,
            "name":                 name_el.get_text(strip=True),
            "brand":                brand,
            "description":          description,
            "category":             category,
            "image_url":            image_url,
            "price":                price,
            "price_incl_tax":       price_incl_tax,
            "price_before_discount": None,
            "currency":             "EUR",
            "price_unit":           price_unit,
            "min_order_qty":        min_qty,
            "in_stock":             in_stock,
            "stock_label":          stock_label,
            "rating":               rating,
            "review_count":         review_count,
            "attributes":           attributes,
            "price_tiers":          price_tiers,
        }

    except Exception as e:
        print(f"    ❌ Error: {url} → {e}")
        return None


# ─── ГЛАВНА ФУНКЦИЈА ───────────────────────────────────────────────────────────
def main():

    # 1. Земи ги категориите од менито
    print("=" * 55)
    print("ЧЕКОР 1: Категории од менито")
    print("=" * 55)
    categories = get_category_urls()

    # 2. За секоја категорија собери product URLs
    print("\n" + "=" * 55)
    print("ЧЕКОР 2: Собирање product URLs")
    print("=" * 55)
    all_product_urls = []
    seen_urls        = set()

    for i, cat in enumerate(categories, 1):
        print(f"[{i}/{len(categories)}] {cat['name']}")
        urls = get_product_urls_from_category(cat["url"])

        new = 0
        for u in urls:
            if u not in seen_urls:
                seen_urls.add(u)
                all_product_urls.append(u)
                new += 1

        print(f"  → {new} new | total: {len(all_product_urls)}")
        time.sleep(0.5)

    print(f"\n✅ Total unique product URLs: {len(all_product_urls)}")

    # 3. Scrape секој производ
    print("\n" + "=" * 55)
    print("ЧЕКОР 3: Scraping производи")
    print("=" * 55)
    all_products = []
    seen_skus    = set()
    failed       = 0

    for i, url in enumerate(all_product_urls, 1):
        product = scrape_product(url)

        if not product:
            failed += 1
            print(f"  ❌ [{i}/{len(all_product_urls)}] FAILED: {url}")
            continue

        if product["sku"] in seen_skus:
            continue

        seen_skus.add(product["sku"])
        all_products.append(product)
        print(f"  ✅ [{i}/{len(all_product_urls)}] {product['sku']} | {product['name'][:45]}")

        time.sleep(0.5)

    # 4. Зачувај во JSON
    with open("all_products.json", "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 55}")
    print(f"✅ DONE!")
    print(f"   Категории   : {len(categories)}")
    print(f"   Product URLs: {len(all_product_urls)}")
    print(f"   Зачувани    : {len(all_products)}")
    print(f"   Неуспешни   : {failed}")
    print(f"   Фајл        : all_products.json")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()