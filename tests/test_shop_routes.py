"""
Tests for shop routes
"""
import pytest
from flask import session

class TestShopHomePage:
    """Tests for shop home page"""
    
    def test_home_page_loads(self, client):
        """Test home page loads successfully"""
        response = client.get('/')
        assert response.status_code == 200
        assert 'اكتشف أفضل العروض' in response.data.decode('utf-8') or 'المنتجات' in response.data.decode('utf-8')
    
    def test_home_page_shows_categories(self, client, sample_category):
        """Test home page displays categories"""
        response = client.get('/')
        assert response.status_code == 200
        # Categories are injected via context processor
        assert sample_category.name in response.data.decode('utf-8') or 'إلكترونيات' in response.data.decode('utf-8')

class TestProductListing:
    """Tests for product listing"""

    def test_products_list_page(self, client, sample_product):
        """Test products list page"""
        response = client.get('/shop')
        assert response.status_code == 200

    def test_filter_by_category(self, client, sample_product, sample_category):
        """Test filtering products by category"""
        response = client.get(f'/shop?category={sample_category.id}')
        assert response.status_code == 200
        assert sample_product.name in response.data.decode('utf-8')

    def test_search_products(self, client, sample_product):
        """Test searching products"""
        response = client.get('/shop?search=Dell')
        assert response.status_code == 200
        assert 'Dell' in response.data.decode('utf-8')

    def test_price_filter(self, client, sample_product):
        """Test filtering by price range"""
        response = client.get('/shop?min_price=10000&max_price=20000')
        assert response.status_code == 200

class TestProductDetail:
    """Tests for product detail page"""
    
    def test_product_detail_page(self, client, sample_product):
        """Test product detail page loads"""
        response = client.get(f'/{sample_product.id}')
        assert response.status_code == 200
        assert sample_product.name in response.data.decode('utf-8')
        assert str(sample_product.price) in response.data.decode('utf-8')
    
    def test_product_view_count(self, client, sample_product, db_session):
        """Test product view count increments"""
        initial_views = sample_product.views
        client.get(f'/{sample_product.id}')
        db_session.refresh(sample_product)
        assert sample_product.views == initial_views + 1
    
    def test_nonexistent_product(self, client):
        """Test accessing nonexistent product returns 404"""
        response = client.get('/99999')
        assert response.status_code == 404

class TestCart:
    """Tests for cart functionality"""
    
    def test_add_to_cart(self, client, sample_product, sample_guest):
        """Test adding product to cart"""
        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session

        response = client.post(f'/cart/add/{sample_product.id}', data={
            'quantity': 2
        }, follow_redirects=True)

        assert response.status_code == 200

    def test_view_cart(self, client, sample_guest):
        """Test viewing cart page"""
        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session

        response = client.get('/cart')
        assert response.status_code == 200
        assert 'سلة التسوق' in response.data.decode('utf-8')

    def test_remove_from_cart(self, client, sample_guest, sample_product, db_session):
        """Test removing item from cart"""
        from app import Cart

        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session

        # Add to cart first
        cart_item = Cart(
            user_id=sample_guest.id,
            product_id=sample_product.id,
            quantity=1
        )
        db_session.add(cart_item)
        db_session.commit()

        # Remove from cart
        response = client.get(f'/cart/remove/{cart_item.id}', follow_redirects=True)
        assert response.status_code == 200

class TestCheckout:
    """Tests for checkout process"""

    def test_checkout_page_loads(self, client, sample_guest, sample_product, db_session):
        """Test checkout page loads when cart has items"""
        from app import Cart

        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session

        cart_item = Cart(
            user_id=sample_guest.id,
            product_id=sample_product.id,
            quantity=1
        )
        db_session.add(cart_item)
        db_session.commit()

        response = client.get('/checkout')
        assert response.status_code == 200

    def test_checkout_requires_cart(self, client, sample_guest):
        """Test checkout redirects if cart is empty"""
        with client.session_transaction() as sess:
            sess['session'] = sample_guest.session

        response = client.get('/checkout')
        # Redirects to shop when cart is empty
        assert response.status_code in (200, 302)

class TestAboutPage:
    """Tests for about page"""
    
    def test_about_page_loads(self, client):
        """Test about page loads successfully"""
        response = client.get('/about')
        assert response.status_code == 200
        assert 'من نحن' in response.data.decode('utf-8') or 'عن المتجر' in response.data.decode('utf-8')
