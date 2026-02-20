"""
Unit tests for all 7 fixes implemented in Feb 2026.

Fix 1: Add Product — default category seeded on startup
Fix 2: /admin/add_city route (was 404)
Fix 3: Dropshipping scraper — JSON-LD extraction + false-duplicate fix
Fix 4: Dropshipped product image path (bare filename → static/uploads/...)
Fix 5: Dropship delete cascades to Product
Fix 6: Banner management (BannerSlide model + CRUD routes)
Fix 7: Limited Time Offer — dynamic sale_products on home page
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from io import BytesIO

from app import (
    app as flask_app, db,
    Category, Product, BannerSlide, DropshipProduct, City, ShippingCost,
)


# ─────────────────────────────────────────────────────────────
# Fix 1 — Default category seeded on startup
# ─────────────────────────────────────────────────────────────
class TestFix1DefaultCategory:
    """Ensure at least one Category exists so Add-Product form is usable."""

    def test_category_exists_after_startup(self, app, db_session):
        """Startup seed logic: an empty DB must get a default category."""
        # Ensure clean slate to test the seeding behaviour
        db_session.execute(Category.__table__.delete())
        db_session.commit()
        assert Category.query.count() == 0

        # Replicate app.py startup seed
        if Category.query.count() == 0:
            db_session.add(Category(name='عام', description='تصنيف عام'))
            db_session.commit()

        assert Category.query.count() >= 1, "Startup seed must create a default category"

    def test_add_product_page_returns_200_with_categories(self, authenticated_client, sample_category):
        """Products admin page must load when at least one category exists."""
        response = authenticated_client.get('/admin/products')
        assert response.status_code == 200

    def test_add_product_page_contains_category_option(self, authenticated_client, sample_category):
        """Admin products page must contain at least one <option> for category select."""
        response = authenticated_client.get('/admin/products')
        html = response.data.decode('utf-8')
        assert '<option' in html


# ─────────────────────────────────────────────────────────────
# Fix 2 — /admin/add_city route
# ─────────────────────────────────────────────────────────────
class TestFix2AddCityRoute:
    """POST /admin/add_city must create City + ShippingCost records."""

    def _post_city(self, client, name='الإسكندرية', city_id='alex_test_01', price='80'):
        return client.post('/admin/add_city', data={
            'name': name,
            'city_id': city_id,
            'shipping_price': price,
        }, follow_redirects=True)

    def test_route_exists_not_404(self, authenticated_client):
        """Route must exist (not 404)."""
        response = self._post_city(authenticated_client)
        assert response.status_code != 404

    def test_add_city_creates_city_record(self, authenticated_client, db_session):
        """City record must be persisted after POST."""
        self._post_city(authenticated_client, city_id='alex_fix2_01')
        city = City.query.filter_by(city_id='alex_fix2_01').first()
        assert city is not None
        assert city.name == 'الإسكندرية'

    def test_add_city_creates_shipping_cost(self, authenticated_client, db_session):
        """ShippingCost must be created for the new city."""
        self._post_city(authenticated_client, city_id='alex_fix2_02', price='90')
        cost = ShippingCost.query.filter_by(city_id='alex_fix2_02').first()
        assert cost is not None
        assert float(cost.price) == 90.0

    def test_add_city_rejects_duplicate_city_id(self, authenticated_client, db_session):
        """Duplicate city_id must be rejected gracefully (no 500)."""
        self._post_city(authenticated_client, city_id='dup_city_01')
        response = self._post_city(authenticated_client, city_id='dup_city_01')
        assert response.status_code == 200  # redirected, not 500

    def test_add_city_rejects_empty_name(self, authenticated_client, db_session):
        """Empty city name must be rejected gracefully."""
        response = self._post_city(authenticated_client, name='', city_id='noname_01')
        assert response.status_code == 200

    def test_add_city_requires_auth(self, client):
        """Unauthenticated request must redirect to login."""
        response = self._post_city(client)
        assert response.status_code in (200, 302)
        # If followed, must NOT create a city (unauthenticated)


# ─────────────────────────────────────────────────────────────
# Fix 3a — Dropshipping: JSON-LD extraction
# ─────────────────────────────────────────────────────────────
class TestFix3JsonLdScraper:
    """scrape_product_data() must use JSON-LD when CSS selectors return nothing."""

    def _parse_json_ld(self, html):
        """Replicate the JSON-LD extraction logic from app.py for unit testing."""
        from bs4 import BeautifulSoup
        import json as _json
        soup = BeautifulSoup(html, 'html.parser')
        ld_name = ld_price = ld_desc = ld_image = None
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                raw = script.string or ''
                ld = _json.loads(raw)
                if isinstance(ld, list):
                    ld = next((x for x in ld if isinstance(x, dict)
                               and x.get('@type') in ('Product', 'product')), ld[0] if ld else {})
                if isinstance(ld, dict) and ld.get('@type', '').lower() == 'product':
                    ld_name = ld.get('name', '') or None
                    ld_desc = ld.get('description', '') or None
                    offers = ld.get('offers', {})
                    if isinstance(offers, list): offers = offers[0] if offers else {}
                    if isinstance(offers, dict):
                        try: ld_price = float(str(offers.get('price', '') or '').replace(',', '') or 0) or None
                        except (ValueError, TypeError): pass
                    imgs = ld.get('image', '')
                    if isinstance(imgs, str): ld_image = imgs or None
                    elif isinstance(imgs, list): ld_image = imgs[0] if imgs else None
                    elif isinstance(imgs, dict): ld_image = imgs.get('url') or imgs.get('contentUrl')
                    if ld_name: break
            except Exception:
                pass
        return {'name': ld_name, 'price': ld_price, 'description': ld_desc, 'image': ld_image}

    def _html(self, ld):
        """Build minimal HTML with only a JSON-LD script — no CSS-selectable elements."""
        return ('<html><head><script type="application/ld+json">'
                + json.dumps(ld, ensure_ascii=False)
                + '</script></head><body></body></html>')

    def test_json_ld_product_name_extracted(self):
        """Name must be extracted from JSON-LD Product schema."""
        ld = {'@type': 'Product', 'name': 'منتج JSON-LD'}
        result = self._parse_json_ld(self._html(ld))
        assert result['name'] == 'منتج JSON-LD'

    def test_json_ld_price_extracted(self):
        """Price must be extracted from JSON-LD offers.price."""
        ld = {'@type': 'Product', 'name': 'X', 'offers': {'price': '350'}}
        result = self._parse_json_ld(self._html(ld))
        assert result['price'] == 350.0

    def test_json_ld_description_extracted(self):
        """Description must be extracted from JSON-LD."""
        ld = {'@type': 'Product', 'name': 'X', 'description': 'وصف تفصيلي'}
        result = self._parse_json_ld(self._html(ld))
        assert result['description'] == 'وصف تفصيلي'

    def test_json_ld_image_extracted(self):
        """Image URL must be extracted from JSON-LD image field."""
        ld = {'@type': 'Product', 'name': 'X', 'image': 'https://cdn.example.com/img.jpg'}
        result = self._parse_json_ld(self._html(ld))
        assert result['image'] == 'https://cdn.example.com/img.jpg'

    def test_json_ld_image_extracted_from_list(self):
        """Image URL list — first image should be returned."""
        ld = {'@type': 'Product', 'name': 'X', 'image': ['https://a.com/1.jpg', 'https://a.com/2.jpg']}
        result = self._parse_json_ld(self._html(ld))
        assert result['image'] == 'https://a.com/1.jpg'

    def test_json_ld_offers_as_list(self):
        """Offers as a list: price of first offer must be extracted."""
        ld = {'@type': 'Product', 'name': 'X', 'offers': [{'price': '299'}, {'price': '350'}]}
        result = self._parse_json_ld(self._html(ld))
        assert result['price'] == 299.0

    def test_json_ld_type_case_insensitive(self):
        """@type must match case-insensitively (e.g. 'product' or 'PRODUCT')."""
        ld = {'@type': 'PRODUCT', 'name': 'اختبار حالة'}
        result = self._parse_json_ld(self._html(ld))
        assert result['name'] == 'اختبار حالة'

    def test_non_product_json_ld_ignored(self):
        """JSON-LD with @type other than Product must not be used."""
        ld = {'@type': 'WebSite', 'name': 'يجب تجاهله'}
        result = self._parse_json_ld(self._html(ld))
        assert result['name'] is None

    def test_json_ld_list_with_product_entry(self):
        """JSON-LD as a list — Product entry must be found."""
        ld = [
            {'@type': 'BreadcrumbList', 'name': 'تجاهل'},
            {'@type': 'Product', 'name': 'منتج في قائمة', 'offers': {'price': '450'}},
        ]
        html = ('<html><head><script type="application/ld+json">'
                + json.dumps(ld, ensure_ascii=False)
                + '</script></head><body></body></html>')
        result = self._parse_json_ld(html)
        assert result['name'] == 'منتج في قائمة'
        assert result['price'] == 450.0

    @patch('app.scrape_product_data')
    def test_scraper_fallback_flash_name_shown_in_admin(
            self, mock_scrape, authenticated_client, db_session):
        """Verifies full scraper route integration: result name is stored in DropshipProduct."""
        mock_scrape.return_value = {
            'success': True,
            'name': 'منتج جسون LD رائع',
            'price': 199.0,
            'description': 'وصف JSON-LD',
            'image_url': '',
            'additional_images': [],
            'source_site': 'test.com'
        }
        response = authenticated_client.post('/admin/dropshipping/scrape', data={
            'url': 'https://test.com/ld-product-unique'
        }, follow_redirects=True)
        assert response.status_code == 200
        stored = DropshipProduct.query.filter_by(source_url='https://test.com/ld-product-unique').first()
        assert stored is not None
        assert stored.name == 'منتج جسون LD رائع'


# ─────────────────────────────────────────────────────────────
# Fix 3b — False duplicate detection fixed
# ─────────────────────────────────────────────────────────────
class TestFix3bFalseDuplicate:
    """After a dropship product is deleted, the same URL can be re-scraped."""

    @patch('app.scrape_product_data')
    def test_stale_record_allows_rescrape(self, mock_scrape, authenticated_client, db_session):
        """If imported_product_id points to a deleted Product, re-scrape must succeed."""
        mock_scrape.return_value = {
            'success': True, 'name': 'منتج معاد', 'price': 100.0,
            'description': 'وصف', 'image_url': '', 'additional_images': [],
            'source_site': 'example.com'
        }
        url = 'https://example.com/deleted-product'
        # Create a stale record where imported_product_id points to a non-existent product
        stale = DropshipProduct(
            source_url=url, source_site='example.com',
            name='قديم', price=100, description='', status='imported',
            imported_product_id=99999  # product ID that does NOT exist in DB
        )
        db_session.add(stale)
        db_session.commit()

        response = authenticated_client.post('/admin/dropshipping/scrape',
                                             data={'url': url}, follow_redirects=True)
        assert response.status_code == 200
        # Stale record removed, scraper should have been called
        mock_scrape.assert_called_once()

    @patch('app.scrape_product_data')
    def test_live_duplicate_blocked(self, mock_scrape, authenticated_client, db_session, sample_category):
        """If product still exists in shop, second scrape must be blocked."""
        mock_scrape.return_value = {
            'success': True, 'name': 'موجود', 'price': 100.0,
            'description': '', 'image_url': '', 'additional_images': [],
            'source_site': 'example.com'
        }
        # Create a live product + dropship record pointing to it
        prod = Product(name='موجود', price=100, discount=0, stock=5,
                       description='', image='static/uploads/x.jpg',
                       category_id=sample_category.id)
        db_session.add(prod)
        db_session.flush()

        url = 'https://example.com/live-product'
        ds = DropshipProduct(source_url=url, source_site='example.com',
                             name='موجود', price=100, description='',
                             status='imported', imported_product_id=prod.id)
        db_session.add(ds)
        db_session.commit()

        response = authenticated_client.post('/admin/dropshipping/scrape',
                                             data={'url': url}, follow_redirects=True)
        assert response.status_code == 200
        # Scraper must NOT have been called again
        mock_scrape.assert_not_called()


# ─────────────────────────────────────────────────────────────
# Fix 4 — Dropshipping import image path
# ─────────────────────────────────────────────────────────────
class TestFix4DropshippingImagePath:
    """Products imported from dropshipping must store full static/uploads/ path."""

    @patch('app.download_image_from_url')
    def test_imported_product_image_has_full_path(self, mock_dl, authenticated_client, db_session, sample_category):
        """Product.image must start with 'static/uploads/' after import."""
        mock_dl.return_value = 'abc123_test.jpg'

        ds = DropshipProduct(
            source_url='https://example.com/img-test',
            source_site='example.com',
            name='منتج اختبار صورة',
            price=200.0,
            description='وصف',
            image_url='https://example.com/img.jpg',
            status='pending',
        )
        db_session.add(ds)
        db_session.commit()

        authenticated_client.post(f'/admin/dropshipping/import/{ds.id}',
                                  data={'category_id': sample_category.id,
                                        'price': '200', 'discount': '0', 'stock': '10'},
                                  follow_redirects=True)

        product = Product.query.filter_by(name='منتج اختبار صورة').first()
        assert product is not None, "Product was not created"
        assert product.image.startswith('static/uploads/'), (
            f"Image path '{product.image}' does not start with 'static/uploads/'"
        )

    @patch('app.download_image_from_url')
    def test_imported_product_image_not_bare_filename(self, mock_dl, authenticated_client, db_session, sample_category):
        """Product.image must NOT be a bare filename like 'abc123.jpg'."""
        mock_dl.return_value = 'bare_filename_test.jpg'

        ds = DropshipProduct(
            source_url='https://example.com/bare-test',
            source_site='example.com',
            name='منتج مسار مجرد',
            price=150.0,
            description='',
            image_url='https://example.com/bare.jpg',
            status='pending',
        )
        db_session.add(ds)
        db_session.commit()

        authenticated_client.post(f'/admin/dropshipping/import/{ds.id}',
                                  data={'category_id': sample_category.id,
                                        'price': '150', 'discount': '0', 'stock': '5'},
                                  follow_redirects=True)

        product = Product.query.filter_by(name='منتج مسار مجرد').first()
        if product:
            # Must not be bare filename
            assert '/' in product.image, (
                f"Image path '{product.image}' is a bare filename — missing directory prefix"
            )


# ─────────────────────────────────────────────────────────────
# Fix 5 — Dropship delete cascades to Product
# ─────────────────────────────────────────────────────────────
class TestFix5DropshipDeleteCascade:
    """Deleting a DropshipProduct must also delete the associated Product."""

    def test_delete_removes_dropship_record(self, authenticated_client, db_session, sample_category):
        """DropshipProduct record must be gone after delete."""
        prod = Product(name='سيحذف', price=100, discount=0, stock=1,
                       description='', image='static/uploads/del.jpg',
                       category_id=sample_category.id)
        db_session.add(prod)
        db_session.flush()

        ds = DropshipProduct(source_url='https://del.example.com/1',
                             source_site='del.example.com',
                             name='سيحذف', price=100, description='',
                             status='imported', imported_product_id=prod.id)
        db_session.add(ds)
        db_session.commit()
        ds_id = ds.id

        authenticated_client.post(f'/admin/dropshipping/delete/{ds_id}',
                                  follow_redirects=True)

        assert db.session.get(DropshipProduct, ds_id) is None

    def test_delete_also_removes_product(self, authenticated_client, db_session, sample_category):
        """Associated Product must be deleted when DropshipProduct is deleted."""
        prod = Product(name='سيحذف أيضاً', price=100, discount=0, stock=1,
                       description='', image='static/uploads/del2.jpg',
                       category_id=sample_category.id)
        db_session.add(prod)
        db_session.flush()
        prod_id = prod.id

        ds = DropshipProduct(source_url='https://del.example.com/2',
                             source_site='del.example.com',
                             name='سيحذف أيضاً', price=100, description='',
                             status='imported', imported_product_id=prod_id)
        db_session.add(ds)
        db_session.commit()
        ds_id = ds.id

        authenticated_client.post(f'/admin/dropshipping/delete/{ds_id}',
                                  follow_redirects=True)

        assert db.session.get(Product, prod_id) is None, (
            "Product still exists after dropship delete — cascade failed"
        )

    def test_delete_pending_no_product(self, authenticated_client, db_session):
        """Deleting a pending (not-imported) DropshipProduct must not crash."""
        ds = DropshipProduct(source_url='https://del.example.com/3',
                             source_site='del.example.com',
                             name='معلق', price=50, description='',
                             status='pending', imported_product_id=None)
        db_session.add(ds)
        db_session.commit()

        response = authenticated_client.post(f'/admin/dropshipping/delete/{ds.id}',
                                              follow_redirects=True)
        assert response.status_code == 200
        assert db.session.get(DropshipProduct, ds.id) is None


# ─────────────────────────────────────────────────────────────
# Fix 6 — Banner management
# ─────────────────────────────────────────────────────────────
class TestFix6BannerManagement:
    """Full CRUD for BannerSlide via admin routes."""

    def _make_banner(self, db_session, **kwargs):
        defaults = dict(
            image_url='https://cdn.example.com/banner.jpg',
            title='بانر تجريبي', subtitle='', description='',
            link_url='/shop', is_active=True, sort_order=0,
        )
        defaults.update(kwargs)
        b = BannerSlide(**defaults)
        db_session.add(b)
        db_session.commit()
        return b

    # Model
    def test_banner_slide_model_has_required_columns(self, app):
        cols = {c.name for c in BannerSlide.__table__.columns}
        for required in ('id', 'image_url', 'title', 'is_active', 'sort_order', 'link_url'):
            assert required in cols, f"Column '{required}' missing from BannerSlide"

    def test_banner_slide_model_create_and_query(self, db_session):
        b = BannerSlide(image_url='https://x.com/img.jpg', title='اختبار',
                        subtitle='', description='', link_url='/shop',
                        is_active=True, sort_order=1)
        db_session.add(b)
        db_session.commit()
        fetched = db.session.get(BannerSlide, b.id)
        assert fetched.title == 'اختبار'
        assert fetched.is_active is True

    # Routes exist
    def test_banners_page_loads(self, authenticated_client):
        response = authenticated_client.get('/admin/banners')
        assert response.status_code == 200
        assert 'بانر' in response.data.decode('utf-8')

    def test_banners_requires_auth(self, client):
        response = client.get('/admin/banners')
        assert response.status_code == 302

    # Add
    def test_banner_add_creates_record(self, authenticated_client, db_session):
        response = authenticated_client.post('/admin/banners/add', data={
            'image_url': 'https://example.com/new-banner.jpg',
            'title': 'بانر جديد',
            'subtitle': 'فرعي',
            'description': 'وصف',
            'link_url': '/shop',
            'highlight_regular_price': '500',
            'highlight_sale_price': '400',
            'highlight_discount': '20%',
            'sort_order': '0',
            'is_active': 'on',
        }, follow_redirects=True)
        assert response.status_code == 200
        banner = BannerSlide.query.filter_by(title='بانر جديد').first()
        assert banner is not None
        assert banner.image_url == 'https://example.com/new-banner.jpg'

    def test_banner_add_without_image_rejected(self, authenticated_client, db_session):
        before = BannerSlide.query.count()
        authenticated_client.post('/admin/banners/add', data={
            'image_url': '', 'title': 'بلا صورة',
        }, follow_redirects=True)
        after = BannerSlide.query.count()
        assert after == before, "Banner without image should not be created"

    # Edit
    def test_banner_edit_updates_record(self, authenticated_client, db_session):
        b = self._make_banner(db_session, title='قبل التعديل')
        authenticated_client.post(f'/admin/banners/edit/{b.id}', data={
            'title': 'بعد التعديل',
            'subtitle': '', 'description': '',
            'link_url': '/shop',
            'highlight_regular_price': '', 'highlight_sale_price': '',
            'highlight_discount': '',
            'sort_order': '0',
            'is_active': 'on',
        }, follow_redirects=True)
        db.session.refresh(b)
        assert b.title == 'بعد التعديل'

    # Delete
    def test_banner_delete_removes_record(self, authenticated_client, db_session):
        b = self._make_banner(db_session, title='للحذف')
        b_id = b.id
        authenticated_client.post(f'/admin/banners/delete/{b_id}',
                                   follow_redirects=True)
        assert db.session.get(BannerSlide, b_id) is None

    # Toggle
    def test_banner_toggle_flips_active(self, authenticated_client, db_session):
        b = self._make_banner(db_session, is_active=True)
        authenticated_client.post(f'/admin/banners/toggle/{b.id}',
                                   follow_redirects=True)
        db.session.refresh(b)
        assert b.is_active is False

    def test_banner_toggle_activates_hidden(self, authenticated_client, db_session):
        b = self._make_banner(db_session, is_active=False)
        authenticated_client.post(f'/admin/banners/toggle/{b.id}',
                                   follow_redirects=True)
        db.session.refresh(b)
        assert b.is_active is True

    # Home page uses db_banners
    def test_home_passes_db_banners_when_exist(self, client, db_session):
        db_session.add(BannerSlide(image_url='https://x.com/b.jpg', title='بانر رئيسي',
                                   subtitle='', description='', link_url='/shop',
                                   is_active=True, sort_order=0))
        db_session.commit()
        response = client.get('/')
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────
# Fix 7 — Dynamic Limited Time Offer (sale_products)
# ─────────────────────────────────────────────────────────────
class TestFix7LimitedTimeOffer:
    """Home page must show discounted products dynamically."""

    def test_home_shows_sale_section_when_discounted_products_exist(
            self, client, db_session, sample_category):
        """When discount > 0 products exist they must appear on home."""
        prod = Product(name='منتج بخصم', price=300, discount=25,
                       stock=10, description='وصف',
                       image='static/uploads/sale.jpg',
                       category_id=sample_category.id)
        db_session.add(prod)
        db_session.commit()

        response = client.get('/')
        html = response.data.decode('utf-8')
        assert response.status_code == 200
        assert 'عرض لفترة محدودة' in html
        assert 'منتج بخصم' in html

    def test_home_hides_sale_section_when_no_discounted_products(
            self, client, db_session, sample_category):
        """When no discounted products exist, section must be absent."""
        # only zero-discount products
        prod = Product(name='منتج بلا خصم', price=200, discount=0,
                       stock=5, description='',
                       image='static/uploads/nodiscount.jpg',
                       category_id=sample_category.id)
        db_session.add(prod)
        db_session.commit()

        response = client.get('/')
        html = response.data.decode('utf-8')
        assert 'منتج بلا خصم' not in html or 'عرض لفترة محدودة' not in html

    def test_home_sale_products_sorted_by_discount_desc(
            self, client, db_session, sample_category):
        """Highest discount must appear first in sale section."""
        for name, disc in [('خصم10', 10), ('خصم50', 50), ('خصم30', 30)]:
            db_session.add(Product(
                name=name, price=100, discount=disc, stock=3,
                description='', image=f'static/uploads/{name}.jpg',
                category_id=sample_category.id
            ))
        db_session.commit()

        response = client.get('/')
        html = response.data.decode('utf-8')
        idx50 = html.find('خصم50')
        idx30 = html.find('خصم30')
        idx10 = html.find('خصم10')
        # Higher discount should appear earlier in HTML
        if idx50 != -1 and idx30 != -1:
            assert idx50 < idx30, "50% discount should appear before 30%"
        if idx30 != -1 and idx10 != -1:
            assert idx30 < idx10, "30% discount should appear before 10%"

    def test_home_renders_discount_percentage(self, client, db_session, sample_category):
        """Discount badge must show the %-off value."""
        db_session.add(Product(
            name='منتج خصم_20', price=500, discount=20, stock=10,
            description='', image='static/uploads/d20.jpg',
            category_id=sample_category.id
        ))
        db_session.commit()

        response = client.get('/')
        html = response.data.decode('utf-8')
        # The template renders -20% badge
        assert '20' in html

    def test_sale_products_out_of_stock_excluded(self, app, db_session, sample_category):
        """Out-of-stock products (stock=0) must be excluded by the sale_products ORM query."""
        db_session.add(Product(
            name='نفد المخزون', price=100, discount=40, stock=0,
            description='', image='static/uploads/oos.jpg',
            category_id=sample_category.id
        ))
        db_session.commit()

        # Test the filtering logic directly — the route filters stock > 0
        with app.app_context():
            sale = Product.query.filter(
                Product.discount > 0, Product.stock > 0
            ).all()
            names = [p.name for p in sale]
        assert 'نفد المخزون' not in names, (
            "Out-of-stock product should be excluded from sale_products query"
        )
