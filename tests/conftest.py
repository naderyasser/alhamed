"""
Pytest configuration and fixtures for testing
"""
import pytest
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app, db
from app import (
    Category, Product, AdditionalImage, AdditionalData, 
    Cart, Order, OrderItem, Admins, Gusts, DropshipProduct
)

@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    flask_app.config['UPLOAD_FOLDER'] = 'static/uploads'
    
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture(scope='function')
def db_session(app):
    """Create database session for testing"""
    with app.app_context():
        yield db.session
        db.session.rollback()
        # Clean up all tables
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()

@pytest.fixture
def sample_category(db_session):
    """Create a sample category"""
    category = Category(name='إلكترونيات', description='أجهزة إلكترونية')
    db_session.add(category)
    db_session.commit()
    return category

@pytest.fixture
def sample_product(db_session, sample_category):
    """Create a sample product"""
    product = Product(
        name='لابتوب Dell',
        price=15000.0,
        discount=10.0,
        stock=50,
        description='لابتوب Dell قوي ومناسب للعمل',
        image='static/uploads/laptop.jpg',
        category_id=sample_category.id
    )
    db_session.add(product)
    db_session.commit()
    return product

@pytest.fixture
def sample_admin(db_session):
    """Create a sample admin user"""
    from werkzeug.security import generate_password_hash
    admin = Admins(
        name='Admin User',
        email='admin@example.com',
        password=generate_password_hash('admin123')
    )
    db_session.add(admin)
    db_session.commit()
    return admin

@pytest.fixture
def sample_guest(db_session):
    """Create a sample guest user"""
    guest = Gusts(
        session='test-session-123',
        name='أحمد محمد',
        phone='01234567890',
        address='القاهرة، مصر'
    )
    db_session.add(guest)
    db_session.commit()
    return guest

@pytest.fixture
def sample_order(db_session, sample_guest, sample_product):
    """Create a sample order"""
    order = Order(
        user_id=sample_guest.id,
        name=sample_guest.name,
        email='ahmad@example.com',
        phone=sample_guest.phone,
        address=sample_guest.address,
        status='pending',
        cod_amount=13500.0,
        payment_method='cod',
        shipping_status='pending'
    )
    db_session.add(order)
    db_session.commit()
    
    order_item = OrderItem(
        order_id=order.id,
        product_id=sample_product.id,
        quantity=1
    )
    db_session.add(order_item)
    db_session.commit()
    
    return order

@pytest.fixture
def sample_dropship_product(db_session):
    """Create a sample dropship product"""
    dropship = DropshipProduct(
        source_url='https://example.com/product/123',
        source_site='example.com',
        name='منتج مستورد',
        price=500.0,
        description='منتج للدروب شوبينج',
        image_url='https://example.com/image.jpg',
        status='pending'
    )
    db_session.add(dropship)
    db_session.commit()
    return dropship

@pytest.fixture
def authenticated_client(client, sample_admin, app):
    """Create an authenticated admin client"""
    with client.session_transaction() as session:
        session['admin'] = sample_admin.id
    return client

@pytest.fixture
def guest_session(client):
    """Create a guest session"""
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client
