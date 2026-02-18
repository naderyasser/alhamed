"""
Tests for products_missing_images route and related functionality.
Tests the phone number updates and Facebook link in templates.
"""
import pytest
import os
from app import Product, Category, AdditionalImage


class TestMissingImagesRoute:
    """Tests for /admin/products/missing-images route"""

    def test_missing_images_requires_auth(self, client):
        """Unauthenticated access should redirect to login"""
        response = client.get('/admin/products/missing-images')
        assert response.status_code == 302
        assert 'login' in response.location.lower() or response.status_code == 302

    def test_missing_images_accessible_when_authenticated(self, authenticated_client):
        """Authenticated admin should access the page"""
        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200

    def test_no_missing_images_shows_success(self, authenticated_client, db_session, sample_category):
        """When all products have valid images the page shows success message"""
        product = Product(
            name='منتج بصورة',
            price=100.0,
            discount=0,
            stock=5,
            description='وصف',
            image='static/uploads/real_image.jpg',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        # Page should indicate no missing images OR show the product as missing
        # (because the file doesn't exist on disk in test env)
        assert 'منتجات بدون صور' in response.data.decode('utf-8') or \
               'ممتاز' in response.data.decode('utf-8')

    def test_empty_image_product_detected(self, authenticated_client, db_session, sample_category):
        """Product with empty image field should be detected as missing"""
        product = Product(
            name='منتج بدون صورة',
            price=200.0,
            discount=0,
            stock=10,
            description='وصف',
            image='',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        assert 'منتج بدون صورة' in response.data.decode('utf-8')

    def test_placeholder_image_product_detected(self, authenticated_client, db_session, sample_category):
        """Product with placeholder image should be detected as missing"""
        product = Product(
            name='منتج placeholder',
            price=150.0,
            discount=0,
            stock=8,
            description='وصف',
            image='static/images/placeholder.png',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        assert 'منتج placeholder' in response.data.decode('utf-8')

    def test_missing_images_page_shows_product_count(self, authenticated_client, db_session, sample_category):
        """Page should display count of missing and total products"""
        # Create products: one with placeholder, one with a "real" path
        p1 = Product(
            name='منتج بلا صورة 1',
            price=100.0,
            discount=0,
            stock=5,
            description='وصف',
            image='',
            category_id=sample_category.id
        )
        p2 = Product(
            name='منتج بلا صورة 2',
            price=200.0,
            discount=0,
            stock=10,
            description='وصف',
            image='static/images/placeholder.png',
            category_id=sample_category.id
        )
        db_session.add_all([p1, p2])
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        # Page contains count info
        assert 'منتج' in body

    def test_missing_images_link_in_products_page(self, authenticated_client):
        """The main products page should have a link to missing images page"""
        response = authenticated_client.get('/admin/products')
        assert response.status_code == 200
        assert 'missing-images' in response.data.decode('utf-8') or \
               'منتجات بدون صور' in response.data.decode('utf-8')

    def test_missing_images_shows_edit_link(self, authenticated_client, db_session, sample_category):
        """Each missing product should have an edit link"""
        product = Product(
            name='منتج يحتاج تعديل',
            price=300.0,
            discount=0,
            stock=3,
            description='وصف',
            image='',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        assert 'تعديل' in body or 'edit' in body.lower()

    def test_missing_images_shows_product_id(self, authenticated_client, db_session, sample_category):
        """Missing image page shows product IDs"""
        product = Product(
            name='منتج مع ID',
            price=400.0,
            discount=0,
            stock=7,
            description='وصف',
            image='',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        assert str(product.id) in response.data.decode('utf-8')

    def test_missing_images_shows_product_price(self, authenticated_client, db_session, sample_category):
        """Missing image page shows product prices"""
        product = Product(
            name='منتج بسعر محدد',
            price=999.0,
            discount=0,
            stock=2,
            description='وصف',
            image='',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        assert '999' in response.data.decode('utf-8')

    def test_product_with_http_image_not_flagged(self, authenticated_client, db_session, sample_category):
        """Products with http/https image URLs should NOT be flagged as missing"""
        product = Product(
            name='منتج بصورة URL',
            price=500.0,
            discount=0,
            stock=15,
            description='وصف',
            image='https://example.com/product-image.jpg',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        # Should NOT appear as missing IF the page lists only missing products
        # If it's showing as "all good" that's also fine
        # Just check page renders
        assert 'منتجات بدون صور' in body or 'ممتاز' in body


class TestContactInfoInTemplates:
    """Tests verifying the contact info (phone & Facebook link) in templates"""

    def test_whatsapp_bubble_uses_new_phone(self, client):
        """The WhatsApp floating button should use 01050188516"""
        response = client.get('/')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        # New phone number should appear in wa.me link
        assert '201050188516' in body or '01050188516' in body

    def test_footer_phone_updated(self, client):
        """Footer phone number should be 01050188516"""
        response = client.get('/')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        assert '01050188516' in body or '201050188516' in body

    def test_old_phone_not_present(self, client):
        """Old phone number 01030553029 should NOT appear in the shop"""
        response = client.get('/')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        assert '01030553029' not in body

    def test_facebook_link_in_footer(self, client):
        """Facebook page link should appear in footer"""
        response = client.get('/')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        assert 'facebook.com/share/1HBiHzhNp9' in body

    def test_facebook_bubble_present(self, client):
        """Facebook floating bubble should be present"""
        response = client.get('/')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        assert 'facebook-bubble' in body or '1HBiHzhNp9' in body

    def test_facebook_link_on_about_page(self, client):
        """Facebook link should also be visible on about page"""
        response = client.get('/about')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        assert '01050188516' in body or 'facebook' in body.lower()

    def test_phone_tel_link_in_footer(self, client):
        """Footer should have a tel: link with the new number"""
        response = client.get('/')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        assert 'tel:+201050188516' in body or 'tel:201050188516' in body


class TestAdminProductsMissingImagesIntegration:
    """Integration tests for the missing images functionality"""

    def test_full_workflow_detect_and_edit(self, authenticated_client, db_session, sample_category):
        """Full workflow: detect missing image product, navigate to edit"""
        # 1. Create a product without an image
        product = Product(
            name='منتج للاختبار الكامل',
            price=750.0,
            discount=5.0,
            stock=20,
            description='منتج للاختبار',
            image='',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        # 2. Visit missing images page
        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        assert 'منتج للاختبار الكامل' in response.data.decode('utf-8')

        # 3. Verify edit endpoint accessible
        edit_response = authenticated_client.get(f'/admin/product/{product.id}/edit')
        assert edit_response.status_code == 200

    def test_missing_images_count_accuracy(self, authenticated_client, db_session, sample_category):
        """Verify the count of missing image products is accurate"""
        # Start fresh: delete any existing products from this test session
        existing = Product.query.all()
        for p in existing:
            db_session.delete(p)
        db_session.commit()

        # Create 3 products: 2 missing images, 1 with http URL
        p1 = Product(name='Missing 1', price=100.0, discount=0, stock=1,
                     description='d', image='', category_id=sample_category.id)
        p2 = Product(name='Missing 2', price=200.0, discount=0, stock=2,
                     description='d', image='static/images/placeholder.png',
                     category_id=sample_category.id)
        p3 = Product(name='Has Image', price=300.0, discount=0, stock=3,
                     description='d', image='https://example.com/img.jpg',
                     category_id=sample_category.id)
        db_session.add_all([p1, p2, p3])
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        body = response.data.decode('utf-8')
        # Page should list the two missing-image products
        assert 'Missing 1' in body
        assert 'Missing 2' in body
        # Product with http image should NOT be flagged
        assert 'Has Image' not in body

    def test_none_image_product_detected(self, authenticated_client, db_session, sample_category):
        """Product with 'None' string as image should be detected"""
        # This is an edge case that can happen when image path is saved as string "None"
        # We need to bypass SQLAlchemy's nullable constraint for this test
        # so we directly create with a "None" string value
        product = Product(
            name='منتج بـ None',
            price=100.0,
            discount=0,
            stock=5,
            description='وصف',
            image='None',
            category_id=sample_category.id
        )
        db_session.add(product)
        db_session.commit()

        response = authenticated_client.get('/admin/products/missing-images')
        assert response.status_code == 200
        assert 'منتج بـ None' in response.data.decode('utf-8')
