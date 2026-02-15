import pathlib

from werkzeug.security import generate_password_hash

from app import app, db, Admins



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
