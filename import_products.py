"""
سكريبت استيراد المنتجات من روابط خارجية (نسخة محسّنة)
======================================================
يدعم:
  - روابط share.google (Google Shopping)
  - روابط amzn.eu (Amazon المختصرة)
  - روابط Amazon.eg المباشرة
  - مواقع مصرية: بي.تك، رنين، الغزاوي، العراقي، Rush Brush، Hapilin، Cairo Sales

الاستخدام:
    python import_products.py
"""

import os
import sys
import re
import json
import time
import requests
from uuid import uuid4
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# ── إعداد المسارات ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import app, db, Product, Category, AdditionalImage, AdditionalData, Cart

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}

# ══════════════════════════════════════════════════════════════
#  بيانات المنتجات المستخرجة من الروابط
# ══════════════════════════════════════════════════════════════

PRODUCT_LINKS = [
    # Amazon.eg
    {"url": "https://share.google/tBSuLDlTxM0StivQp", "source": "Amazon.eg"},
    {"url": "https://share.google/ERX6YVY3628Zg2639", "source": "Amazon.eg"},
    # شركة العراقى
    {"url": "https://share.google/U1RGgvrZJeqbTqqMl", "source": "شركة العراقى"},
    # الغزاوي
    {"url": "https://share.google/mm9PJWKWjm05Qs7ec", "source": "الغزاوي"},
    {"url": "https://share.google/CTkARvtfeFcfKBLiu", "source": "الغزاوي"},
    # Cairo Sales Stores
    {"url": "https://share.google/gwpxbsuFCCIhZQeWW", "source": "Cairo Sales"},
    {"url": "https://share.google/qzxWMCYP9sIPfF6iY", "source": "Cairo Sales"},
    {"url": "https://share.google/8veDpdw9H4Hh3DsPT", "source": "Cairo Sales"},
    # Raneen
    {"url": "https://share.google/8dBlGtqqgH2xX8wx8", "source": "Raneen"},
    # Eval El-Torkey
    {"url": "https://share.google/WcbUj4PZPB6fjlCOw", "source": "Eval El-Torkey"},
    {"url": "https://share.google/v9VQQYJ2gkgEHRImS", "source": "Eval El-Torkey"},
    # Amazon - طقم أواني
    {"url": "https://amzn.eu/d/0cfF4hjR", "source": "Amazon.eg",
     "fallback_name": "طقم أواني طهي من الجرانيت ماستر فلاور، لون أسود 11 قطعة تروفال، مصقول"},
    # Amazon.eg
    {"url": "https://share.google/1ui3HQL5PLY8bBCwR", "source": "Amazon.eg"},
    {"url": "https://share.google/YfqApxBefVWvUNLdN", "source": "Amazon.eg"},
    # Raneen
    {"url": "https://share.google/viZTKCnwZY1H2viUZ", "source": "Raneen"},
    # بي.تك
    {"url": "https://share.google/rdqYKouvJxE2404th", "source": "بي.تك"},
    {"url": "https://share.google/aHHE1FwT17YT7hyA9", "source": "بي.تك"},
    {"url": "https://share.google/tOBsj31CLhLByiRKM", "source": "بي.تك"},
    {"url": "https://share.google/5LXxyCohaWBfSfdz4", "source": "بي.تك"},
    # Amazon.eg
    {"url": "https://share.google/dJMA86V7iwfEMHVyC", "source": "Amazon.eg"},
    {"url": "https://share.google/oDNg9ltpPksMPHn1r", "source": "Amazon.eg"},
    # Amazon - ماكينات ازالة شعر
    {"url": "https://amzn.eu/d/08j95yTn", "source": "Amazon.eg",
     "fallback_name": "ماكينة ازالة الشعر للاستخدام الجاف والرطب سيلك ابيل 5-820 من براون"},
    {"url": "https://amzn.eu/d/0bxoFKS3", "source": "Amazon.eg",
     "fallback_name": "ماكينة ازالة الشعر سيلك ابيل 5 سينسو سمارت 5-620 من براون"},
    {"url": "https://share.google/yzVKFgGr0QHXUPDR7", "source": "Amazon.eg"},
    {"url": "https://amzn.eu/d/0eKUuDah", "source": "Amazon.eg",
     "fallback_name": "آلة إزالة الشعر براون سيلك ابيل 513-5 للمبتدئات"},
    {"url": "https://amzn.eu/d/0esryerg", "source": "Amazon.eg",
     "fallback_name": "ماكينة ازالة الشعر سيلك ابيل 9 سينسو سمارت 9-720 من براون"},
    # Amazon.eg
    {"url": "https://share.google/8Uku7YZ1YdISZIiW3", "source": "Amazon.eg"},
    # بي.تك
    {"url": "https://share.google/DPquu5uLE50XSVPVf", "source": "بي.تك"},
    # Amazon.eg
    {"url": "https://share.google/7PsDyqQtXsqajEiPD", "source": "Amazon.eg"},
    {"url": "https://share.google/5esxwLoTnk3V5HlFt", "source": "Amazon.eg"},
    # Hapilin
    {"url": "https://share.google/cTNGux2XUhQiVsZga", "source": "Hapilin"},
    # Amazon.eg
    {"url": "https://share.google/ITPxbHYrOAiXx1SHR", "source": "Amazon.eg"},
    # بي.تك
    {"url": "https://share.google/aolhzZwJkThtBeU3A", "source": "بي.تك"},
    # Amazon - ماكينة إزالة شعر
    {"url": "https://amzn.eu/d/0cvjJvk7", "source": "Amazon.eg",
     "fallback_name": "ماكينة إزالة الشعر سيلك اكسبرت برو موديل PL3233 من براون"},
    # Amazon.eg
    {"url": "https://share.google/0QuDcchoEnpA3ww0w", "source": "Amazon.eg"},
    # RUSH BRUSH
    {"url": "https://share.google/hrZu82xSUnD3uSRXY", "source": "RUSH BRUSH"},
    # Amazon.eg
    {"url": "https://share.google/sAyl4dMILSheDE9Qm", "source": "Amazon.eg"},
    # RUSH BRUSH
    {"url": "https://share.google/1XAtrCVzQeW5c9mXZ", "source": "RUSH BRUSH"},
    {"url": "https://share.google/r5SZ9iiLb0d0iZsji", "source": "RUSH BRUSH"},
    {"url": "https://share.google/LTNiv78JOo4Q02YJd", "source": "RUSH BRUSH"},
    # Amazon.eg
    {"url": "https://share.google/k0FyBMJPxtCSuhhUB", "source": "Amazon.eg"},
    {"url": "https://share.google/IGudvNoJukWiuV96Q", "source": "Amazon.eg"},
    {"url": "https://share.google/gAkTJhrLijdBwiwOU", "source": "Amazon.eg"},
    {"url": "https://share.google/xGgrUBawajKM117uw", "source": "Amazon.eg"},
    # RUSH BRUSH
    {"url": "https://share.google/GXditokkatFPH3wD0", "source": "RUSH BRUSH"},
]


