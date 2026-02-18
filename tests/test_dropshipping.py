"""
Tests for dropshipping functionality
"""
import pytest
import json
from unittest.mock import patch, Mock

class TestDropshippingRoutes:
    """Tests for dropshipping routes"""
    
    def test_dropshipping_page_loads(self, authenticated_client):
        """Test dropshipping page loads"""
        response = authenticated_client.get('/admin/dropshipping')
        assert response.status_code == 200
        assert 'دروب شوبينج' in response.data.decode('utf-8')
    
    def test_dropshipping_requires_auth(self, client):
        """Test dropshipping requires authentication"""
        response = client.get('/admin/dropshipping')
        assert response.status_code == 302
    
    def test_dropshipping_displays_items(self, authenticated_client, sample_dropship_product):
        """Test dropshipping items are displayed"""
        response = authenticated_client.get('/admin/dropshipping')
        assert response.status_code == 200
        assert sample_dropship_product.name in response.data.decode('utf-8')

class TestDropshippingScraping:
    """Tests for product scraping"""
    
    @patch('app.scrape_product_data')
    def test_scrape_product_success(self, mock_scrape, authenticated_client, db_session):
        """Test successful product scraping"""
        mock_scrape.return_value = {
            'success': True,
            'name': 'منتج مسحوب',
            'price': 299.99,
            'description': 'وصف المنتج',
            'image_url': 'https://example.com/image.jpg',
            'additional_images': ['https://example.com/img1.jpg'],
            'source_site': 'example.com'
        }
        
        response = authenticated_client.post('/admin/dropshipping/scrape', data={
            'url': 'https://example.com/product/123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        mock_scrape.assert_called_once()
    
    @patch('app.scrape_product_data')
    def test_scrape_product_failure(self, mock_scrape, authenticated_client):
        """Test failed product scraping"""
        mock_scrape.return_value = {
            'success': False,
            'error': 'فشل الاتصال بالموقع'
        }
        
        response = authenticated_client.post('/admin/dropshipping/scrape', data={
            'url': 'https://invalid-site.com/product'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_scrape_empty_url(self, authenticated_client):
        """Test scraping with empty URL"""
        response = authenticated_client.post('/admin/dropshipping/scrape', data={
            'url': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_scrape_duplicate_url(self, authenticated_client, sample_dropship_product):
        """Test scraping duplicate URL"""
        response = authenticated_client.post('/admin/dropshipping/scrape', data={
            'url': sample_dropship_product.source_url
        }, follow_redirects=True)
        
        assert response.status_code == 200

class TestDropshippingImport:
    """Tests for importing dropship products"""
    
    @patch('app.download_image_from_url')
    def test_import_dropship_product(self, mock_download, authenticated_client, sample_dropship_product, sample_category, db_session):
        """Test importing dropship product as local product"""
        mock_download.return_value = 'downloaded_image.jpg'
        
        data = {
            'name': 'منتج مستورد',
            'price': '500',
            'discount': '10',
            'stock': '15',
            'category_id': str(sample_category.id),
            'description': 'وصف المنتج المستورد'
        }
        
        response = authenticated_client.post(f'/admin/dropshipping/import/{sample_dropship_product.id}',
                                            data=data,
                                            follow_redirects=True)
        
        assert response.status_code == 200
        
        # Check status changed
        db_session.refresh(sample_dropship_product)
        assert sample_dropship_product.status == 'imported'
        assert sample_dropship_product.imported_product_id is not None
    
    def test_import_nonexistent_dropship(self, authenticated_client):
        """Test importing nonexistent dropship product"""
        response = authenticated_client.post('/admin/dropshipping/import/99999', data={
            'name': 'test',
            'price': '100',
            'stock': '10',
            'category_id': '1'
        })
        
        assert response.status_code == 404

class TestDropshippingDelete:
    """Tests for deleting dropship products"""
    
    def test_delete_dropship_product(self, authenticated_client, sample_dropship_product, db_session):
        """Test deleting dropship product"""
        dropship_id = sample_dropship_product.id
        
        response = authenticated_client.post(f'/admin/dropshipping/delete/{dropship_id}',
                                            follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify deleted
        from app import DropshipProduct
        deleted = db_session.get(DropshipProduct, dropship_id)
        assert deleted is None
    
    def test_delete_nonexistent_dropship(self, authenticated_client):
        """Test deleting nonexistent dropship product"""
        response = authenticated_client.post('/admin/dropshipping/delete/99999')
        assert response.status_code == 404

class TestScrapingFunction:
    """Tests for scraping helper function"""
    
    @patch('requests.get')
    def test_scrape_product_data_success(self, mock_get):
        """Test scraping product data from HTML"""
        from app import scrape_product_data
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
            <html>
                <head>
                    <meta property="og:title" content="Test Product">
                    <meta property="og:image" content="https://example.com/image.jpg">
                    <meta property="og:description" content="Product description">
                    <meta property="product:price:amount" content="299.99">
                </head>
                <body>
                    <h1>Test Product</h1>
                </body>
            </html>
        '''
        mock_get.return_value = mock_response
        
        result = scrape_product_data('https://example.com/product')
        
        assert result['success'] is True
        assert 'Test Product' in result['name']
    
    @patch('requests.get')
    def test_scrape_product_data_timeout(self, mock_get):
        """Test scraping with timeout"""
        from app import scrape_product_data
        import requests
        
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = scrape_product_data('https://example.com/product')
        
        assert result['success'] is False
        assert 'انتهت مهلة' in result['error']
    
    @patch('requests.get')
    def test_scrape_product_data_connection_error(self, mock_get):
        """Test scraping with connection error"""
        from app import scrape_product_data
        import requests
        
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        result = scrape_product_data('https://example.com/product')
        
        assert result['success'] is False
        assert 'فشل الاتصال' in result['error']

class TestImageDownload:
    """Tests for image downloading"""
    
    @patch('requests.get')
    @patch('builtins.open', create=True)
    def test_download_image_success(self, mock_open, mock_get, app):
        """Test successful image download"""
        from app import download_image_from_url
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.iter_content = lambda chunk_size: [b'fake image data']
        mock_get.return_value = mock_response
        
        with app.app_context():
            result = download_image_from_url('https://example.com/image.jpg')
        
        assert result is not None
        assert result.endswith('.jpg')
    
    @patch('requests.get')
    def test_download_image_failure(self, mock_get, app):
        """Test failed image download"""
        from app import download_image_from_url
        import requests
        
        mock_get.side_effect = requests.exceptions.RequestException()
        
        with app.app_context():
            result = download_image_from_url('https://example.com/image.jpg')
        
        assert result is None
