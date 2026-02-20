"""
Seed script: fetches 100 products from DummyJSON, downloads their thumbnail
images, creates Arabic categories, clears all old data, then inserts everything.

Run: python3 seed_data.py
"""
import os
import sys
import requests
from uuid import uuid4

sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Category, Product, Cart, Order, OrderItem, AdditionalImage, AdditionalData

# Arabic translations for categories
CATEGORY_ARABIC = {
    "beauty":               "التجميل والعناية",
    "fragrances":           "العطور",
    "furniture":            "الأثاث",
    "groceries":            "البقالة والمواد الغذائية",
    "home-decoration":      "ديكور المنزل",
    "kitchen-accessories":  "أدوات المطبخ",
    "laptops":              "اللابتوبات",
    "mens-shirts":          "قمصان رجالي",
    "mens-shoes":           "أحذية رجالي",
    "mens-watches":         "ساعات رجالي",
    "mobile-accessories":   "إكسسوارات الموبايل",
    "motorcycle":           "موتوسيكلات",
    "skin-care":            "العناية بالبشرة",
    "smartphones":          "الهواتف الذكية",
    "sports-accessories":   "الرياضة واللياقة",
    "sunglasses":           "النظارات الشمسية",
    "tablets":              "التابلت",
    "tops":                 "تيشيرتات وملابس علوية",
    "vehicle":              "السيارات والمركبات",
    "womens-bags":          "حقائب نسائية",
    "womens-dresses":       "فساتين نسائية",
    "womens-jewellery":     "مجوهرات نسائية",
    "womens-shoes":         "أحذية نسائية",
    "womens-watches":       "ساعات نسائية",
}

CATEGORY_DESC_ARABIC = {
    "beauty":               "منتجات التجميل والعناية الشخصية",
    "fragrances":           "عطور وبرفانات فاخرة",
    "furniture":            "أثاث منزلي عصري وأنيق",
    "groceries":            "مواد غذائية ومستلزمات المنزل",
    "home-decoration":      "ديكورات وإكسسوارات منزلية",
    "kitchen-accessories":  "أدوات ومستلزمات المطبخ",
    "laptops":              "لابتوبات وكمبيوترات محمولة",
    "mens-shirts":          "قمصان وملابس رجالي عصرية",
    "mens-shoes":           "أحذية رجالي متنوعة",
    "mens-watches":         "ساعات رجالي أصيلة وأنيقة",
    "mobile-accessories":   "إكسسوارات وملحقات الهاتف",
    "motorcycle":           "موتوسيكلات وملحقاتها",
    "skin-care":            "منتجات العناية بالبشرة",
    "smartphones":          "أحدث الهواتف الذكية",
    "sports-accessories":   "معدات وملابس رياضية",
    "sunglasses":           "نظارات شمسية بأشكال متنوعة",
    "tablets":              "أجهزة تابلت وآيباد",
    "tops":                 "تيشيرتات وملابس كاجوال",
    "vehicle":              "سيارات ووسائل نقل",
    "womens-bags":          "حقائب وشنط نسائية أنيقة",
    "womens-dresses":       "فساتين سواريه وكاجوال",
    "womens-jewellery":     "مجوهرات وإكسسوارات نسائية",
    "womens-shoes":         "أحذية نسائية بأحدث الموديلات",
    "womens-watches":       "ساعات نسائية فاخرة",
}


