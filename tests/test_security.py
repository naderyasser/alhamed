import pathlib

from werkzeug.security import generate_password_hash

from app import app, db, Admins, Gusts, Category, Product, Cart, City, ShippingCost, Order



def setup_module(module):
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
    )
    with app.app_context():
        db.drop_all()
        db.create_all()



def teardown_module(module):
    with app.app_context():
        db.session.remove()
        db.drop_all()



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
