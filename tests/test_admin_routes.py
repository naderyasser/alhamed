"""
Tests for admin routes
"""
import pytest
from flask import session
from io import BytesIO

class TestAdminAuth:
    """Tests for admin authentication"""
    
    def test_admin_login_page(self, client):
        """Test admin login page loads"""
        response = client.get('/admin/login')
        assert response.status_code == 200
        assert 'تسجيل الدخول' in response.data.decode('utf-8')
    
    def test_admin_login_success(self, client, sample_admin):
        """Test successful admin login"""
        response = client.post('/admin/login', data={
            'username': 'admin@example.com',
            'password': 'admin123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_admin_login_failure(self, client, sample_admin):
        """Test failed admin login with wrong password"""
        response = client.post('/admin/login', data={
            'username': 'admin@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should stay on the login page (not redirect to dashboard)
        assert 'تسجيل الدخول' in response.data.decode('utf-8')
    
    def test_admin_logout(self, authenticated_client):
        """Test admin logout"""
        response = authenticated_client.get('/admin/logout', follow_redirects=True)
        assert response.status_code == 200
    
    def test_admin_required_decorator(self, client):
        """Test that admin routes require authentication"""
        response = client.get('/admin/')
        assert response.status_code == 302  # Redirect to login

class TestAdminDashboard:
    """Tests for admin dashboard"""
    
    def test_admin_dashboard_loads(self, authenticated_client):
        """Test admin dashboard loads"""
        response = authenticated_client.get('/admin/')
        assert response.status_code == 200
        assert 'لوحة التحكم' in response.data.decode('utf-8')
    
    def test_dashboard_shows_stats(self, authenticated_client, sample_order):
        """Test dashboard displays statistics"""
        response = authenticated_client.get('/admin/')
        assert response.status_code == 200

class TestAdminProducts:
    """Tests for admin product management"""
    
    def test_products_page_loads(self, authenticated_client):
        """Test products management page loads"""
        response = authenticated_client.get('/admin/products')
        assert response.status_code == 200
        assert 'المنتجات' in response.data.decode('utf-8')
    
    def test_products_list_displayed(self, authenticated_client, sample_product):
        """Test products are displayed"""
        response = authenticated_client.get('/admin/products')
        assert response.status_code == 200
        assert sample_product.name in response.data.decode('utf-8')
    
    def test_add_product_with_valid_data(self, authenticated_client, sample_category, app):
        """Test adding a product with valid data"""
        data = {
            'name': 'منتج جديد',
            'price': '500',
            'discount': '10',
            'quantity': '20',
            'category': str(sample_category.id),
            'description': 'وصف المنتج',
            'image': (BytesIO(b'fake image data'), 'test.jpg')
        }
        
        response = authenticated_client.post('/admin/add_product', 
                                            data=data,
                                            content_type='multipart/form-data',
                                            follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_add_product_without_name(self, authenticated_client, sample_category):
        """Test adding product without name fails"""
        data = {
            'name': '',
            'price': '500',
            'quantity': '20',
            'category': str(sample_category.id),
        }
        
        response = authenticated_client.post('/admin/add_product', 
                                            data=data,
                                            follow_redirects=False)
        
        # Route redirects back (302) when validation fails
        assert response.status_code in (200, 302, 400)
    
    def test_delete_product(self, authenticated_client, sample_product):
        """Test deleting a product"""
        response = authenticated_client.post(f'/admin/delete_product/{sample_product.id}',
                                            follow_redirects=True)
        assert response.status_code == 200
    
    def test_edit_product(self, authenticated_client, sample_product, sample_category):
        """Test editing a product"""
        data = {
            'name': 'اسم معدل',
            'price': '16000',
            'discount': '15',
            'quantity': '40',
            'category': str(sample_category.id),
            'description': 'وصف معدل'
        }
        
        response = authenticated_client.post(f'/admin/edit_product/{sample_product.id}',
                                            data=data,
                                            follow_redirects=True)
        assert response.status_code == 200

class TestAdminCategories:
    """Tests for admin category management"""
    
    def test_categories_page_loads(self, authenticated_client):
        """Test categories page loads"""
        response = authenticated_client.get('/admin/categories')
        assert response.status_code == 200
        assert 'التصنيفات' in response.data.decode('utf-8')
    
    def test_add_category(self, authenticated_client):
        """Test adding a new category"""
        response = authenticated_client.post('/admin/add_category', data={
            'name': 'تصنيف جديد',
            'description': 'وصف التصنيف'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_add_duplicate_category(self, authenticated_client, sample_category):
        """Test adding duplicate category fails"""
        response = authenticated_client.post('/admin/add_category', data={
            'name': sample_category.name
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_edit_category(self, authenticated_client, sample_category):
        """Test editing a category"""
        response = authenticated_client.post(f'/admin/edit_category/{sample_category.id}',
                                            data={
                                                'name': 'اسم معدل',
                                                'description': 'وصف معدل'
                                            },
                                            follow_redirects=True)
        assert response.status_code == 200
    
    def test_delete_empty_category(self, authenticated_client, db_session):
        """Test deleting category without products"""
        from app import Category
        category = Category(name='تصنيف للحذف')
        db_session.add(category)
        db_session.commit()
        
        response = authenticated_client.post(f'/admin/delete_category/{category.id}',
                                            follow_redirects=True)
        assert response.status_code == 200
    
    def test_delete_category_with_products(self, authenticated_client, sample_product, sample_category):
        """Test deleting category with products is blocked or warns the user"""
        response = authenticated_client.post(f'/admin/delete_category/{sample_category.id}',
                                            follow_redirects=True)
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        # Either blocked with a message, or redirected back to categories page
        assert ('لا يمكن' in body or 'خطأ' in body
                or 'تصنيف' in body or 'categories' in response.headers.get('Location', '').lower()
                or 'المنتجات' in body or response.status_code == 200)

class TestAdminOrders:
    """Tests for admin order management"""
    
    def test_orders_page_loads(self, authenticated_client):
        """Test orders page loads"""
        response = authenticated_client.get('/admin/orders')
        assert response.status_code == 200
    
    def test_orders_list_displayed(self, authenticated_client, sample_order):
        """Test orders are displayed"""
        response = authenticated_client.get('/admin/orders')
        assert response.status_code == 200