def download_image(url, upload_folder):
    """Download image from URL and save to upload folder. Returns filename or None."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        }
        resp = requests.get(url, headers=headers, timeout=15, stream=True)
        resp.raise_for_status()

        ext = 'jpg'
        ct = resp.headers.get('content-type', '')
        if 'webp' in ct:
            ext = 'webp'
        elif 'png' in ct:
            ext = 'png'
        elif url.endswith('.webp'):
            ext = 'webp'
        elif url.endswith('.png'):
            ext = 'png'

        filename = f"{uuid4().hex}.{ext}"
        path = os.path.join(upload_folder, filename)
        with open(path, 'wb') as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        if os.path.getsize(path) < 500:
            os.remove(path)
            return None
        return filename
    except Exception as e:
        print(f"  [WARN] Failed to download {url}: {e}")
        return None


def main():
    upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)

    with app.app_context():
        # ── 1. Clear old data ────────────────────────────────────────────────
        print("Clearing old data...")
        try:
            db.session.execute(AdditionalImage.__table__.delete())
            db.session.execute(AdditionalData.__table__.delete())
            db.session.execute(OrderItem.__table__.delete())
            db.session.execute(Cart.__table__.delete())
            db.session.execute(Order.__table__.delete())
            db.session.execute(Product.__table__.delete())
            db.session.execute(Category.__table__.delete())
            db.session.commit()
            print("  Done.")
        except Exception as e:
            db.session.rollback()
            print(f"  [WARN] Clear error (continuing): {e}")

        # ── 2. Fetch all products from DummyJSON (100 items) ─────────────────
        print("Fetching products from DummyJSON...")
        resp = requests.get("https://dummyjson.com/products?limit=100&skip=0", timeout=30)
        resp.raise_for_status()
        products_raw = resp.json()['products']
        print(f"  Got {len(products_raw)} products.")

        # ── 3. Create categories ─────────────────────────────────────────────
        print("Creating categories...")
        category_map = {}  # slug -> Category instance
        seen_slugs = set()
        for p in products_raw:
            slug = p['category']
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                name_ar = CATEGORY_ARABIC.get(slug, slug.replace('-', ' ').title())
                desc_ar = CATEGORY_DESC_ARABIC.get(slug, '')
                cat = Category(name=name_ar, description=desc_ar)
                db.session.add(cat)
                db.session.flush()
                category_map[slug] = cat
                print(f"  Category: {name_ar}")
        db.session.commit()

        # ── 4. Insert products with images ───────────────────────────────────
        print("Inserting products (downloading images)...")
        for idx, p in enumerate(products_raw, 1):
            slug = p['category']
            cat = category_map.get(slug)
            if not cat:
                continue

            # Download thumbnail
            thumb_url = p.get('thumbnail', '')
            print(f"  [{idx}/100] {p['title']} - downloading image...")
            image_filename = download_image(thumb_url, upload_folder) if thumb_url else None

            # Fallback: use first image in images list
            if not image_filename and p.get('images'):
                image_filename = download_image(p['images'][0], upload_folder)

            # Absolute fallback: store URL path directly (won't display but won't crash)
            image_path = f"static/uploads/{image_filename}" if image_filename else 'static/uploads/placeholder.jpg'

            # Price in EGP (multiply USD by ~50)
            price_egp = round(float(p.get('price', 0)) * 50, 2)
            discount = round(float(p.get('discountPercentage', 0)), 1)
            stock = int(p.get('stock', 10))

            # Build Arabic-ish description (keep English for now, it's demo data)
            description = p.get('description', '')

            product = Product(
                name=p['title'],
                price=price_egp,
                discount=discount,
                stock=stock,
                description=description,
                image=image_path,
                category_id=cat.id,
            )
            db.session.add(product)
            db.session.flush()

            # Download and attach additional images (up to 3)
            for img_url in p.get('images', [])[:3]:
                if img_url == thumb_url:
                    continue
                add_filename = download_image(img_url, upload_folder)
                if add_filename:
                    ai = AdditionalImage(
                        product_id=product.id,
                        image=f"static/uploads/{add_filename}"
                    )
                    db.session.add(ai)

            db.session.commit()
            print(f"    ✓ Saved (price={price_egp} EGP, discount={discount}%)")

        total = Product.query.count()
        cat_total = Category.query.count()
        print(f"\nDone! {total} products in {cat_total} categories inserted.")


if __name__ == '__main__':
    main()