# ══════════════════════════════════════════════════════════════
#  وظائف مساعدة
# ══════════════════════════════════════════════════════════════

def download_image(image_url: str) -> str | None:
    """تحميل صورة من رابط وحفظها محليًا"""
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()
        ct = resp.headers.get('content-type', '')
        ext = 'jpg'
        if 'png' in ct:
            ext = 'png'
        elif 'webp' in ct:
            ext = 'webp'
        elif 'gif' in ct:
            ext = 'gif'
        filename = f"{uuid4().hex}.{ext}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        with open(path, 'wb') as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        # تحقق أن الملف مش فاضي
        if os.path.getsize(path) < 500:
            os.remove(path)
            return None
        return filename
    except Exception as e:
        print(f"   ⚠ فشل تحميل صورة: {e}")
        return None


def scrape_amazon(soup, url: str) -> dict:
    """سحب بيانات من صفحة أمازون"""
    # الاسم
    name = None
    tag = soup.select_one('#productTitle')
    if tag:
        name = tag.get_text(strip=True)

    # السعر
    price = None
    for sel in ['span.a-price span.a-offscreen', '.a-price .a-offscreen',
                '#priceblock_ourprice', '#priceblock_dealprice',
                '.a-price-whole', '#corePrice_feature_div .a-offscreen']:
        tag = soup.select_one(sel)
        if tag:
            txt = tag.get_text(strip=True)
            nums = re.findall(r'[\d,]+\.?\d*', txt.replace(',', ''))
            if nums:
                try:
                    price = float(nums[0])
                    break
                except ValueError:
                    pass

    # السعر الأصلي (قبل الخصم)
    original_price = None
    for sel in ['.a-text-price span.a-offscreen', '.basisPrice .a-offscreen',
                '#listPrice', '.a-price[data-a-strike] .a-offscreen']:
        tag = soup.select_one(sel)
        if tag:
            txt = tag.get_text(strip=True)
            nums = re.findall(r'[\d,]+\.?\d*', txt.replace(',', ''))
            if nums:
                try:
                    original_price = float(nums[0])
                    break
                except ValueError:
                    pass

    discount = 0.0
    if original_price and price and original_price > price:
        discount = round(((original_price - price) / original_price) * 100, 1)

    # الوصف
    description = ''
    desc_tag = soup.select_one('#productDescription')
    if desc_tag:
        description = desc_tag.get_text(strip=True)[:2000]
    if not description:
        bullets = soup.select('#feature-bullets li span.a-list-item')
        if bullets:
            description = ' | '.join(b.get_text(strip=True) for b in bullets[:10])[:2000]

    # الصورة الرئيسية
    image_url = None
    img_tag = soup.select_one('#imgTagWrapperId img, #landingImage')
    if img_tag:
        # Try data-a-dynamic-image first (high res)
        dyn = img_tag.get('data-a-dynamic-image')
        if dyn:
            try:
                d = json.loads(dyn)
                if d:
                    image_url = list(d.keys())[-1]  # اختار أكبر resolution
            except (json.JSONDecodeError, IndexError):
                pass
        if not image_url:
            image_url = img_tag.get('data-old-hires') or img_tag.get('src')

    # صور إضافية
    additional = []
    thumbs = soup.select('#altImages img, .imageThumbnail img')
    for t in thumbs[:8]:
        src = t.get('src', '')
        if src and 'sprite' not in src and 'play-button' not in src:
            # حوّل thumbnail لصورة كبيرة
            hi_res = re.sub(r'\._[A-Z0-9_,]+_\.', '.', src)
            if hi_res != image_url and hi_res not in additional:
                additional.append(hi_res)

    return {
        'name': name,
        'price': price,
        'discount': discount,
        'description': description,
        'image_url': image_url,
        'additional_images': additional,
    }


