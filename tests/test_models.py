"""
Tests for database models
"""
import pytest
from datetime import datetime
from app import Category, Product, AdditionalImage, Cart, Order, OrderItem, Admins, Gusts, DropshipProduct

class TestCategory:
    """Tests for Category model"""
    
    def test_create_category(self, db_session):
        """Test creating a category"""
        category = Category(name='أزياء', description='ملابس وأحذية')
        db_session.add(category)
        db_session.commit()
        
        assert category.id is not None
        assert category.name == 'أزياء'
        assert category.description == 'ملابس وأحذية'
        assert category.created_at is not None
    
    def test_category_products_relationship(self, db_session, sample_category):
        """Test category-products relationship"""
        product = Product(
            name='قميص',
            price=200.0,
            discount=0,
            stock=10,
            description='قميص قطني',
            image='shirt.jpg',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()
        
        assert len(sample_category.products) == 1
        assert sample_category.products[0].name == 'قميص'

class TestProduct:
    """Tests for Product model"""
    
    def test_create_product(self, db_session, sample_category):
        """Test creating a product"""
        product = Product(
            name='هاتف Samsung',
            price=8000.0,
            discount=15.0,
            stock=30,
            description='هاتف ذكي حديث',
            image='phone.jpg',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()
        
        assert product.id is not None
        assert product.name == 'هاتف Samsung'
        assert product.price == 8000.0
        assert product.discount == 15.0
        assert product.stock == 30
        assert product.views == 0
    
    def test_product_category_relationship(self, db_session, sample_product, sample_category):
        """Test product-category relationship"""
        assert sample_product.category.id == sample_category.id
        assert sample_product.category.name == sample_category.name
    
    def test_product_additional_images(self, db_session, sample_product):
        """Test product additional images"""
        img1 = AdditionalImage(image='image1.jpg', product_id=sample_product.id)
        img2 = AdditionalImage(image='image2.jpg', product_id=sample_product.id)
        db_session.add_all([img1, img2])
        db_session.commit()
        
        assert len(sample_product.additional_images) == 2

class TestCart:
    """Tests for Cart model"""
    
    def test_create_cart_item(self, db_session, sample_guest, sample_product):
        """Test creating a cart item"""
        cart_item = Cart(
            user_id=sample_guest.id,
            product_id=sample_product.id,
            quantity=2
        )
        db_session.add(cart_item)
        db_session.commit()
        
        assert cart_item.id is not None
        assert cart_item.quantity == 2
        assert cart_item.product.name == sample_product.name

class TestOrder:
    """Tests for Order model"""
    
    def test_create_order(self, db_session, sample_guest):
        """Test creating an order"""
        order = Order(
            user_id=sample_guest.id,
            name='محمد علي',
            email='mohamed@example.com',
            phone='01111111111',
            address='الإسكندرية',
            status='pending',
            cod_amount=1000.0,
            payment_method='cod',
            shipping_status='pending'
        )
        db_session.add(order)
        db_session.commit()
        
        assert order.id is not None
        assert order.name == 'محمد علي'
        assert order.shipping_status == 'pending'
        assert order.payment_status == 'pending'
    
    def test_order_items(self, db_session, sample_order, sample_product):
        """Test order items relationship"""
        items = OrderItem.query.filter_by(order_id=sample_order.id).all()
        assert len(items) == 1
        assert items[0].product_id == sample_product.id

class TestAdmins:
    """Tests for Admins model"""
    
    def test_create_admin(self, db_session):
        """Test creating an admin"""
        from werkzeug.security import generate_password_hash
        admin = Admins(
            name='Super Admin',
            email='superadmin@example.com',
            password=generate_password_hash('secure123')
        )
        db_session.add(admin)
        db_session.commit()
        
        assert admin.id is not None
        assert admin.email == 'superadmin@example.com'
    
    def test_admin_password_hash(self, db_session, sample_admin):
        """Test admin password is hashed"""
        from werkzeug.security import check_password_hash
        assert check_password_hash(sample_admin.password, 'admin123')
        assert sample_admin.password != 'admin123'

class TestDropshipProduct:
    """Tests for DropshipProduct model"""
    
    def test_create_dropship_product(self, db_session):
        """Test creating a dropship product"""
        dropship = DropshipProduct(
            source_url='https://amazon.com/product/abc',
            source_site='amazon.com',
            name='منتج أمازون',
            price=350.0,
            description='منتج مستورد من أمازون',
            image_url='https://amazon.com/img.jpg',
            status='pending'
        )
        db_session.add(dropship)
        db_session.commit()
        
        assert dropship.id is not None
        assert dropship.status == 'pending'
        assert dropship.source_site == 'amazon.com'
    
    def test_dropship_status_change(self, db_session, sample_dropship_product, sample_product):
        """Test changing dropship status after import"""
        sample_dropship_product.status = 'imported'
        sample_dropship_product.imported_product_id = sample_product.id
        db_session.commit()
        
        assert sample_dropship_product.status == 'imported'
        assert sample_dropship_product.imported_product_id == sample_product.id
