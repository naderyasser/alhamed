"""
Tests for API endpoints
"""
import pytest
import json

class TestRecentOrdersAPI:
    """Tests for recent orders API"""
    
    def test_recent_orders_api(self, authenticated_client, sample_order):
        """Test recent orders API endpoint"""
        response = authenticated_client.get('/admin/api/recent-orders')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'orders' in data
        assert 'count' in data
    
    def test_recent_orders_requires_auth(self, client):
        """Test API requires authentication"""
        response = client.get('/admin/api/recent-orders')
        assert response.status_code == 302

class TestDropshippingAPI:
    """Tests for dropshipping API endpoints"""
    
    @pytest.mark.skip(reason="Requires mocking network requests")
    def test_dropshipping_scrape_api(self, authenticated_client):
        """Test dropshipping scrape API"""
        data = {
            'url': 'https://example.com/product'
        }
        
        response = authenticated_client.post('/admin/dropshipping/api/scrape',
                                            json=data,
                                            content_type='application/json')
        
        # Should return JSON response
        assert response.status_code in [200, 400]
        result = json.loads(response.data)
        assert 'success' in result
    
    def test_dropshipping_api_empty_url(self, authenticated_client):
        """Test API with empty URL"""
        response = authenticated_client.post('/admin/dropshipping/api/scrape',
                                            json={'url': ''},
                                            content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

class TestProductImageAPI:
    """Tests for product image operations"""
    
    def test_delete_additional_image(self, authenticated_client, sample_product, db_session):
        """Test deleting additional product image"""
        from app import AdditionalImage
        
        # Create additional image
        img = AdditionalImage(
            image='static/uploads/test_image.jpg',
            product_id=sample_product.id
        )
        db_session.add(img)
        db_session.commit()
        
        response = authenticated_client.post(f'/admin/delete_additional_image/{img.id}')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
