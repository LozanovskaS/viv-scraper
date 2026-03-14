"""
Quick test: scrape a handful of product URLs and print the result.
Run with:  python test_few.py
"""
import json
from test_scraper import scrape_product

TEST_URLS = [
    "https://webshop.viv.nl/brievenbusdoosjes-220-x-155-x-28-mm-a5-formaat-bruin",
    "https://webshop.viv.nl/kraftpapier-op-rol-50-cm-x-400-meter-50-gram-m2-wit",
    "https://webshop.viv.nl/bubbeltjesfolie-op-rol-50-cm-x-100-meter-kleine-bellen",
]

for url in TEST_URLS:
    print(f"\n{'-' * 60}")
    print(f"URL: {url}")
    product = scrape_product(url)
    if product:
        print(json.dumps(product, ensure_ascii=False, indent=2))
    else:
        print("  FAILED to scrape")
