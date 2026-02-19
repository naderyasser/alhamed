"""
Production readiness tests for alhamed e-commerce store.

Covers:
- Production configuration checks
- All public HTTP routes respond correctly
- Security basics (admin auth, CSRF exemptions)
- API contract (cities, shipping cost)
- End-to-end order placement flow (COD)
- Admin panel route coverage
- Error handling
"""
import json
import os
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db
from app import (
    Admins, Category, City, Gusts, Order, Product,
    ShippingCost, Cart,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_full_catalog(session):
    """Insert the minimum data needed for a complete checkout flow."""
    category = Category(name='Test Cat', description='Test')
    session.add(category)
    session.flush()

    product = Product(
        name='Test Product',
        price=100.0,
        discount=0.0,
        stock=10,
        description='Test',
        image='static/uploads/test.png',
        category_id=category.id,
    )
    session.add(product)
    session.flush()

    city = City(name='Cairo', city_id='99')
    session.add(city)
    session.flush()

    shipping = ShippingCost(city_id=99, price=25.0)
    session.add(shipping)
    session.flush()

    guest = Gusts(session='prod-test-session', name='Test User', phone='01000000000', address='Test Addr')
    session.add(guest)
    session.flush()

    cart = Cart(user_id=guest.id, product_id=product.id, quantity=1)
    session.add(cart)
    session.commit()

    return {'category': category, 'product': product, 'city': city, 'guest': guest}


# ---------------------------------------------------------------------------
# 1. Production configuration
# ---------------------------------------------------------------------------

class TestProductionConfig:
    """Verify settings expected of a production deployment."""

    def test_secret_key_is_set(self, app):
        """SECRET_KEY must be non-empty."""
        assert app.config.get('SECRET_KEY'), 'SECRET_KEY is not set'

    def test_secret_key_is_not_trivial(self, app):
        """SECRET_KEY must not be a common placeholder."""
        key = app.config.get('SECRET_KEY', '')
        bad_keys = {'secret', 'changeme', 'dev', 'development', 'insecure'}
        assert key.lower() not in bad_keys, f'SECRET_KEY looks like a placeholder: {key}'

    def test_upload_folder_configured(self, app):
        """UPLOAD_FOLDER must be configured."""
        assert app.config.get('UPLOAD_FOLDER'), 'UPLOAD_FOLDER is not configured'


# ---------------------------------------------------------------------------
# 2. Public shop routes
# ---------------------------------------------------------------------------

class TestPublicRoutes:
    """All public-facing routes should respond without 5xx errors."""

    def test_home_page(self, client):
        response = client.get('/')
        assert response.status_code == 200

    def test_shop_page(self, client):
        response = client.get('/shop')
        assert response.status_code == 200

    def test_product_detail_valid(self, client, sample_product):
        response = client.get(f'/{sample_product.id}')
        assert response.status_code == 200

    def test_product_detail_not_found(self, client):
        response = client.get('/999999')
        assert response.status_code == 404

    def test_cart_page_empty(self, client):
        response = client.get('/cart')
        assert response.status_code == 200

    def test_checkout_redirects_when_cart_empty(self, client):
        """Checkout without cart items should redirect."""
        response = client.get('/checkout', follow_redirects=False)
        assert response.status_code == 302

    def test_return_policy_page(self, client):
        response = client.get('/return-policy')
        assert response.status_code == 200

    def test_about_page(self, client):
        response = client.get('/about')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 3. Admin route protection
# ---------------------------------------------------------------------------

class TestAdminProtection:
    """Admin routes must redirect unauthenticated users to login."""

    PROTECTED = [
        '/admin/',
        '/admin/orders',
        '/admin/products',
        '/admin/categories',
        '/admin/dropshipping',
        '/admin/api/recent-orders',
    ]

    @pytest.mark.parametrize('path', PROTECTED)
    def test_admin_route_requires_auth(self, client, path):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        location = response.headers.get('Location', '')
        assert 'login' in location.lower(), f'{path} did not redirect to login'

    def test_admin_login_page_loads(self, client):
        response = client.get('/admin/login')
        assert response.status_code == 200

    def test_admin_login_wrong_password(self, client, sample_admin):
        response = client.post(
            '/admin/login',
            data={'username': sample_admin.email, 'password': 'WRONG'},
            follow_redirects=False,
        )
        # Should stay on login page or redirect back
        assert response.status_code in (200, 302)
        if response.status_code == 302:
            assert '/admin/login' in response.headers.get('Location', '')

    def test_admin_login_correct_password(self, client, sample_admin):
        from werkzeug.security import check_password_hash
        response = client.post(
            '/admin/login',
            data={'username': sample_admin.email, 'password': 'admin123'},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert '/admin' in response.headers.get('Location', '')

    def test_dashboard_accessible_when_authenticated(self, authenticated_client):
        response = authenticated_client.get('/admin/')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 4. API endpoints
# ---------------------------------------------------------------------------

class TestAPIEndpoints:
    """API contracts should be stable."""

    def test_cities_api_returns_json(self, client, db_session):
        city = City(name='Cairo', city_id='100')
        db_session.add(city)
        db_session.commit()

        response = client.get('/api/cities')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        assert 'city' in data
        assert isinstance(data['city'], list)

    def test_shipping_cost_valid_city(self, client, db_session):
        city = City(name='Alex', city_id='200')
        db_session.add(city)
        db_session.flush()
        db_session.add(ShippingCost(city_id=200, price=30.0))
        db_session.commit()

        response = client.get('/api/shipping-cost?city_id=200')
        assert response.status_code == 200
        data = response.get_json()
        assert 'cost' in data

    def test_shipping_cost_unknown_city_returns_404(self, client):
        response = client.get('/api/shipping-cost?city_id=999999')
        assert response.status_code == 404

    def test_recent_orders_api_authenticated(self, authenticated_client, sample_order):
        response = authenticated_client.get('/admin/api/recent-orders')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'orders' in data


# ---------------------------------------------------------------------------
# 5. Cart operations
# ---------------------------------------------------------------------------

class TestCartOperations:
    """Cart add/remove/view should work correctly."""

    def test_add_product_to_cart(self, client, sample_product, sample_guest):
        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session
        response = client.post(f'/cart/add/{sample_product.id}', follow_redirects=False)
        assert response.status_code in (200, 302)

    def test_view_cart_with_item(self, client, db_session, sample_product, sample_guest):
        cart = Cart(user_id=sample_guest.id, product_id=sample_product.id, quantity=1)
        db_session.add(cart)
        db_session.commit()

        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session

        response = client.get('/cart')
        assert response.status_code == 200

    def test_remove_product_from_cart(self, client, db_session, sample_product, sample_guest):
        cart = Cart(user_id=sample_guest.id, product_id=sample_product.id, quantity=1)
        db_session.add(cart)
        db_session.commit()

        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session

        response = client.get(f'/cart/remove/{sample_product.id}', follow_redirects=False)
        assert response.status_code in (200, 302)


# ---------------------------------------------------------------------------
# 6. End-to-end order placement (COD)
# ---------------------------------------------------------------------------

class TestOrderPlacementCOD:
    """Full checkout flow from cart to confirmed order."""

    def test_place_cod_order_creates_db_record(self, client, db_session):
        objects = _create_full_catalog(db_session)
        guest = objects['guest']
        city = objects['city']

        before = db_session.query(Order).count()

        with client.session_transaction() as sess:
            sess['session'] = guest.session
            sess['cart_count'] = 1

        response = client.post(
            '/checkout/place_order',
            data={
                'name': 'End-to-End User',
                'phone': '01000000000',
                'address': '123 Test St',
                'city': city.city_id,
                'zone_id': '10',
                'district_id': '20',
                'total': '125',
                'payment_method': 'cash_on_delivery',
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert 'order_confirmation' in response.headers.get('Location', '')

        after = db_session.query(Order).count()
        assert after == before + 1

    def test_place_order_with_invalid_payment_method_redirects(self, client, db_session):
        objects = _create_full_catalog(db_session)
        guest = objects['guest']
        city = objects['city']

        with client.session_transaction() as sess:
            sess['session'] = guest.session
            sess['cart_count'] = 1

        response = client.post(
            '/checkout/place_order',
            data={
                'name': 'Test',
                'phone': '01000000000',
                'address': 'Addr',
                'city': city.city_id,
                'zone_id': '10',
                'district_id': '20',
                'total': '125',
                'payment_method': 'invalid_method',
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert '/checkout' in response.headers.get('Location', '')


# ---------------------------------------------------------------------------
# 7. Payment webhook
# ---------------------------------------------------------------------------

class TestPaymentWebhook:
    """Webhook must be CSRF-exempt and validate its payload."""

    def test_webhook_empty_body_returns_400(self, client):
        response = client.post('/payment/webhook', json={})
        assert response.status_code == 400

    def test_webhook_rejects_wrong_secret(self, client):
        prev = os.environ.get('PAYMENT_WEBHOOK_SECRET')
        os.environ['PAYMENT_WEBHOOK_SECRET'] = 'correct-secret'
        try:
            response = client.post(
                '/payment/webhook',
                json={'invoiceKey': 'x', 'status': 'paid'},
                headers={'X-Webhook-Secret': 'wrong-secret'},
            )
            assert response.status_code == 401
        finally:
            if prev is None:
                os.environ.pop('PAYMENT_WEBHOOK_SECRET', None)
            else:
                os.environ['PAYMENT_WEBHOOK_SECRET'] = prev


# ---------------------------------------------------------------------------
# 8. Admin product management
# ---------------------------------------------------------------------------

class TestAdminProductManagement:
    """Admin can create, edit, and delete products."""

    def test_add_product_missing_name_does_not_crash(self, authenticated_client, sample_category):
        response = authenticated_client.post(
            '/admin/add_product',
            data={
                'name': '',
                'price': '500',
                'quantity': '10',
                'category': str(sample_category.id),
            },
            follow_redirects=False,
        )
        assert response.status_code in (200, 302, 400)

    def test_delete_product_success(self, authenticated_client, sample_product):
        response = authenticated_client.post(
            f'/admin/delete_product/{sample_product.id}',
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_admin_products_page_loads(self, authenticated_client, sample_product):
        response = authenticated_client.get('/admin/products')
        assert response.status_code == 200
        assert sample_product.name.encode() in response.data


# ---------------------------------------------------------------------------
# 9. Admin order management
# ---------------------------------------------------------------------------

class TestAdminOrderManagement:
    """Admin can read and update orders."""

    def test_orders_page_loads(self, authenticated_client, sample_order):
        response = authenticated_client.get('/admin/orders')
        assert response.status_code == 200

    def test_update_order_status(self, authenticated_client, sample_order, db_session):
        response = authenticated_client.post(
            f'/admin/order/{sample_order.id}/update-status',
            data={'status': 'completed'},
            follow_redirects=False,
        )
        assert response.status_code == 302

        db_session.expire(sample_order)
        assert sample_order.status == 'completed'

    def test_update_shipping_status(self, authenticated_client, sample_order, db_session):
        response = authenticated_client.post(
            f'/admin/update_shipping_status/{sample_order.id}',
            data={'status': 'shipped'},
            follow_redirects=False,
        )
        assert response.status_code == 302

        db_session.expire(sample_order)
        assert sample_order.shipping_status == 'shipped'
