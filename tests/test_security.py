import pathlib
import os

from werkzeug.security import generate_password_hash

from app import app, db, Admins, Gusts, Category, Product, Cart, City, ShippingCost, Order



def setup_module(module):
    # Conftest's session-scoped 'app' fixture manages the database lifecycle.
    # db.create_all() is idempotent: safe to call again if tables already exist.
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    with app.app_context():
        db.create_all()


def teardown_module(module):
    pass



def test_admin_login_requires_csrf_token():
    with app.app_context():
        admin = Admins.query.filter_by(email="admin@test.com").first()
        if not admin:
            db.session.add(
                Admins(
                    name="Admin",
                    email="admin@test.com",
                    password=generate_password_hash("secret123"),
                )
            )
            db.session.commit()

    client = app.test_client()
    response = client.post(
        "/admin/login",
        data={"username": "admin@test.com", "password": "secret123"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)



def test_admin_login_with_valid_csrf_token_succeeds():
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_csrf_token"] = "test-token-123"

    response = client.post(
        "/admin/login",
        data={
            "username": "admin@test.com",
            "password": "secret123",
            "csrf_token": "test-token-123",
        },
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/admin" in response.headers.get("Location", "")



def test_payment_webhook_is_csrf_exempt_and_validates_payload():
    client = app.test_client()
    response = client.post("/payment/webhook", json={})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"



def test_no_legacy_query_get_usage_in_app_file():
    app_py = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    content = app_py.read_text(encoding="utf-8")
    assert ".query.get(" not in content


def _seed_checkout_data(session_id="test-session-checkout"):
    with app.app_context():
        guest = Gusts.query.filter_by(session=session_id).first()
        if not guest:
            guest = Gusts(session=session_id)
            db.session.add(guest)
            db.session.flush()

        category = Category.query.filter_by(name="Test Category").first()
        if not category:
            category = Category(name="Test Category")
            db.session.add(category)
            db.session.flush()

        product = Product.query.filter_by(name="Test Product").first()
        if not product:
            product = Product(
                name="Test Product",
                price=100.0,
                discount=0,
                stock=10,
                description="Test Description",
                image="/static/uploads/test.png",
                category_id=category.id,
            )
            db.session.add(product)
            db.session.flush()

        cart_item = Cart.query.filter_by(user_id=guest.id, product_id=product.id).first()
        if not cart_item:
            cart_item = Cart(user_id=guest.id, product_id=product.id, quantity=1)
            db.session.add(cart_item)

        city = City.query.filter_by(city_id="1").first()
        if not city:
            city = City(name="Test City", city_id="1")
            db.session.add(city)

        shipping = ShippingCost.query.filter_by(city_id=1).first()
        if not shipping:
            shipping = ShippingCost(city_id=1, price=20.0)
            db.session.add(shipping)

        db.session.commit()
        return guest.id


def test_checkout_page_loads_with_cart_items():
    session_id = "test-session-checkout-page"
    _seed_checkout_data(session_id=session_id)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["session"] = session_id
        sess["_csrf_token"] = "csrf-checkout-page"
        sess["cart_count"] = 1

    response = client.get("/checkout", follow_redirects=False)
    assert response.status_code == 200


def test_place_order_rejects_invalid_payment_method():
    session_id = "test-session-invalid-payment"
    _seed_checkout_data(session_id=session_id)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["session"] = session_id
        sess["_csrf_token"] = "csrf-invalid-payment"
        sess["cart_count"] = 1

    response = client.post(
        "/checkout/place_order",
        data={
            "csrf_token": "csrf-invalid-payment",
            "name": "Test User",
            "phone": "01000000000",
            "address": "Test Address",
            "city": "1",
            "zone_id": "10",
            "district_id": "20",
            "total": "120",
            "payment_method": "invalid-method",
        },
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/checkout" in response.headers.get("Location", "")


def test_place_order_cash_on_delivery_creates_order():
    session_id = "test-session-cod-order"
    _seed_checkout_data(session_id=session_id)

    with app.app_context():
        before_count = Order.query.count()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["session"] = session_id
        sess["_csrf_token"] = "csrf-cod-order"
        sess["cart_count"] = 1

    response = client.post(
        "/checkout/place_order",
        data={
            "csrf_token": "csrf-cod-order",
            "name": "Test COD",
            "phone": "01000000000",
            "address": "Test Address",
            "city": "1",
            "zone_id": "10",
            "district_id": "20",
            "total": "120",
            "payment_method": "cash_on_delivery",
        },
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    assert "/order_confirmation" in response.headers.get("Location", "")

    with app.app_context():
        after_count = Order.query.count()
        assert after_count == before_count + 1


def test_admin_orders_requires_admin_session():
    client = app.test_client()
    response = client.get('/admin/orders', follow_redirects=False)

    assert response.status_code in (301, 302)
    assert '/admin/login' in response.headers.get('Location', '')


def test_admin_delete_order_requires_csrf_token():
    session_id = 'test-session-admin-delete'
    _seed_checkout_data(session_id=session_id)

    with app.app_context():
        guest = Gusts.query.filter_by(session=session_id).first()
        order = Order(
            user_id=guest.id,
            name='Delete Test',
            email='delete@test.com',
            phone='01000000000',
            address='Delete Address',
            city='1',
            zone_id='10',
            district_id='20',
            cod_amount=100,
            payment_method='cash_on_delivery',
            status='pending',
        )
        db.session.add(order)
        db.session.commit()
        order_id = order.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['admin'] = 1

    response = client.post(f'/admin/delete_order/{order_id}', data={}, follow_redirects=False)
    assert response.status_code in (301, 302)


def test_api_cities_returns_json():
    _seed_checkout_data(session_id='test-session-api-cities')
    client = app.test_client()

    response = client.get('/api/cities')
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert 'city' in payload
    assert isinstance(payload['city'], list)


def test_api_shipping_cost_returns_expected_value():
    _seed_checkout_data(session_id='test-session-api-shipping')
    client = app.test_client()

    response = client.get('/api/shipping-cost?city_id=1')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'cost' in payload


def test_payment_webhook_rejects_invalid_secret_when_configured():
    previous_secret = os.environ.get('PAYMENT_WEBHOOK_SECRET')
    os.environ['PAYMENT_WEBHOOK_SECRET'] = 'secret-123'
    client = app.test_client()

    response = client.post(
        '/payment/webhook',
        json={'invoiceKey': 'x', 'status': 'paid'},
        headers={'X-Webhook-Secret': 'wrong-secret'},
    )

    assert response.status_code == 401
    payload = response.get_json()
    assert payload['status'] == 'error'

    if previous_secret is None:
        os.environ.pop('PAYMENT_WEBHOOK_SECRET', None)
    else:
        os.environ['PAYMENT_WEBHOOK_SECRET'] = previous_secret


def _seed_admin_order_for_updates(session_id='test-session-admin-updates'):
    _seed_checkout_data(session_id=session_id)
    with app.app_context():
        guest = Gusts.query.filter_by(session=session_id).first()
        order = Order(
            user_id=guest.id,
            name='Admin Update',
            email='admin-update@test.com',
            phone='01000000000',
            address='Admin Address',
            city='1',
            zone_id='10',
            district_id='20',
            cod_amount=150,
            payment_method='cash_on_delivery',
            status='pending',
            shipping_status='pending',
        )
        db.session.add(order)
        db.session.commit()
        return order.id


def test_admin_update_order_status_success():
    order_id = _seed_admin_order_for_updates('test-session-status-update')
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['admin'] = 1
        sess['_csrf_token'] = 'csrf-admin-status'

    response = client.post(
        f'/admin/order/{order_id}/update-status',
        data={'csrf_token': 'csrf-admin-status', 'status': 'completed'},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)

    with app.app_context():
        order = db.session.get(Order, order_id)
        assert order.status == 'completed'


def test_admin_update_shipping_status_success():
    order_id = _seed_admin_order_for_updates('test-session-shipping-update')
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['admin'] = 1
        sess['_csrf_token'] = 'csrf-admin-shipping'

    response = client.post(
        f'/admin/update_shipping_status/{order_id}',
        data={'csrf_token': 'csrf-admin-shipping', 'status': 'shipped'},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)

    with app.app_context():
        order = db.session.get(Order, order_id)
        assert order.shipping_status == 'shipped'


def test_admin_update_payment_method_success():
    order_id = _seed_admin_order_for_updates('test-session-payment-update')
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['admin'] = 1
        sess['_csrf_token'] = 'csrf-admin-payment'

    response = client.post(
        f'/admin/order/{order_id}/update-payment-method',
        data={'csrf_token': 'csrf-admin-payment', 'payment_method': 'visa'},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)

    with app.app_context():
        order = db.session.get(Order, order_id)
        assert order.payment_method == 'visa'
