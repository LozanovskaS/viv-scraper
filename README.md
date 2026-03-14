# VIV Webshop Scraper

Scrapes all products from [webshop.viv.nl](https://webshop.viv.nl) and stores them in a PostgreSQL database.

## What it does

- Crawls all categories and product pages
- Extracts a generic product model (name, SKU, price, stock, attributes, price tiers, etc.)
- Stores results in PostgreSQL using upsert — safe to run multiple times

## Project structure

```
viv-scraper/
├── docker-compose.yml
└── scraper/
    ├── scraper.py          # crawls webshop.viv.nl and saves to all_products.json
    ├── db_loader.py        # loads all_products.json into PostgreSQL
    ├── requirements.txt
    ├── Dockerfile
    └── all_products.json   # 911 products
```

## Quick start

**Requirements:** Docker + Docker Compose

1. Clone the repo
   ```bash
   git clone https://github.com/LozanovskaS/viv-scraper.git
   cd viv-scraper
   ```

2. Create a `.env` file in the root

3. Start the database and load all products:
   ```bash
   docker-compose up --build
   ```

That's it. The `loader` container will connect to PostgreSQL and upsert all 911 products.

## Product model

Each product contains:

| Field | Description |
|-------|-------------|
| `sku` | Article number |
| `name` | Product name |
| `brand` | Brand |
| `description` | Full description |
| `category` | Breadcrumb path as array |
| `price` | Price excl. VAT |
| `price_incl_tax` | Price incl. VAT |
| `price_tiers` | Quantity discounts (JSONB) |
| `attributes` | Product specs (JSONB) |
| `in_stock` | Stock status |
| `rating` / `review_count` | Customer reviews |
| `source_url` | Original product URL |

## Re-scrape

To fetch fresh data from the website:
```bash
docker-compose run --rm loader python scraper.py
```

Then reload into the database:
```bash
docker-compose up
```

## Tech stack

- Python 3.12
- BeautifulSoup4 + requests
- PostgreSQL 16
- Docker + Docker Compose
