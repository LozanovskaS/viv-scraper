import json
import os
import time
import psycopg2
from psycopg2.extras import Json

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "viv_scraper"),
    "user":     os.getenv("POSTGRES_USER", "viv"),
    "password": os.getenv("POSTGRES_PASSWORD", "viv123"),
}

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS products (
    id                    SERIAL PRIMARY KEY,
    source_domain         VARCHAR(100) NOT NULL,
    source_url            TEXT         NOT NULL,
    sku                   VARCHAR(50)  NOT NULL,
    name                  TEXT         NOT NULL,
    brand                 VARCHAR(100),
    description           TEXT,
    category              TEXT[],
    image_url             TEXT,
    price                 NUMERIC(10,4),
    price_incl_tax        NUMERIC(10,4),
    price_before_discount NUMERIC(10,4),
    currency              VARCHAR(10)  DEFAULT 'EUR',
    price_unit            VARCHAR(200),
    min_order_qty         INTEGER,
    in_stock              BOOLEAN,
    stock_label           VARCHAR(100),
    rating                NUMERIC(3,2),
    review_count          INTEGER      DEFAULT 0,
    attributes            JSONB,
    price_tiers           JSONB,
    scraped_at            TIMESTAMP    DEFAULT NOW(),
    UNIQUE (sku, source_domain)
);
"""

UPSERT = """
INSERT INTO products (
    source_domain, source_url, sku, name, brand, description,
    category, image_url, price, price_incl_tax, price_before_discount,
    currency, price_unit, min_order_qty, in_stock, stock_label,
    rating, review_count, attributes, price_tiers
) VALUES (
    %(source_domain)s, %(source_url)s, %(sku)s, %(name)s, %(brand)s, %(description)s,
    %(category)s, %(image_url)s, %(price)s, %(price_incl_tax)s, %(price_before_discount)s,
    %(currency)s, %(price_unit)s, %(min_order_qty)s, %(in_stock)s, %(stock_label)s,
    %(rating)s, %(review_count)s, %(attributes)s, %(price_tiers)s
)
ON CONFLICT (sku, source_domain) DO UPDATE SET
    source_url            = EXCLUDED.source_url,
    name                  = EXCLUDED.name,
    brand                 = EXCLUDED.brand,
    description           = EXCLUDED.description,
    category              = EXCLUDED.category,
    image_url             = EXCLUDED.image_url,
    price                 = EXCLUDED.price,
    price_incl_tax        = EXCLUDED.price_incl_tax,
    price_before_discount = EXCLUDED.price_before_discount,
    currency              = EXCLUDED.currency,
    price_unit            = EXCLUDED.price_unit,
    min_order_qty         = EXCLUDED.min_order_qty,
    in_stock              = EXCLUDED.in_stock,
    stock_label           = EXCLUDED.stock_label,
    rating                = EXCLUDED.rating,
    review_count          = EXCLUDED.review_count,
    attributes            = EXCLUDED.attributes,
    price_tiers           = EXCLUDED.price_tiers,
    scraped_at            = NOW();
"""


def connect(retries=5, delay=3):
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            print(f"Connected to PostgreSQL")
            return conn
        except psycopg2.OperationalError as e:
            print(f"  Attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)
    raise SystemExit("Could not connect to PostgreSQL")


def main():
    conn = connect()
    cur  = conn.cursor()

    cur.execute(CREATE_TABLE)
    conn.commit()
    print("Table ready")

    with open("all_products.json", encoding="utf-8") as f:
        products = json.load(f)

    print(f"Loading {len(products)} products...")

    ok = 0
    for p in products:
        cur.execute(UPSERT, {
            "source_domain":        p.get("source_domain"),
            "source_url":           p.get("source_url"),
            "sku":                  p.get("sku"),
            "name":                 p.get("name"),
            "brand":                p.get("brand"),
            "description":          p.get("description"),
            "category":             p.get("category") or [],
            "image_url":            p.get("image_url"),
            "price":                p.get("price"),
            "price_incl_tax":       p.get("price_incl_tax"),
            "price_before_discount": p.get("price_before_discount"),
            "currency":             p.get("currency", "EUR"),
            "price_unit":           p.get("price_unit"),
            "min_order_qty":        p.get("min_order_qty"),
            "in_stock":             p.get("in_stock"),
            "stock_label":          p.get("stock_label"),
            "rating":               p.get("rating"),
            "review_count":         p.get("review_count", 0),
            "attributes":           Json(p.get("attributes") or {}),
            "price_tiers":          Json(p.get("price_tiers") or []),
        })
        ok += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done — {ok} products upserted")


if __name__ == "__main__":
    main()