def scrape_generic(soup, url: str) -> dict:
    """سحب بيانات من أي موقع آخر (بي.تك، رنين، الغزاوي، إلخ)"""
    # الاسم
    name = None
    for sel in ['h1', '[itemprop="name"]', '.product-title', '.product_title',
                '.product-name', '.product__title', 'h1.page-title',
                '.product-info h1', 'h2.product-name']:
        tag = soup.select_one(sel)
        if tag and tag.get_text(strip=True):
            name = tag.get_text(strip=True)[:300]
            break
    if not name:
        og = soup.find('meta', property='og:title')
        if og:
            name = og.get('content', '')[:300]

    # السعر
    price = None
    for sel in ['[itemprop="price"]', '.price ins', '.price .current',
                '.product-price', '.current-price', 'span.price',
                '.special-price .price', '.product-info-price .price',
                '.price-box .price', 'meta[itemprop="price"]']:
        tag = soup.select_one(sel)
        if tag:
            content = tag.get('content') or tag.get_text(strip=True)
            nums = re.findall(r'[\d,]+\.?\d*', content.replace(',', ''))
            if nums:
                try:
                    price = float(nums[0])
                    break
                except ValueError:
                    pass
    if price is None:
        og = soup.find('meta', property='product:price:amount')
        if og:
            try:
                price = float(og.get('content', '0'))
            except ValueError:
                pass

    # السعر قبل الخصم
    original_price = None
    for sel in ['.price del', '.old-price .price', '.was-price',
                'del .woocommerce-Price-amount', '.compare-price',
                '.price-box .old-price .price']:
        tag = soup.select_one(sel)
        if tag:
            content = tag.get('content') or tag.get_text(strip=True)
            nums = re.findall(r'[\d,]+\.?\d*', content.replace(',', ''))
            if nums:
                try:
                    original_price = float(nums[0])
                    break
                except ValueError:
                    pass

    discount = 0.0
    if original_price and price and original_price > price:
        discount = round(((original_price - price) / original_price) * 100, 1)

    # الوصف
    description = ''
    for sel in ['[itemprop="description"]', '.product-description',
                '#productDescription', '.description', '.product__description',
                '.product-info-description', '.product-cms-block',
                '.short-description']:
        tag = soup.select_one(sel)
        if tag:
            description = tag.get_text(strip=True)[:2000]
            break
    if not description:
        og = soup.find('meta', property='og:description')
        if og:
            description = og.get('content', '')[:2000]
    if not description:
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '')[:2000]

    # الصورة الرئيسية
    image_url = None
    for sel in ['[itemprop="image"]', '.product-image img', '#main-image',
                '.gallery-image img', 'img.product-image',
                '.product-media img', '.fotorama img',
                '.product-img img', '.product-gallery__image img']:
        tag = soup.select_one(sel)
        if tag:
            image_url = tag.get('src') or tag.get('data-src') or tag.get('data-lazy') or tag.get('data-zoom')
            if image_url:
                image_url = urljoin(url, image_url)
                break
    if not image_url:
        og = soup.find('meta', property='og:image')
        if og:
            image_url = urljoin(url, og.get('content', ''))

    # صور إضافية
    additional = []
    for sel in ['.product-gallery img', '.thumbnail img', '[data-gallery] img',
                '.product-images img', '.more-views img', '.product-thumbs img']:
        imgs = soup.select(sel)
        if imgs:
            for img in imgs[:10]:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src:
                    full = urljoin(url, src)
                    if full != image_url and full not in additional:
                        additional.append(full)
            if additional:
                break

    return {
        'name': name,
        'price': price,
        'discount': discount,
        'description': description,
        'image_url': image_url,
        'additional_images': additional,
    }


