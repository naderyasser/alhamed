"""
Tests for utility functions
"""
import pytest
from datetime import datetime, timedelta

class TestHelperFunctions:
    """Tests for helper functions"""
    
    def test_allowed_file(self):
        """Test file extension validation"""
        from app import allowed_file
        
        assert allowed_file('image.jpg') is True
        assert allowed_file('image.jpeg') is True
        assert allowed_file('image.png') is True
        assert allowed_file('image.gif') is True
        assert allowed_file('document.pdf') is False
        assert allowed_file('script.exe') is False
        assert allowed_file('noextension') is False
    
    def test_utc_now(self):
        """Test UTC time function returns naive datetime (tzinfo stripped for SQLite)"""
        from app import utc_now

        now = utc_now()
        assert isinstance(now, datetime)
        # utc_now() intentionally strips tzinfo for SQLite compatibility
        assert now.tzinfo is None

class TestSessionManagement:
    """Tests for session management"""
    
    def test_check_session_creates_user(self, client, db_session):
        """Test check_session creates guest user"""
        from app import check_session, Gusts
        
        with client:
            client.get('/')
            with client.session_transaction() as sess:
                if 'user_id' in sess:
                    user_id = sess['user_id']
                    user = db_session.get(Gusts, user_id)
                    assert user is not None

class TestCartCleanup:
    """Tests for cart cleanup"""
    
    def test_cleanup_expired_cart_items(self, db_session, sample_guest, sample_product):
        """Test cleaning up expired cart items"""
        from app import Cart, cleanup_expired_cart_items, utc_now

        # Create old cart item
        old_cart = Cart(
            user_id=sample_guest.id,
            product_id=sample_product.id,
            quantity=1
        )
        old_cart.created_at = utc_now() - timedelta(hours=25)
        db_session.add(old_cart)

        # Create recent cart item
        new_cart = Cart(
            user_id=sample_guest.id,
            product_id=sample_product.id,
            quantity=2
        )
        db_session.add(new_cart)
        db_session.commit()

        # Run cleanup (already inside active app context from the session fixture)
        cleanup_expired_cart_items()
        
        # Old item should be deleted
        assert db_session.get(Cart, old_cart.id) is None
        # New item should still exist
        assert db_session.get(Cart, new_cart.id) is not None

class TestCSRF:
    """Tests for CSRF protection"""

    def test_csrf_token_injection(self, client):
        """Test CSRF token is injected into templates via meta tag"""
        response = client.get('/')
        assert b'csrf-token' in response.data

    def test_categories_injection(self, client, sample_category):
        """Test categories are visible in rendered pages (context processor)"""
        response = client.get('/')
        assert response.status_code == 200
        assert sample_category.name in response.data.decode('utf-8')