def scrape_product(url: str, fallback_name: str = None) -> dict:
    """سحب بيانات منتج - يدعم أمازون + مواقع أخرى"""
    try:
        # تابع الـ redirects
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        final_url = resp.url
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # اختر الـ scraper المناسب
        if 'amazon' in final_url.lower():
            data = scrape_amazon(soup, final_url)
        else:
            data = scrape_generic(soup, final_url)

        # استخدم الاسم البديل لو مفيش اسم
        if not data['name'] and fallback_name:
            data['name'] = fallback_name

        data['success'] = bool(data['name'])
        data['final_url'] = final_url
        if not data['success']:
            data['error'] = 'لم يتم العثور على اسم المنتج'

        return data

    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'انتهت مهلة الاتصال', 'final_url': url}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'فشل الاتصال بالموقع', 'final_url': url}
    except Exception as e:
        return {'success': False, 'error': str(e), 'final_url': url}


# ══════════════════════════════════════════════════════════════
#  قاعدة البيانات
# ══════════════════════════════════════════════════════════════

def clear_old_data():
    """مسح كل المنتجات والأقسام والصور القديمة"""
    with app.app_context():
        Cart.query.delete()
        AdditionalData.query.delete()
        AdditionalImage.query.delete()
        Product.query.delete()
        Category.query.delete()
        db.session.commit()

    # مسح ملفات الصور
    for f in os.listdir(UPLOAD_FOLDER):
        fpath = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass

    print("✓ تم مسح كل البيانات القديمة")


def get_or_create_category(name: str) -> int:
    """إنشاء أو إيجاد قسم"""
    cat = Category.query.filter_by(name=name).first()
    if not cat:
        cat = Category(name=name, description=f'منتجات {name}')
        db.session.add(cat)
        db.session.flush()
    return cat.id


def import_single_product(item: dict, index: int, total: int) -> bool:
    """استيراد منتج واحد"""
    url = item['url']
    source = item.get('source', 'عام')
    fallback = item.get('fallback_name')

    print(f"\n[{index}/{total}] 🔗 {url}")
    print(f"   المصدر: {source}")

    data = scrape_product(url, fallback)

    if not data.get('success'):
        print(f"   ✗ فشل: {data.get('error', 'خطأ غير معروف')}")
        print(f"   ℹ الرابط النهائي: {data.get('final_url', url)}")
        return False

    name = data['name'][:100] if data['name'] else 'منتج بدون اسم'
    price = data.get('price') or 0
    discount = data.get('discount') or 0
    description = data.get('description') or 'لا يوجد وصف'

    print(f"   ✓ {name}")
    print(f"   ✓ السعر: {price} | الخصم: {discount}%")

    # القسم
    cat_id = get_or_create_category(source)

    # الصورة الرئيسية
    main_image = 'default.jpg'
    if data.get('image_url'):
        dl = download_image(data['image_url'])
        if dl:
            main_image = dl
            print(f"   ✓ صورة: {dl}")

    # إنشاء المنتج
    product = Product(
        name=name,
        price=price,
        discount=discount,
        stock=100,
        description=description[:2000],
        image=main_image,
        category_id=cat_id,
    )
    db.session.add(product)
    db.session.flush()

    # صور إضافية
    for img_url in (data.get('additional_images') or []):
        img_file = download_image(img_url)
        if img_file:
            db.session.add(AdditionalImage(image=img_file, product_id=product.id))

    db.session.commit()
    print(f"   ✅ تم (ID: {product.id})")
    return True


# ══════════════════════════════════════════════════════════════
#  التشغيل
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  استيراد المنتجات - الحامد")
    print(f"  عدد الروابط: {len(PRODUCT_LINKS)}")
    print("=" * 60)

    confirm = input("\n⚠  سيتم مسح كل المنتجات القديمة. هل تريد المتابعة؟ (y/نعم): ").strip().lower()
    if confirm not in ('نعم', 'y', 'yes'):
        print("تم الإلغاء.")
        return

    with app.app_context():
        clear_old_data()

        success = 0
        failed = 0
        failed_urls = []

        for i, item in enumerate(PRODUCT_LINKS, 1):
            try:
                if import_single_product(item, i, len(PRODUCT_LINKS)):
                    success += 1
                else:
                    failed += 1
                    failed_urls.append(item['url'])
            except Exception as e:
                print(f"   ✗ خطأ غير متوقع: {e}")
                failed += 1
                failed_urls.append(item['url'])
                db.session.rollback()

            # تأخير بسيط بين الطلبات عشان ما يتم حظرنا
            time.sleep(1)

    print("\n" + "=" * 60)
    print(f"  ✅ نجح: {success}")
    print(f"  ✗ فشل: {failed}")
    print(f"  📦 إجمالي: {len(PRODUCT_LINKS)}")
    if failed_urls:
        print("\n  الروابط الفاشلة:")
        for u in failed_urls:
            print(f"    - {u}")
    print("=" * 60)


if __name__ == '__main__':
    main()
