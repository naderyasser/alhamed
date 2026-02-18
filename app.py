# pyright: reportMissingImports=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportArgumentType=false
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, Blueprint, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text as sa_text
from datetime import datetime, timedelta, timezone
from flask_migrate import Migrate
import os
import json
import hmac
import secrets
import requests
from uuid import uuid4
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from models.bosta import BostaService
import pandas as pd
from io import BytesIO
import shutil
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

# Import Honeybadger conditionally to handle compatibility issues
try:
    from honeybadger.contrib import FlaskHoneybadger
    has_honeybadger = True
except (ImportError, AttributeError) as e:
    print(f"Warning: Honeybadger import failed: {e}")
    has_honeybadger = False

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///orfe-shop.sqlite3')
is_debug_env = os.getenv('FLASK_DEBUG', '1') in ('1', 'true', 'True')
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    if is_debug_env:
        secret_key = 'dev-only-secret-key-change-me'
    else:
        raise RuntimeError('SECRET_KEY environment variable is required in non-debug mode')

app.config['SECRET_KEY'] = secret_key
app.config['FAWATERAK_API_KEY'] = os.getenv('FAWATERAK_API_KEY', '')
app.config['FAWATERAK_API_URL'] = os.getenv('FAWATERAK_API_URL', 'https://app.fawaterk.com/api/v2/createInvoiceLink')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'orfe-shop'
app.secret_key = app.config['SECRET_KEY']

CSRF_EXEMPT_ENDPOINTS = {
    'shop.payment_webhook',
}


def utc_now():
    """Return current UTC time as a naive datetime (no timezone info).
    SQLite does not preserve timezone info, so we store naive UTC consistently."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Configure Honeybadger only if successfully imported
if has_honeybadger:
    app.config['HONEYBADGER_ENVIRONMENT'] = os.getenv('HONEYBADGER_ENVIRONMENT', 'production')
    app.config['HONEYBADGER_API_KEY'] = os.getenv('HONEYBADGER_API_KEY', '')
    app.config['HONEYBADGER_PARAMS_FILTERS'] = 'password, secret, credit-card'
    try:
        FlaskHoneybadger(app, report_exceptions=True)
        print("Honeybadger initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize Honeybadger: {e}")
        # Continue without error reporting

# Database backup functionality
def create_project_backup():
    """Create a full backup of the project including code and database"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Create backups directory if it doesn't exist
        backup_dir = os.path.join(os.path.dirname(app.root_path), 'backups', timestamp)
        os.makedirs(backup_dir, exist_ok=True)
        
        # 2. Create project backup (excluding venv, __pycache__, etc.)
        def backup_filter(src, names):
            return {
                'env', '__pycache__', '.git', 'backups',
                '*.pyc', '*.pyo', '*.pyd', '.Python', 'pip-log.txt',
                '.env', '.venv', 'venv', 'ENV'
            }
        
        # Copy entire project
        shutil.copytree(
            app.root_path, 
            os.path.join(backup_dir, 'project'),
            ignore=backup_filter,
            dirs_exist_ok=True
        )
        
        # 3. Backup database separately
        db_backup_dir = os.path.join(backup_dir, 'database')
        os.makedirs(db_backup_dir, exist_ok=True)
        
        db_source = os.path.join(app.root_path, 'instance', 'orfe-shop.sqlite3')
        db_backup = os.path.join(db_backup_dir, 'orfe-shop.sqlite3')
        shutil.copy2(db_source, db_backup)
        
        # 4. Create a zip archive of the backup
        backup_zip = os.path.join(os.path.dirname(backup_dir), f'orfe_backup_{timestamp}.zip')
        shutil.make_archive(
            os.path.splitext(backup_zip)[0],
            'zip',
            backup_dir
        )
        
        # 5. Git operations - Stage only tracked files
        try:
            # Initialize git configuration if not set
            subprocess.run(['git', 'config', 'user.name', 'Backup System'], check=True)
            subprocess.run(['git', 'config', 'user.email', 'backup@alhamd-store.com'], check=True)
            
            # Stage all tracked files
            subprocess.run(['git', 'add', '-u'], check=True)
            
            # Create backup commit
            commit_message = f'Project backup {timestamp}'
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            
            # Try to push (this might fail if no remote access)
            try:
                subprocess.run(['git', 'push', 'origin', 'main'], check=True)
                git_status = "and pushed to GitHub"
            except subprocess.CalledProcessError:
                git_status = "but GitHub push failed (check credentials)"
            
            return True, f"Backup created successfully {git_status}. Saved to: {backup_zip}"
            
        except subprocess.CalledProcessError as e:
            return True, f"Backup created but git operations failed: {str(e)}. Saved to: {backup_zip}"
            
    except Exception as e:
        return False, f"Backup failed: {str(e)}"
        
# Add escapejs filter
@app.template_filter('escapejs')
def escapejs(value):
    if not value:
        return ''
    value = str(value)
    value = value.replace('\\', '\\\\')
    value = value.replace('\'', '\\\'')
    value = value.replace('"', '\\"')
    value = value.replace('\n', '\\n')
    value = value.replace('\r', '\\r')
    value = value.replace('\t', '\\t')
    return value

# save sessiom 365 day 
app.config['PERMANENT_SESSION_LIFETIME'] = 365 * 24 * 60 * 60
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bosta_service = BostaService()

# Add apply_discount filter
@app.template_filter('apply_discount')
def apply_discount(price, discount):
    if not discount:
        return price
    return price * (1 - discount/100)

# Check for shipping discount eligibility
def check_shipping_discount(cart_items):
    """
    Check if the cart is eligible for free shipping based on specific product combination:
    - Only applies when products with IDs 1, 2, and 3 are all in the cart
    
    Returns a dictionary with discount info
    """
    # Initialize product presence flags
    has_product_1 = False
    has_product_2 = False
    has_product_3 = False
    
    # Check each cart item
    for item in cart_items:
        product_id = item.product_id if hasattr(item, 'product_id') else item.product.id 
        
        if product_id == 1:
            has_product_1 = True
        elif product_id == 2:
            has_product_2 = True
        elif product_id == 3:
            has_product_3 = True
    
    # Determine discount eligibility - only applies when all three products are present
    discount_eligible = has_product_1 and has_product_2 and has_product_3
    
    return {
        "eligible": discount_eligible,
        "discount_type": "combo_1_2_3" if discount_eligible else None
    }

# Check for promotional discount (10% off all orders for 5 days)
def check_promotional_discount():
    """
    عرض خصم 10% على جميع الطلبات لمدة 5 أيام
    Check for 10% promotional discount on all orders (valid for 5 days)
    Returns dictionary with discount info
    """

    # Define promotional period (5 days from January 4, 2026)
    promo_start_date = datetime(2026, 1, 4)  # تاريخ بداية العرض
    promo_end_date = datetime(2026, 1, 9, 23, 59, 59)  # 5 أيام
    current_date = datetime.now()

    # Check if promotion is still active
    if current_date < promo_start_date or current_date > promo_end_date:
        return {
            "eligible": False,
            "discount_percent": 0,
            "message": None,
            "promo_active": False
        }

    return {
        "eligible": True,
        "discount_percent": 10,  # 10% خصم
        "message": "خصم 10% على جميع الطلبات! 🎉",
        "promo_active": True
    }

# Check for Eid Al-Adha shipping offer
def check_eid_shipping_offer(cart_items, city_id):
    """
    Check for Eid Al-Adha special shipping offer (6 days duration):
    - Free shipping for package #4 to Alexandria, Cairo, Giza, and Beheira
    - 50% off shipping for package #4 to other governorates
    Returns dictionary with offer details
    """
    
    # Define offer period (6 days) - Eid Al-Adha 2025
    offer_start_date = datetime(2025, 6, 5)  # يبدأ اليوم
    offer_end_date = datetime(2025, 6, 11, 23, 59, 59)  # 6 days
    current_date = datetime.now()
    
    # Check if offer is still active
    if current_date < offer_start_date or current_date > offer_end_date:
        return {"eligible": False, "discount": 0, "message": None, "offer_active": False}

    # Check if cart contains package #4 (العناية الكاملة)
    has_package_4 = False
    for item in cart_items:
        product_id = item.product_id if hasattr(item, 'product_id') else item.product.id 
        if product_id == 4:
            has_package_4 = True
            break
    
    if not has_package_4:
        return {"eligible": False, "discount": 0, "message": None, "offer_active": True}

    # Define cities with free shipping (you'll need to check your actual city_id values)
    free_shipping_cities = [
        "الاسكندريه",  # الإسكندرية
        "القاهره",       # القاهرة  
        "الجيزه",        # الجيزة
        "البحيره"      # البحيرة
    ]
    
    # Get city name from database
    try:
        city = City.query.filter_by(city_id=city_id).first()
        city_name = city.name if city else ""
    except Exception:
        city_name = ""
    
    # Check if city qualifies for free shipping
    city_qualifies_for_free = any(free_city.lower() in city_name.lower() for free_city in free_shipping_cities)
    
    if city_qualifies_for_free:
        return {
            "eligible": True,
            "discount": 1.0,  # 100% discount (free shipping)
            "message": "🎉 شحن مجاني - عرض عيد الأضحى على باقة العناية الكاملة",
            "offer_active": True,
            "offer_type": "eid_free_shipping"
        }
    else:
        return {
            "eligible": True,
            "discount": 0.5,  # 50% discount
            "message": "🎉 خصم 50% على الشحن - عرض عيد الأضحى على باقة العناية الكاملة", 
            "offer_active": True,
            "offer_type": "eid_50_percent"
        }

# products and  Category and Card and Order and OrderItem and adintiol images and adintiol data to prodect amd promo code
class Admins(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
class Gusts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(100), nullable=True) 
    address = db.Column(db.String(100), nullable=True)
    orders = db.relationship('Order', backref='guest', lazy=True)
    carts = db.relationship('Cart', backref='gust', lazy=True)  # This should work now
    last_activity = db.Column(db.DateTime, nullable=False, default=utc_now)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True, default='')
    products = db.relationship('Product', backref='category', lazy=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(100), nullable=False)
    views = db.Column(db.Integer, nullable=False, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    additional_images = db.relationship('AdditionalImage', backref='product', lazy=True)
    additional_data = db.relationship('AdditionalData', backref='product', lazy=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
class AdditionalImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(100), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
class AdditionalData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('gusts.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    
    # إضافة العلاقة مع Product
    product = db.relationship('Product', backref='carts', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('gusts.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100))
    zone_id = db.Column(db.String(100))
    district_id = db.Column(db.String(100))
    business_reference = db.Column(db.String(50), unique=True)
    tracking_number = db.Column(db.String(100))
    shipping_status = db.Column(db.String(50), default='pending')
    cod_amount = db.Column(db.Float)
    payment_method = db.Column(db.String(50), nullable=False)
    package_size = db.Column(db.String(20), default='SMALL')
    package_type = db.Column(db.String(20), default='Parcel')
    invoice_key = db.Column(db.String(100), nullable=True)
    invoice_id = db.Column(db.String(50), nullable=True)
    invoice_url = db.Column(db.String(200), nullable=True)
    payment_status = db.Column(db.String(20), default='pending', nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)  
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

class PromoCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False)
    discount = db.Column(db.Float, nullable=False)
    count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    session = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
class Logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    session = db.Column(db.String(100), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)  
# shiping and city and zone and district and prices
class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    zones = db.relationship('Zone', backref='city', lazy=True, foreign_keys='Zone.city_id')
    price = db.relationship('ShippingCost', backref='city', lazy=True, foreign_keys='ShippingCost.city_id')
    districts = db.relationship('District', backref='city', lazy=True, foreign_keys='District.city_id')
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'city_id': self.city_id,
            'zones': [zone.serialize() for zone in self.zones],
            'districts': [district.serialize() for district in self.districts]
        }

class Zone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city_id = db.Column(db.Integer, db.ForeignKey('city.city_id'), nullable=False)
    zone_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'zone_id': self.zone_id
        }

class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city_id = db.Column(db.Integer, db.ForeignKey('city.city_id'), nullable=False)
    district_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'district_id': self.district_id
        }

class ShippingCost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey('city.city_id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

class DropshipProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_url = db.Column(db.String(500), nullable=False)
    source_site = db.Column(db.String(100), nullable=True)
    name = db.Column(db.String(300), nullable=True)
    price = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    additional_images = db.Column(db.Text, nullable=True)  # JSON array
    status = db.Column(db.String(20), default='pending')  # pending, imported, error
    imported_product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

# changShippingCostFromcity_idIsIdToCityId()

shop = Blueprint('shop', __name__)
admin = Blueprint('admin', __name__)

def cleanup_expired_cart_items():
    """Delete cart items older than 24 hours"""
    try:
        expiration_time = utc_now() - timedelta(hours=24)
        expired_items = Cart.query.filter(Cart.created_at < expiration_time).all()
        for item in expired_items:
            db.session.delete(item)
        db.session.commit()
    except Exception as e:
        app.logger.error(f'Error cleaning up expired cart items: {str(e)}')
        db.session.rollback()

def check_session():
    """
    Check and manage user session, including:
    - Session creation/validation
    - Cart cleanup
    - User activity tracking
    - Session expiration handling
    """
    try:
        # 1. Check if session exists
        if 'session' not in session:
            # Create new session
            session['session'] = os.urandom(24).hex()
            session['cart_count'] = 0
            new_guest = Gusts(
                session=session['session'],
                last_activity=utc_now()
            )
            db.session.add(new_guest)
            db.session.commit()
            return

        # 2. Get existing guest
        guest = Gusts.query.filter_by(session=session['session']).first()
        
        if guest:
            # 3. Keep previous last activity for expiration check
            previous_last_activity = guest.last_activity
            
            # 4. Clean up expired cart items
            cleanup_expired_cart_items()
            
            # 5. Update cart count
            cart_count = Cart.query.filter_by(user_id=guest.id).count()
            session['cart_count'] = cart_count
            
            # 6. Check for session expiration (30 days of inactivity)
            expiration_time = utc_now() - timedelta(days=30)
            if previous_last_activity:
                if previous_last_activity.tzinfo is not None:
                    previous_last_activity = previous_last_activity.replace(tzinfo=None)
                if previous_last_activity < expiration_time:
                    # Clear old cart items
                    Cart.query.filter_by(user_id=guest.id).delete()
                    # Create new session
                    session.clear()
                    session['session'] = os.urandom(24).hex()
                    session['cart_count'] = 0
                    new_guest = Gusts(
                        session=session['session'],
                        last_activity=utc_now()
                    )
                    db.session.add(new_guest)
                    db.session.commit()
                    return

            # Update activity only after expiration check
            guest.last_activity = utc_now()
                
            db.session.commit()
        else:
            # 7. Handle orphaned session
            session.clear()
            session['session'] = os.urandom(24).hex()
            session['cart_count'] = 0
            new_guest = Gusts(
                session=session['session'],
                last_activity=utc_now()
            )
            db.session.add(new_guest)
            db.session.commit()
            
    except Exception as e:
        app.logger.error(f'Error in check_session: {str(e)}')
        db.session.rollback()
        # Ensure session is valid even if there's an error
        if 'session' not in session:
            session['session'] = os.urandom(24).hex()
            session['cart_count'] = 0


def generate_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_hex(32)
        session['_csrf_token'] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {'csrf_token': generate_csrf_token()}

@app.context_processor
def inject_global_data():
    """Inject categories and other global data into all templates"""
    try:
        all_categories = Category.query.all()
    except Exception:
        all_categories = []
    return {'all_categories': all_categories}
@app.route('/test-honeybadger')
def test_honeybadger():
    if os.getenv('FLASK_DEBUG', '0') not in ('1', 'true', 'True'):
        abort(404)
    return f"{1/0}"
@app.before_request
def before_request():
    check_session()
    cleanup_expired_cart_items()  # Clean up expired items on each request
    session.permanent = True
    session.modified = True


@app.before_request
def csrf_protect():
    if request.method != 'POST':
        return

    if request.endpoint in CSRF_EXEMPT_ENDPOINTS:
        return

    if request.is_json:
        return

    session_token = session.get('_csrf_token')
    request_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')

    if not session_token or not request_token or not hmac.compare_digest(session_token, request_token):
        if request.blueprint == 'admin':
            flash('جلسة النموذج غير صالحة، أعد المحاولة', 'error')
            return redirect(request.referrer or url_for('admin.login'))
        flash('انتهت صلاحية النموذج، أعد المحاولة', 'danger')
        return redirect(request.referrer or url_for('shop.home'))

@app.template_filter('currency')
def currency_format(value):
    return f"{value:,.2f} ج.م"

@app.template_filter('date_format')
def date_format(value):
    return value.strftime('%Y-%m-%d %I:%M %p')
@shop.route('/')
def home():

    check_session()
    categories = Category.query.all()
    last_products = Product.query.order_by(Product.created_at.desc()).limit(8).all()
    trending_products = Product.query.order_by(Product.views.desc()).limit(8).all()
    return render_template("shop/index.html", 
                           last_products=last_products, 
                           most_viewed=trending_products,
                           categories=categories,
                           section_id="featured-products",
                           section_title="Our Featured Products",
                           products=last_products)

@shop.route('/shop')
def list():
    page = request.args.get('page', 1, type=int)  # Current page
    per_page = request.args.get('per_page', 9, type=int)  # Items per page
    sort = request.args.get('sort', 'default')  # Sorting option
    search = request.args.get('search', '')  # Search query
    category = request.args.get('category', '')  # Category filter
    price = request.args.get('price', '')  # Price range filter

    # Base query
    query = Product.query

    # Apply filters
    if search:
      query = query.filter(or_(
        Product.name.ilike(f'%{search}%'),
        Product.description.ilike(f'%{search}%')
      ))
    if category:
      query = query.filter(Product.category_id == category)
    if price:
      try:
          if '+' in price:
              # Handle "200+" style price ranges
              min_price = float(price.replace('+', ''))
              query = query.filter(Product.price >= min_price)
          elif '-' in price:
              # Handle regular price ranges like "100-200"
              min_price, max_price = map(float, price.split('-'))
              query = query.filter(Product.price.between(min_price, max_price))
          else:
              # Handle single price value
              exact_price = float(price)
              query = query.filter(Product.price == exact_price)
      except ValueError:
          # Silently handle invalid price formats
          app.logger.warning(f"Invalid price filter format: {price}")

    # Apply sorting
    if sort == 'name-asc':
      query = query.order_by(Product.name.asc())
    elif sort == 'name-desc':
      query = query.order_by(Product.name.desc())
    elif sort == 'price-asc':
      query = query.order_by(Product.price.asc())
    elif sort == 'price-desc':
      query = query.order_by(Product.price.desc())
    elif sort == 'rating-asc' or sort == 'rating-desc':
      # Handle rating sort by falling back to default sort for now (newest products)
      # This prevents errors when rating is requested but the field doesn't exist
      app.logger.warning(f"Rating sort requested but not implemented. Falling back to default sort.")
      query = query.order_by(Product.created_at.desc())
    elif sort == 'model-asc' or sort == 'model-desc':
      # Handle model sort by falling back to default sort
      app.logger.warning(f"Model sort requested but not implemented. Falling back to default sort.")
      query = query.order_by(Product.created_at.desc())
    else:
      query = query.order_by(Product.created_at.desc())

    # Pagination
    paginated_products = query.paginate(page=page, per_page=per_page, error_out=False)
    products = paginated_products.items

    # Get all categories for the sidebar
    categories = Category.query.all()

    # Render the template with filtered products and pagination data
    return render_template('shop/shop.html', 
                  products=products, 
                  categories=categories, 
                  pagination=paginated_products,
                  current_filters={
                    'sort': sort,
                    'search': search,
                    'category': category,
                    'price': price
                  })
    
@shop.route('/<int:product_id>')
def product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    additional_images = AdditionalImage.query.filter_by(product_id=product_id).all()
    additional_data = AdditionalData.query.filter_by(product_id=product_id).all()
    product.views += 1
    db.session.commit()
    random_products = Product.query.order_by(db.func.random()).limit(6).all()
    return render_template('shop/product.html', product=product, additional_images=additional_images, additional_data=additional_data, products=random_products)
@shop.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    try:
        # Clean up expired items first
        cleanup_expired_cart_items()
        
        # Get product and validate
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)
        if not product.stock > 0:
            flash('المنتج غير متوفر حالياً', 'danger')
            return redirect(url_for('shop.product', product_id=product_id))
            
        # Validate and get quantity
        try:
            quantity = int(request.form.get('quantity', 1))
            if quantity < 1:
                raise ValueError("Quantity must be positive")
        except ValueError:
            flash('الكمية غير صالحة', 'danger')
            return redirect(url_for('shop.product', product_id=product_id))
        
        # Check stock availability
        if quantity > product.stock:
            flash('الكمية المطلوبة غير متوفرة في المخزون', 'danger')
            return redirect(url_for('shop.product', product_id=product_id))
        
        # Get or create user session
        user = Gusts.query.filter_by(session=session['session']).first()
        if not user:
            flash('حدث خطأ في جلسة المستخدم', 'danger')
            return redirect(url_for('shop.product', product_id=product_id))
        
        # Check if item exists in cart
        cart_item = Cart.query.filter_by(user_id=user.id, product_id=product_id).first()
        
        if cart_item:
            # Update existing cart item
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.stock:
                flash('لا يمكن إضافة هذه الكمية، المخزون غير كافي', 'danger')
                return redirect(url_for('shop.cart'))
            
            cart_item.quantity = new_quantity
            cart_item.created_at = utc_now()  # Reset the creation time
        else:
            # Create new cart item
            cart_item = Cart(
                user_id=user.id,
                product_id=product_id,
                quantity=quantity,
                created_at=utc_now()
            )
        
        # Save changes
        db.session.add(cart_item)
        db.session.commit()
        
        # Update session cart count
        session['cart_count'] = Cart.query.filter_by(user_id=user.id).count()
        
        flash('تمت إضافة المنتج إلى السلة بنجاح!', 'success')
        
        # Handle checkout redirect
        if 'add-to-cart-checkout' in request.form:
            return redirect(url_for('shop.cart'))
        
        return redirect(url_for('shop.product', product_id=product_id))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error adding item to cart: {str(e)}')
        flash('حدث خطأ أثناء إضافة المنتج إلى السلة', 'danger')
        return redirect(url_for('shop.product', product_id=product_id))

@shop.route('/cart/update/<int:item_id>', methods=['POST'])
def update_cart(item_id):
    user = Gusts.query.filter_by(session=session['session']).first()
    if not user:
        return jsonify({'success': False, 'message': 'يرجى تحديث الصفحة'}), 400
    cart_item = db.session.get(Cart, item_id)
    if not cart_item:
        abort(404)
    product = db.session.get(Product, cart_item.product_id)
    if not product:
        abort(404)
    
    if not request.json:
        return jsonify({'success': False, 'message': 'بيانات غير صحيحة'}), 400
    new_quantity = request.json.get('quantity')
    if new_quantity is None or not isinstance(new_quantity, int):
        return jsonify({'success': False, 'message': 'الكمية غير صحيحة'}), 400
    
    if not (1 <= new_quantity <= product.stock):
        return jsonify({
            'success': False,
            'message': f'الكمية يجب أن تكون بين 1 و {product.stock}'
        }), 400
    
    cart_item.quantity = new_quantity
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_total': product.price * new_quantity,
        'new_subtotal': sum(item.product.price * item.quantity for item in user.carts)
    })

@shop.route('/cart/remove/<int:item_id>')
def remove_from_cart(item_id):
    user = Gusts.query.filter_by(session=session['session']).first()
    if not user:
        flash('يرجى تحديث الصفحة', 'danger')
        return redirect(url_for('shop.home'))
    cart_item = Cart.query.filter_by(id=item_id, user_id=user.id).first()
    if not cart_item:
        abort(404)
    
    db.session.delete(cart_item)
    db.session.commit()
    flash('تم حذف المنتج من السلة', 'success')
    return redirect(url_for('shop.cart'))
from urllib.parse import quote

@shop.route('/checkout')
def checkout():
    user = Gusts.query.filter_by(session=session['session']).first()
    if not user:
        flash('يرجى تحديث الصفحة', 'danger')
        return redirect(url_for('shop.home'))
    cart_items = Cart.query.filter_by(user_id=user.id).all()
    if not cart_items:
        flash('سلة التسوق فارغة', 'danger')
        return redirect(url_for('shop.cart'))

    subtotal = sum(item.product.price * item.quantity for item in cart_items)

    # Check for promotional discount (10% off)
    promo_info = check_promotional_discount()
    if promo_info['eligible']:
        discount_amount = subtotal * (promo_info['discount_percent'] / 100)
        total = subtotal - discount_amount
    else:
        discount_amount = 0
        total = subtotal

    cities = City.query.all()

    # WhatsApp message generation

    admin_phone = os.getenv('ADMIN_PHONE', '')

    message_lines = ["السلام عليكم، انا عاوز اشتري:"]
    for item in cart_items:
        message_lines.append(f"- {item.product.name} × {item.quantity}")
    message_lines.append("\nمن موقع Al Hamd، وعاوز ادفع بالمحافظ الإلكترونية.")

    full_message = "\n".join(message_lines)
    encoded_message = quote(full_message)
    whatsapp_link = f"https://wa.me/{admin_phone}?text={encoded_message}"

    return render_template(
        'shop/checkout.html',
        cart_items=cart_items,
        total=total,
        subtotal=subtotal,
        promo_info=promo_info,
        discount_amount=discount_amount,
        cities=cities,
        whatsapp_link=whatsapp_link
    )


def handle_fawaterak_payment(order):
    customer_name = order.name.strip().split(maxsplit=1)
    first_name = customer_name[0]
    last_name = customer_name[1] if len(customer_name) > 1 else 'N/A'

    if not all([first_name, last_name, order.phone]):
        flash('البيانات الأساسية للعميل غير مكتملة', 'danger')
        return redirect(url_for('shop.checkout'))

    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
    
    if not shipping_cost:
        flash('تكلفة الشحن غير متوفرة لهذه المدينة', 'danger')
        return redirect(url_for('shop.checkout'))

    cart_items = []
    products_total = 0.0

    # Add shipping cost to cart items and total
    shipping_price = float(shipping_cost.price)
    cart_items.append({
        "name": "Shipping Cost",
        "price": str(round(shipping_price, 2)),
        "quantity": "1"
    })

    # Add product items to cart items and total
    for item in order_items:
        product = db.session.get(Product, item.product_id)
        if product:
            try:
                price = float(product.price)
                quantity = int(item.quantity)
            except (ValueError, TypeError):
                flash('خطأ في بيانات المنتج', 'danger')
                return redirect(url_for('shop.checkout'))

            cart_items.append({
                "name": product.name[:255],
                "price": str(round(price, 2)),
                "quantity": str(quantity)
            })
            products_total += round(price * quantity, 2)

    if not cart_items:
        flash('سلة التسوق فارغة', 'danger')
        return redirect(url_for('shop.checkout'))

    # Apply promotional discount (10% off) if eligible
    promo_info = check_promotional_discount()
    if promo_info['eligible']:
        promo_discount = products_total * (promo_info['discount_percent'] / 100)
        discounted_products_total = products_total - promo_discount
        # Add discount as negative line item for Fawaterak
        cart_items.append({
            "name": "خصم 10% - عرض خاص",
            "price": str(round(-promo_discount, 2)),
            "quantity": "1"
        })
        app.logger.info(f"Promotional discount applied to Fawaterak payment: {promo_discount}")
    else:
        discounted_products_total = products_total

    cart_total = discounted_products_total + shipping_price

    # Prepare the payload for Fawaterak
    payload = {
        "cartTotal": str(round(cart_total, 2)),
        "currency": "EGP",
        "customer": {
            "first_name": first_name[:50],
            "last_name": last_name[:50],
            "email": order.email or "no-email@example.com",
            "phone": ''.join(filter(str.isdigit, order.phone))[:15],
            "address": order.address[:100] if order.address else "N/A"
        },
        "redirectionUrls": {
            "successUrl": url_for('shop.payment_success', order_id=order.id, _external=True),
            "failUrl": url_for('shop.payment_fail', order_id=order.id, _external=True),
            "pendingUrl": url_for('shop.payment_pending', order_id=order.id, _external=True),
            "webhookUrl": url_for('shop.payment_webhook', _external=True)
        },
        "cartItems": cart_items,
        "sendEmail": False,
        "sendSMS": False
    }

    headers = {
        'Authorization': f'Bearer {app.config["FAWATERAK_API_KEY"]}',
        'Content-Type': 'application/json'
    }

    app.logger.debug("Fawaterak Payload:")
    app.logger.debug(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            app.config['FAWATERAK_API_URL'],
            headers=headers,
            json=payload,
            timeout=10
        )

        if not response.ok:
            app.logger.error(f"Fawaterak API Error: {response.status_code} - {response.text}")
            response.raise_for_status()

        fawaterak_data = response.json()
        if fawaterak_data.get('status') != 'success':
            app.logger.error(f"Fawaterak API Error: {fawaterak_data}")
            flash('فشل في إنشاء فاتورة الدفع', 'danger')
            return redirect(url_for('shop.checkout'))

        order.invoice_key = fawaterak_data['data']['invoiceKey']
        order.invoice_id = fawaterak_data['data']['invoiceId']
        order.invoice_url = fawaterak_data['data']['url']
        db.session.commit()

        return redirect(fawaterak_data['data']['url'])

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Fawaterak API Request Failed: {e}")
        flash('فشل في الاتصال بخدمة الدفع، الرجاء المحاولة مرة أخرى', 'danger')
        return redirect(url_for('shop.checkout'))
    
def send_discord_notification(order, order_items):
    """Send professional bilingual order notification to Discord webhook"""
    try:
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL', '')
        if not webhook_url:
            return  # Skip notification if webhook not configured
        
        # Get shipping cost and city info
        shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
        shipping_price = shipping_cost.price if shipping_cost else 0
        city = City.query.filter_by(city_id=order.city).first()
        city_name = city.name if city else "Unknown City"
        
        # Calculate order totals and build product details
        total_amount = 0
        total_items = 0
        product_details_ar = []
        product_details_en = []
        
        # Enhanced product emoji mapping
        product_emojis = {
            'زيت': '🌿', 'oil': '🌿',
            'سبراي': '💨', 'spray': '💨',
            'سيروم': '✨', 'serum': '✨',
            'كريم': '🧴', 'cream': '🧴',
            'شامبو': '🧴', 'shampoo': '🧴',
            'بلسم': '💧', 'conditioner': '💧',
            'ماسك': '🎭', 'mask': '🎭',
            'لوشن': '🧴', 'lotion': '🧴'
        }
        
        for item in order_items:
            product = db.session.get(Product, item.product_id)
            if product:
                item_total = product.price * item.quantity
                total_amount += item_total
                total_items += item.quantity
                
                # Get appropriate emoji for product
                product_emoji = '🛍️'
                product_name_lower = product.name.lower()
                for key, emoji in product_emojis.items():
                    if key in product_name_lower:
                        product_emoji = emoji
                        break
                
                # Arabic product details
                product_details_ar.append(
                    f"{product_emoji} **{product.name}**\n"
                    f"   └ الكمية: `{item.quantity}` × `{product.price:.0f} EGP` = **{item_total:.0f} EGP**"
                )
                
                # English product details
                product_details_en.append(
                    f"{product_emoji} **{product.name}**\n"
                    f"   └ Qty: `{item.quantity}` × `{product.price:.0f} EGP` = **{item_total:.0f} EGP**"
                )
        
        total_with_shipping = total_amount + shipping_price
        
        # Enhanced payment method formatting with better colors
        payment_info = {
            'visa': {'emoji': '💳', 'text_ar': 'بطاقة ائتمان', 'text_en': 'Credit Card', 'color': 0x4285f4},
            'vodafone_cash': {'emoji': '📱', 'text_ar': 'فودافون كاش', 'text_en': 'Vodafone Cash', 'color': 0xe60000},
            'cash_on_delivery': {'emoji': '💵', 'text_ar': 'الدفع عند الاستلام', 'text_en': 'Cash on Delivery', 'color': 0x34a853},
            'cod': {'emoji': '💵', 'text_ar': 'الدفع عند الاستلام', 'text_en': 'Cash on Delivery', 'color': 0x34a853}
        }
        
        payment_method = order.payment_method if order.payment_method in payment_info else 'cod'
        payment = payment_info[payment_method]
        
        # WhatsApp and admin links
        phone_clean = order.phone.replace(" ", "").replace("+", "")
        if not phone_clean.startswith("2"):
            phone_clean = "2" + phone_clean
        whatsapp_link = f"https://wa.me/{phone_clean}"
        admin_url = os.getenv('ADMIN_URL', '/admin/orders')
        
        # Create professional Discord embed with bilingual content
        embed = {
            "title": f"🎉 New Order Received! | طلب جديد وصل! #{order.id}",
            "description": (
                f"### 🌟 A new customer has placed an order for our premium products!\n"
                f"### عميل جديد قام بطلب منتجاتنا المميزة!\n\n"
                f"> 💼 **[Order Management | إدارة الطلبات]({admin_url})**\n"
                f"> 📱 **[WhatsApp Contact | تواصل واتساب]({whatsapp_link})**"
            ),
            "color": payment['color'],
            "fields": [
                {
                    "name": "👤 Customer Information | بيانات العميل",
                    "value": (
                        f"```yaml\n"
                        f"Name     | الاسم    : {order.name}\n"
                        f"Phone    | الهاتف   : {order.phone}\n"
                        f"Email    | الإيميل  : {order.email or 'Not provided | غير متوفر'}\n"
                        f"City     | المدينة  : {city_name}\n"
                        f"Address  | العنوان  : {order.address}\n"
                        f"```"
                    ),
                    "inline": False
                },
                {
                    "name": "🛒 Order Items | منتجات الطلب",
                    "value": "\n".join(product_details_en) if product_details_en else "❌ No products found",
                    "inline": False
                },
                {
                    "name": "💰 Financial Summary | الملخص المالي",
                    "value": (
                        f"```diff\n"
                        f"+ Products Value | قيمة المنتجات: {total_amount:.0f} EGP\n"
                        f"+ Shipping Cost | رسوم الشحن   : {shipping_price:.0f} EGP\n"
                        f"- - - - - - - - - - - - - - - - - - - - - - - -\n"
                        f"= Total Amount  | الإجمالي      : {total_with_shipping:.0f} EGP\n"
                        f"```"
                    ),
                    "inline": True
                },
                {
                    "name": "📊 Order Details | تفاصيل الطلب",
                    "value": (
                        f"{payment['emoji']} **Payment | الدفع:** {payment['text_en']} | {payment['text_ar']}\n"
                        f"📦 **Items Count | عدد القطع:** {total_items}\n"
                        f"🕐 **Time | التوقيت:** {order.created_at.strftime('%d/%m/%Y - %H:%M')}\n"
                        f"🆔 **Order ID | رقم الطلب:** `#{order.id}`\n"
                        f"🏪 **Store | المتجر:** Al Hamd"
                    ),
                    "inline": True
                }
            ],
            "thumbnail": {
                "url": os.getenv('LOGO_URL', '/static/img/logo.png')
            },
            "image": {
                "url": os.getenv('LOGO_URL', '/static/img/logo.png')
            },
            "timestamp": utc_now().isoformat(),
            "footer": {
                "text": "💎 Al Hamd - Premium Products | منتجات مميزة",
                "icon_url": os.getenv('LOGO_URL', '/static/img/logo.png')
            },
            "author": {
                "name": "Order Management System | نظام إدارة الطلبات",
                "icon_url": os.getenv('LOGO_URL', '/static/img/logo.png'),
                "url": admin_url
            }
        }
        
        # Create the complete professional message
        message = {
            "username": "🌟 Al Hamd",
            "avatar_url": "https://k.top4top.io/p_3515e1v1u1.png",
            "content": (
                f"@everyone 🔔 **NEW ORDER ALERT | تنبيه طلب جديد**\n"
                f"📋 **Order #{order.id}** | **Customer:** {order.name} | **Amount:** {total_with_shipping:.0f} EGP\n"
                f"🎯 **Payment:** {payment['text_en']} | {payment['text_ar']}"
            ),
            "embeds": [embed]
        }
        
        # Send to Discord
        response = requests.post(
            webhook_url,
            json=message,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 204:
            app.logger.info(f"Professional Discord notification sent successfully for order #{order.id}")
        else:
            app.logger.error(f"Discord notification failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        app.logger.error(f"Error sending Discord notification: {str(e)}")

@shop.route('/checkout/place_order', methods=['POST'])
def place_order():
    try:
        # 1. Validate required fields
        required_fields = ['name', 'phone', 'address', 'city', 'zone_id', 'district_id', 'total', 'payment_method']
        missing_fields = [field for field in required_fields if field not in request.form]
        if missing_fields:
            flash(f'الحقول التالية مطلوبة: {", ".join(missing_fields)}', 'danger')
            return redirect(url_for('shop.checkout'))

        # 2. Get user and validate cart
        user = Gusts.query.filter_by(session=session['session']).first()
        if not user:
            flash('حدث خطأ في جلسة المستخدم', 'danger')
            return redirect(url_for('shop.checkout'))

        cart_items = Cart.query.filter_by(user_id=user.id).all()
        if not cart_items:
            flash('سلة التسوق فارغة', 'danger')
            return redirect(url_for('shop.cart'))

        # 3. Validate payment method
        payment_method = request.form['payment_method']
        valid_payment_methods = ['cash_on_delivery', 'vodafone_cash', 'visa']
        if payment_method not in valid_payment_methods:
            flash('طريقة الدفع المختارة غير متاحة', 'danger')
            return redirect(url_for('shop.checkout'))

        # 4. Get and validate shipping cost
        shipping_cost = ShippingCost.query.filter_by(city_id=request.form['city']).first()
        if not shipping_cost:
            flash('تكلفة الشحن غير متوفرة لهذه المدينة', 'danger')
            return redirect(url_for('shop.checkout'))

        # 5. Calculate product total server-side (secure calculation)
        product_subtotal = 0
        for item in cart_items:
            product = db.session.get(Product, item.product_id)
            if product:
                product_subtotal += product.price * item.quantity

        # Apply promotional discount (10% off) if eligible
        promo_info = check_promotional_discount()
        if promo_info['eligible']:
            promo_discount = product_subtotal * (promo_info['discount_percent'] / 100)
            product_total = product_subtotal - promo_discount
            app.logger.info(f"Promotional discount applied: {promo_info['discount_percent']}% off - saved {promo_discount}")
        else:
            product_total = product_subtotal

        # 6. Check stock availability
        for cart_item in cart_items:
            product = db.session.get(Product, cart_item.product_id)
            if not product:
                flash(f'المنتج غير موجود', 'danger')
                return redirect(url_for('shop.cart'))
            
            if product.stock < cart_item.quantity:
                flash(f'الكمية المتاحة من {product.name} غير كافية', 'danger')
                return redirect(url_for('shop.cart'))

        # 7. Check for Eid Al-Adha shipping offer first (takes priority)
        eid_offer_info = check_eid_shipping_offer(cart_items, request.form['city'])
        
        # 8. Check for regular shipping discount eligibility
        discount_info = check_shipping_discount(cart_items)
        
        # 9. Calculate shipping cost (with Eid offer or regular discount if applicable)
        if eid_offer_info['eligible']:
            # Apply Eid offer discount
            discount_amount = shipping_cost.price * eid_offer_info['discount']
            shipping_price = shipping_cost.price - discount_amount
            app.logger.info(f"Eid Al-Adha offer applied - discount: {eid_offer_info['discount']*100}%, offer type: {eid_offer_info['offer_type']}")
        elif discount_info['eligible']:
            # Free shipping if regular discount is eligible
            shipping_price = 0
            app.logger.info(f"Free shipping applied for order - discount type: {discount_info['discount_type']}")
        else:
            # Regular shipping cost
            shipping_price = shipping_cost.price

        # 9. Calculate final total
        total_amount = product_total + shipping_price

        # 10. Create order
        order = Order(
            user_id=user.id,
            name=request.form['name'],
            email=request.form.get('email', 'test@gmail.com'),
            phone=request.form['phone'],
            address=request.form['address'],
            city=request.form['city'],
            zone_id=request.form['zone_id'],
            district_id=request.form['district_id'],
            cod_amount=total_amount,  # This now reflects the correct amount with any shipping discount
            payment_method=payment_method,
            status='pending'
        )

        # 11. Add order to session and commit to get the order ID
        db.session.add(order)
        db.session.commit()

        # 12. Create order items and update stock
        order_items = []
        for cart_item in cart_items:
            product = db.session.get(Product, cart_item.product_id)
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity
            )
            order_items.append(order_item)
            db.session.add(order_item)
            
            # Update product stock
            product.stock -= cart_item.quantity
            
            # Delete cart item
            db.session.delete(cart_item)

        # 13. Commit all changes
        db.session.commit()

        # 14. Send Discord notification
        send_discord_notification(order, order_items)

        # 15. Handle payment method
        if payment_method == 'visa':
            return handle_fawaterak_payment(order)

        flash('تم إنشاء الطلب بنجاح!', 'success')
        # if payment method is vodafone cash
        admin_phone = os.getenv('ADMIN_PHONE', '')
        message_lines = ["السلام عليكم، انا عاوز اشتري:"]
        for item in cart_items:
            message_lines.append(f"- {item.product.name} × {item.quantity}")
        message_lines.append("\nمن موقع Al Hamd، وعاوز ادفع بالمحافظ الإلكترونية.")
        full_message = "\n".join(message_lines)
        encoded_message = quote(full_message)
        whatsapp_link = f"https://wa.me/{admin_phone}?text={encoded_message}"
        if payment_method == 'vodafone_cash':
            return redirect(whatsapp_link)
        return redirect(url_for('shop.order_confirmation', order_id=order.id))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error in place_order: {str(e)}')
        flash('حدث خطأ أثناء معالجة الطلب، الرجاء المحاولة مرة أخرى', 'danger')
        return redirect(url_for('shop.checkout'))

# order_confirmation
@shop.route('/order_confirmation')
def order_confirmation():
    # get gusts session
    user = Gusts.query.filter_by(session=session['session']).first()
    if not user:
        flash('يرجى تحديث الصفحة', 'danger')
        return redirect(url_for('shop.home'))
    # get order by user id
    order = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).first()
    if not order:
        flash('لا يوجد طلبات', 'info')
        return redirect(url_for('shop.home'))
    # get order items by order id
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    for item in order_items:
        product = db.session.get(Product, item.product_id)
        item.product = product
    return render_template('shop/order_confirmation.html', order=order, order_items=order_items)

# order_detail
@shop.route('/order_detail')
def order_detail():
    try:
        # get gusts session
        user = Gusts.query.filter_by(session=session['session']).first()
        
        # get order by user id
        order = Order.query.filter_by(user_id=user.id).order_by(Order.id.desc()).first()
        
        # Check if order exists
        if not order:
            flash('لا يوجد طلبات سابقة', 'warning')
            return redirect(url_for('shop.cart'))
        
        # get order items by order id
        shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        
        for item in order_items:
            product = db.session.get(Product, item.product_id)
            item.product = product
            
        productsPrice = 0 
        for item in order_items:
            productsPrice += item.product.price * item.quantity
            
        return render_template('shop/order_detail.html', order=order, order_items=order_items, shipping_cost=shipping_cost, productsPrice=productsPrice)
    
    except Exception as e:
        app.logger.error(f"Error in order_detail: {str(e)}")
        flash('حدث خطأ أثناء عرض تفاصيل الطلب', 'danger')
        return redirect(url_for('shop.cart'))

@shop.route('/payment/success/<int:order_id>')
def payment_success(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    order.payment_status = 'paid'
    db.session.commit()
    user = Gusts.query.filter_by(session=session['session']).first()
    Cart.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    return render_template('shop/payment_success.html', order=order)

@shop.route('/payment/fail/<int:order_id>')
def payment_fail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    # Capture order data before deletion
    order_data = {'id': order.id, 'cod_amount': order.cod_amount}
    db.session.delete(order)
    db.session.commit()
    return render_template('shop/payment_fail.html', order=order_data)


@shop.route('/payment/pending/<int:order_id>')
def payment_pending(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    order.payment_status = 'pending'
    db.session.commit()
    return render_template('shop/payment_pending.html', order=order)


@shop.route('/payment/webhook', methods=['POST'])
def payment_webhook():
    try:
        webhook_secret = os.getenv('PAYMENT_WEBHOOK_SECRET', '')
        if webhook_secret:
            incoming_secret = request.headers.get('X-Webhook-Secret', '')
            if incoming_secret != webhook_secret:
                return jsonify({'status': 'error', 'message': 'Unauthorized webhook'}), 401

        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400

        invoice_key = data.get('invoiceKey')
        status = data.get('status')

        if not invoice_key or not status:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        order = Order.query.filter_by(invoice_key=invoice_key).first()
        if order:
            order.payment_status = status
            if status == 'paid':
                user = db.session.get(Gusts, order.user_id)
                if user:
                    Cart.query.filter_by(user_id=user.id).delete()
            db.session.commit()
            return jsonify({'status': 'success'}), 200

        return jsonify({'status': 'error', 'message': 'Order not found'}), 404

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@shop.route('/api/cities')
def get_cities():
    cities = City.query.all()
    return jsonify(city=[city.serialize() for city in cities])

# /api/zones?city_id=
@shop.route('/api/zones')
def get_zones_api():
    city_id = request.args.get('city_id')
    zones = Zone.query.filter_by(city_id=city_id).all()
    return jsonify(zones=[zone.serialize() for zone in zones])

# /api/districts?city_id=
@shop.route('/api/districts')
def get_districts_api():
    city_id = request.args.get('city_id')
    districts = District.query.filter_by(city_id=city_id).all()
    return jsonify(districts=[district.serialize() for district in districts])

@shop.route('/api/shipping-cost')
def get_shipping_cost_api():    
    city_id = request.args.get('city_id')
    shipping_cost = ShippingCost.query.filter_by(city_id=city_id).first()

    if shipping_cost is None:
        return jsonify(error="Shipping cost not found"), 404  # Return error response

    return jsonify(cost=shipping_cost.price)

@shop.route('/cart')
def cart():
    user = Gusts.query.filter_by(session=session['session']).first()
    if not user:
        flash('يرجى تحديث الصفحة', 'danger')
        return redirect(url_for('shop.home'))
    # Change the query to use correct relationship between Cart and Product
    cart_query_result = db.session.query(Cart, Product).join(Product).filter(Cart.user_id == user.id).all()
    total = sum(item.Product.price * item.Cart.quantity for item in cart_query_result)
    all_last_orders = Order.query.filter_by(user_id=user.id).order_by(Order.id.desc()).limit(10).all()
    cart_items = [
        {
            'id': item.Cart.id,
            'product': item.Product, 
            'quantity': item.Cart.quantity
        } for item in cart_query_result
    ]
    return render_template('shop/cart.html', cart_items=cart_items, total=total, all_last_orders=all_last_orders)

@shop.route('/return-policy')
def return_policy():
    """Return policy page for Google Merchant Center verification"""
    return render_template('shop/return-policy.html')

@shop.route('/about')
def about():
    """About us page"""
    admin_phone = os.getenv('ADMIN_PHONE', '201050188516')
    return render_template('shop/about.html', admin_phone=admin_phone)

# chang-quantity/plus/1
@shop.route('/cart/change-quantity/<action>/<int:item_id>')
def change_quantity(action, item_id):
    user = Gusts.query.filter_by(session=session['session']).first()
    if not user:
        flash('يرجى تحديث الصفحة', 'danger')
        return redirect(url_for('shop.home'))
    cart_item = Cart.query.filter_by(id=item_id, user_id=user.id).first()
    if not cart_item:
        abort(404)
    
    if action == 'plus':
        product = db.session.get(Product, cart_item.product_id)
        if product and cart_item.quantity < product.stock:
            cart_item.quantity += 1
        else:
            flash('الكمية المطلوبة غير متوفرة', 'warning')
    elif action == 'minus':
        cart_item.quantity -= 1
        if cart_item.quantity < 1:
            cart_item.quantity = 1
    
    db.session.commit()
    return redirect(url_for('shop.cart'))
# admin log in
@admin.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            is_admin_created = Admins.query.first()
            if not is_admin_created:
                default_password = os.getenv('ADMIN_PASSWORD', 'admin123')
                new_admin = Admins(
                    name='Admin',
                    email=os.getenv('ADMIN_EMAIL', 'admin@example.com'),
                    password=generate_password_hash(default_password),
                )
                db.session.add(new_admin)
                db.session.commit()
                flash('تم إنشاء حساب المشرف بنجاح!', 'success')
                return redirect(url_for('admin.login'))
            
            email = request.form.get('username')
            password = request.form.get('password')
            
            if not email or not password:
                flash('الرجاء إدخال البريد الإلكتروني وكلمة المرور', 'error')
                return redirect(url_for('admin.login'))
            
            admin = Admins.query.filter_by(email=email).first()
            is_valid_password = False
            if admin:
                is_valid_password = check_password_hash(admin.password, password)

                # Backward compatibility for old plaintext password records
                if not is_valid_password and admin.password == password:
                    admin.password = generate_password_hash(password)
                    db.session.commit()
                    is_valid_password = True

            if admin and is_valid_password:
                session['admin'] = admin.id
                admin.last_login = utc_now()
                db.session.commit()
                return redirect(url_for('admin.home'))
            
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')
            return redirect(url_for('admin.login'))
            
        except Exception as e:
            app.logger.error(f'Login error: {str(e)}')
            flash('حدث خطأ أثناء تسجيل الدخول', 'error')
            return redirect(url_for('admin.login'))
    
    return render_template('admin/login.html')
from functools import wraps
# ...existing code...
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin.login'))


@admin.route('/')
@admin_required
def home():
    try:
        # Get date range from request
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Create base query with date filter if provided
        base_query = Order.query
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                # Add one day to end date to include all records of the end date
                end = end + timedelta(days=1)
                base_query = base_query.filter(Order.created_at.between(start, end))
            except ValueError:
                flash('صيغة التاريخ غير صحيحة', 'error')

        # Initialize all statistics with default values
        products_count = 0
        categories_count = 0
        active_products = 0
        orders_count = 0
        delivered_orders_count = 0
        pending_orders_count = 0
        shipped_orders_count = 0
        returned_orders_count = 0
        total_revenue = 0
        monthly_revenue = 0
        daily_revenue = 0
        total_shipping_cost = 0
        avg_order_value = 0
        customers_count = 0
        new_customers = 0
        repeat_customers = 0
        delivered_orders = []
        pending_orders = []
        
        try:
            # Product and category statistics
            products = Product.query.all()
            products_count = len(products)
            categories_count = Category.query.count()
            active_products = sum(1 for p in products if p.stock > 0)
        except Exception as e:
            app.logger.error(f'Error counting products: {str(e)}')
        
        try:
            # Order statistics using query filters for better performance
            orders_count = Order.query.count()
            delivered_orders = Order.query.filter_by(shipping_status='delivered').all()
            delivered_orders_count = len(delivered_orders)
            pending_orders = Order.query.filter_by(shipping_status='pending').all()
            pending_orders_count = len(pending_orders)
            
            shipped_orders_count = Order.query.filter_by(shipping_status='shipped').count()
            returned_orders_count = Order.query.filter_by(shipping_status='returned').count()
            
            # Update variables used in template
            shipped_orders = shipped_orders_count
            returned_orders = returned_orders_count
        except Exception as e:
            app.logger.error(f'Error calculating order statistics: {str(e)}')
        
        try:
            # Customer statistics
            customers_count = Gusts.query.count()
            new_customers = Gusts.query.filter(
                Gusts.created_at >= datetime.now() - timedelta(days=30)
            ).count()
            
            # Calculate repeat customers
            repeat_customers = db.session.query(Gusts).join(Order).group_by(Gusts.id).having(
                db.func.count(Order.id) > 1
            ).count()
        except Exception as e:
            app.logger.error(f'Error calculating customer statistics: {str(e)}')
        
        try:
            # Calculate revenue statistics for delivered orders
            delivered_query = base_query.filter(
                Order.shipping_status == 'delivered',
                Order.cod_amount.isnot(None)
            )
            
            for order in delivered_query.all():
                try:
                    shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
                    shipping_price = float(shipping_cost.price) if shipping_cost else 0
                    total_shipping_cost += shipping_price
                    
                    order_amount = float(order.cod_amount) if order.cod_amount else 0
                    total_revenue += max(0, order_amount - shipping_price)
                except (ValueError, TypeError, AttributeError) as e:
                    app.logger.error(f'Error processing order {order.id}: {str(e)}')
                    continue
            
            # Calculate average order value
            avg_order_value = total_revenue / delivered_orders_count if delivered_orders_count > 0 else 0
            
            # Calculate monthly and daily revenue
            current_month = datetime.now().month
            current_year = datetime.now().year
            today = datetime.now().date()
            
            for order in delivered_query.all():
                try:
                    shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
                    shipping_price = float(shipping_cost.price) if shipping_cost else 0
                    order_amount = float(order.cod_amount) if order.cod_amount else 0
                    revenue = max(0, order_amount - shipping_price)
                    
                    if order.created_at.date() == today:
                        daily_revenue += revenue
                    if order.created_at.month == current_month and order.created_at.year == current_year:
                        monthly_revenue += revenue
                except Exception as e:
                    app.logger.error(f'Error processing revenue for order {order.id}: {str(e)}')
                    continue
                    
        except Exception as e:
            app.logger.error(f'Error calculating revenue statistics: {str(e)}')

        # Get recent orders with error handling
        try:
            recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        except Exception as e:
            app.logger.error(f'Error fetching recent orders: {str(e)}')
            recent_orders = []
        
        # Initialize chart data
        revenue_chart = {'labels': [], 'data': []}
        orders_chart = {'labels': [], 'data': []}
        
        try:
            # Generate chart data for the last 6 months
            current_date = datetime.now()
            for i in range(6):
                month_date = current_date - timedelta(days=30*i)
                month_name = month_date.strftime('%B')
                
                # Revenue data
                monthly_revenue = db.session.query(db.func.sum(Order.cod_amount)).filter(
                    Order.shipping_status == 'delivered',
                    db.extract('month', Order.created_at) == month_date.month,
                    db.extract('year', Order.created_at) == month_date.year
                ).scalar() or 0
                
                # Orders data
                monthly_orders = Order.query.filter(
                    Order.shipping_status == 'delivered',
                    db.extract('month', Order.created_at) == month_date.month,
                    db.extract('year', Order.created_at) == month_date.year
                ).count()
                
                revenue_chart['labels'].insert(0, month_name)
                revenue_chart['data'].insert(0, monthly_revenue)
                orders_chart['labels'].insert(0, month_name)
                orders_chart['data'].insert(0, monthly_orders)
        except Exception as e:
            app.logger.error(f'Error generating chart data: {str(e)}')
        
        # Get top selling products
        try:
            top_products = db.session.query(
                Product,
                db.func.sum(OrderItem.quantity).label('total_sold')
            ).select_from(Product).join(
                OrderItem, Product.id == OrderItem.product_id
            ).join(
                Order, OrderItem.order_id == Order.id
            ).filter(
                Order.shipping_status == 'delivered'
            ).group_by(Product.id).order_by(
                db.desc('total_sold')
            ).limit(5).all()
        except Exception as e:
            app.logger.error(f'Error fetching top products: {str(e)}')
            top_products = []
        try:
            shipping_status_distribution = db.session.query(
                Order.shipping_status,
                db.func.count(Order.id).label('count')
            ).group_by(Order.shipping_status).all()
        except Exception as e:
            app.logger.error(f'Error fetching shipping status distribution: {str(e)}')
            shipping_status_distribution = []

        return render_template('admin/index.html',
            products_count=products_count,
            categories_count=categories_count,
            active_products=active_products,
            orders_count=orders_count,
            delivered_orders=delivered_orders,
            pending_orders=pending_orders_count,
            shipped_orders=shipped_orders_count,
            returned_orders=returned_orders_count,
            customers_count=customers_count,
            new_customers=new_customers,
            repeat_customers=repeat_customers,
            total_revenue=total_revenue,
            monthly_revenue=monthly_revenue,
            daily_revenue=daily_revenue,
            total_shipping_cost=total_shipping_cost,
            avg_order_value=avg_order_value,
            recent_orders=recent_orders,
            revenue_chart=revenue_chart,
            orders_chart=orders_chart,
            top_products=top_products,
            shipping_status_distribution=shipping_status_distribution)
                            
    except Exception as e:
        app.logger.error(f'Error in admin dashboard: {str(e)}')
        flash('حدث خطأ أثناء تحميل لوحة التحكم', 'error')
        return redirect(url_for('admin.login'))

@admin.route('/add_product', methods=['POST'])
@admin_required
def add_product():
    try:
        # التحقق من الحقول المطلوبة
        if 'name' not in request.form or not request.form['name'].strip():
            flash('اسم المنتج مطلوب', 'error')
            return redirect(request.referrer)
            
        # معالجة البيانات الأساسية
        name = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        
        # Handle empty or invalid price
        price_str = request.form.get('price', '0').strip()
        try:
            price = float(price_str) if price_str else 0
        except ValueError:
            flash('السعر غير صالح', 'error')
            return redirect(request.referrer)
            
        # Handle empty or invalid discount
        discount_str = request.form.get('discount', '0').strip()
        try:
            discount = float(discount_str) if discount_str else 0
        except ValueError:
            flash('نسبة الخصم غير صالحة', 'error')
            return redirect(request.referrer)
            
        # Handle empty or invalid stock
        stock_str = request.form.get('quantity', '0').strip()
        try:
            stock = int(stock_str) if stock_str else 0
        except ValueError:
            flash('الكمية غير صالحة', 'error')
            return redirect(request.referrer)
            
        # Handle empty or invalid category
        category_str = request.form.get('category', '0').strip()
        try:
            category_id = int(category_str) if category_str else 0
        except ValueError:
            flash('التصنيف غير صالح', 'error')
            return redirect(request.referrer)

        # معالجة الصورة الرئيسية
        if 'image' not in request.files:
            flash('الصورة الرئيسية مطلوبة', 'error')
            return redirect(request.referrer)
            
        image_file = request.files['image']
        if image_file.filename == '':
            flash('لم يتم اختيار صورة رئيسية', 'error')
            return redirect(request.referrer)
            
        if not allowed_file(image_file.filename):
            flash('نوع الملف غير مسموح به للصورة الرئيسية', 'error')
            return redirect(request.referrer)
            
        main_image_filename = save_uploaded_file(image_file)

        # إنشاء المنتج
        new_product = Product(
            name=name,
            description=description,
            price=price,
            discount=discount,
            stock=stock,
            image=f"static/uploads/{main_image_filename}",
            category_id=category_id
        )
        db.session.add(new_product)
        db.session.commit()

        # معالجة الصور الإضافية
        additional_images = request.files.getlist('additional_images')
        for file in additional_images:
            if file and allowed_file(file.filename):
                filename = save_uploaded_file(file)
                additional_image = AdditionalImage(
                    image=f"static/uploads/{filename}",
                    product_id=new_product.id
                )
                db.session.add(additional_image)

        db.session.commit()
        flash('تمت إضافة المنتج بنجاح!', 'success')
        return redirect(url_for('admin.products'))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error adding product: {str(e)}')
        flash('حدث خطأ أثناء إضافة المنتج، الرجاء المحاولة مرة أخرى', 'error')
        return redirect(request.referrer)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{uuid4().hex}_{file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        return filename
    return None

@admin.route('/add_category', methods=['POST'])
@admin_required
def add_category():
    try:
        name = request.form.get('name')
        if not name:
            flash('اسم التصنيف مطلوب!', 'error')
            return redirect(url_for('admin.categories'))
            
        # Check if category already exists
        existing_category = Category.query.filter_by(name=name).first()
        if existing_category:
            flash('تصنيف بهذا الاسم موجود بالفعل!', 'error')
            return redirect(url_for('admin.categories'))
            
        description = request.form.get('description', '')
        new_category = Category(name=name, description=description)
        db.session.add(new_category)
        db.session.commit()
        flash('تمت إضافة التصنيف بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding category: {e}")
        flash('حدث خطأ أثناء إضافة التصنيف!', 'error')
        
    return redirect(url_for('admin.categories'))

@admin.route('/products')
@admin_required
def products():
    products = Product.query.all()
    categories = Category.query.all()
    return render_template('admin/products.html', products=products, categories=categories)


@admin.route('/products/missing-images')
@admin_required
def products_missing_images():
    """Show all products that have no real image (missing, placeholder, or empty)"""
    import os as _os
    all_products = Product.query.all()
    missing = []
    for p in all_products:
        img = p.image or ''
        # Consider missing if: empty, points to placeholder, or file doesn't exist on disk
        if (
            not img
            or 'placeholder' in img.lower()
            or img.strip() in ('', 'None')
            or (not img.startswith('http') and not _os.path.exists(_os.path.join(app.root_path, img)))
        ):
            missing.append(p)
    return render_template('admin/products_missing_images.html', products=missing, total=len(all_products))

@admin.route('/delete_product/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    additional_images = AdditionalImage.query.filter_by(product_id=product_id).all()
    additional_data = AdditionalData.query.filter_by(product_id=product_id).all()
    for image in additional_images:
        db.session.delete(image)
    for data in additional_data:
        db.session.delete(data)

    db.session.delete(product)
    db.session.commit()
    flash('تم حذف المنتج بنجاح!', 'success')
    return redirect(url_for('admin.products'))

@admin.route('/product/<int:product_id>/edit', methods=['GET'])
@admin_required
def get_edit_product_form(product_id):
    """Return the edit product form HTML for AJAX loading"""
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    categories = Category.query.all()
    
    return render_template('admin/edit_product.html', product=product, categories=categories)

@admin.route('/edit_product/<int:product_id>', methods=['POST'])
@admin_required
def edit_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    try:
        # Validate required fields
        if not request.form.get('name'):
            flash('اسم المنتج مطلوب!', 'error')
            return redirect(url_for('admin.products'))
        
        if not request.form.get('price'):
            flash('سعر المنتج مطلوب!', 'error')
            return redirect(url_for('admin.products'))
            
        if not request.form.get('quantity'):
            flash('كمية المنتج مطلوبة!', 'error')
            return redirect(url_for('admin.products'))
            
        if not request.form.get('category'):
            flash('تصنيف المنتج مطلوب!', 'error')
            return redirect(url_for('admin.products'))

        # Update product fields
        product.name = request.form['name'].strip()
        product.description = request.form.get('description', '').strip()
        product.price = float(request.form['price'])
        product.discount = float(request.form.get('discount', 0))
        product.stock = int(request.form['quantity'])
        product.category_id = int(request.form['category'])

        # Handle Main Image Upload
        image_file = request.files.get('image')
        if image_file and image_file.filename != '':
            # Validate file type
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            if '.' in image_file.filename and image_file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                filename = secure_filename(image_file.filename)
                # Add timestamp to prevent filename conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                # Store relative path instead of full path
                product.image = f"static/uploads/{filename}"
            else:
                flash('نوع الملف غير مدعوم! يرجى اختيار صورة بصيغة PNG, JPG, JPEG, GIF, أو WEBP', 'error')
                return redirect(url_for('admin.products'))

        # Handle Additional Images Upload
        additional_images = request.files.getlist('additional_images')
        for file in additional_images:
            if file and file.filename != '' and allowed_file(file.filename):
                filename = save_uploaded_file(file)
                if filename:
                    additional_image = AdditionalImage(
                        image=f"static/uploads/{filename}",
                        product_id=product.id
                    )
                    db.session.add(additional_image)

        db.session.commit()
        flash('تم تعديل المنتج بنجاح!', 'success')
    except ValueError as e:
        db.session.rollback()
        flash('خطأ في البيانات المدخلة! تأكد من صحة الأرقام المدخلة.', 'error')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error editing product {product_id}: {str(e)}")
        flash('حدث خطأ أثناء تعديل المنتج!', 'error')
    return redirect(url_for('admin.products'))

@admin.route('/delete_additional_image/<int:image_id>', methods=['POST'])
@admin_required
def delete_additional_image(image_id):
    """Delete an additional product image"""
    try:
        additional_image = db.session.get(AdditionalImage, image_id)
        if not additional_image:
            abort(404)
        
        # Delete the file from filesystem
        try:
            image_path = os.path.join(app.root_path, additional_image.image)
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            app.logger.warning(f"Could not delete image file: {str(e)}")
        
        # Delete from database
        db.session.delete(additional_image)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم حذف الصورة بنجاح'})
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting additional image {image_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ أثناء حذف الصورة'}), 500

@admin.route('/categories', methods=['GET', 'POST'])
@admin_required
def categories():
    try:
        categories = Category.query.order_by(Category.created_at.desc()).all()
        return render_template('admin/categories.html', categories=categories)
    except Exception as e:
        print(f"Error loading categories: {e}")
        flash('حدث خطأ أثناء تحميل التصنيفات!', 'error')
        return render_template('admin/categories.html', categories=[])

@admin.route('/delete_category/<int:category_id>', methods=['POST'])
@admin_required
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        abort(404)
    # Check if category has products
    if category.products:
        flash(f'لا يمكن حذف التصنيف "{category.name}" لأنه يحتوي على {len(category.products)} منتج. قم بنقل المنتجات أولاً.', 'error')
        return redirect(url_for('admin.categories'))
    db.session.delete(category)
    db.session.commit()
    flash('تم حذف القسم بنجاح!', 'success')
    return redirect(url_for('admin.categories'))

@admin.route('/edit_category/<int:category_id>', methods=['POST'])
@admin_required
def edit_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        abort(404)
    try:
        if 'name' in request.form and request.form['name']:
            category.name = request.form['name']
        if 'description' in request.form:
            category.description = request.form['description']
        db.session.commit()
        flash('تم تعديل القسم بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        flash('حدث خطأ أثناء تعديل القسم!', 'error')
    return redirect(url_for('admin.categories'))

# ==================== DROPSHIPPING ROUTES ====================

def scrape_product_data(url):
    """Scrape product data from a given URL using generic selectors"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        # Use final URL after redirects for source_site
        final_url = response.url
        soup = BeautifulSoup(response.text, 'html.parser')
        parsed_url = urlparse(final_url)
        source_site = parsed_url.netloc.replace('www.', '')
        
        # Detect site type for specialized extraction
        is_amazon = 'amazon' in source_site
        is_noon = 'noon.com' in source_site
        is_jumia = 'jumia' in source_site
        
        # ── Extract product name ──
        name = None
        if is_amazon:
            name_selectors = ['#productTitle', '#title span', 'h1#title']
        elif is_noon:
            name_selectors = ['h1[data-qa="pdp-name"]', 'h1.productTitle', 'h1']
        elif is_jumia:
            name_selectors = ['h1.-fs20', 'h1.-pts', 'h1']
        else:
            name_selectors = ['h1', '[itemprop="name"]', '.product-title', '.product_title', '#productTitle']
        
        for selector in name_selectors:
            tag = soup.select_one(selector)
            if tag and tag.get_text(strip=True):
                name = tag.get_text(strip=True)[:300]
                break
        if not name:
            og = soup.find('meta', property='og:title')
            if og:
                name = og.get('content', '')[:300]
        
        # ── Extract price ──
        price = None
        if is_amazon:
            price_selectors = [
                '.a-price .a-offscreen',
                '#priceblock_ourprice', '#priceblock_dealprice',
                '#price_inside_buybox', '.a-price-whole',
                '#corePrice_feature_div .a-offscreen',
                'span.a-price span.a-offscreen',
            ]
        elif is_noon:
            price_selectors = ['strong[data-qa="div-price-now"]', '.priceNow', 'span.price']
        elif is_jumia:
            price_selectors = ['.-b.-ltr', '.-fs24', 'span.-b.-ltr']
        else:
            price_selectors = ['[itemprop="price"]', '.price', '.product-price', '.current-price', 'span.price']
        
        for selector in price_selectors:
            tag = soup.select_one(selector)
            if tag:
                content = tag.get('content') or tag.get_text(strip=True)
                # Remove currency symbols and commas, extract numbers
                cleaned = re.sub(r'[^\d.,]', '', content.replace('٫', '.'))
                nums = re.findall(r'[\d,]+\.?\d*', cleaned.replace(',', ''))
                if nums:
                    try:
                        price = float(nums[0])
                        break
                    except ValueError:
                        pass
        if price is None:
            og = soup.find('meta', property='product:price:amount')
            if og:
                try:
                    price = float(og.get('content', '0'))
                except ValueError:
                    pass
        
        # ── Extract description ──
        description = ''
        if is_amazon:
            desc_selectors = ['#feature-bullets', '#productDescription', '#aplus_feature_div', '[itemprop="description"]']
        elif is_jumia:
            desc_selectors = ['.markup.-mhm.-pvl.-oxa.-sc', '.card-body.-fs14', '[itemprop="description"]']
        else:
            desc_selectors = ['[itemprop="description"]', '.product-description', '#productDescription', '.description']
        
        for selector in desc_selectors:
            tag = soup.select_one(selector)
            if tag:
                description = tag.get_text(strip=True)[:2000]
                break
        if not description:
            og = soup.find('meta', property='og:description')
            if og:
                description = og.get('content', '')[:2000]
        
        # ── Extract main image ──
        image_url = None
        if is_amazon:
            img_selectors = ['#landingImage', '#imgBlkFront', '#main-image-container img', '#imageBlock img']
            for selector in img_selectors:
                tag = soup.select_one(selector)
                if tag:
                    # Amazon stores hi-res in data-old-hires or data-a-dynamic-image
                    image_url = tag.get('data-old-hires') or tag.get('src') or tag.get('data-src')
                    if image_url:
                        image_url = urljoin(final_url, image_url)
                        break
            # Fallback: try extracting from data-a-dynamic-image JSON
            if not image_url:
                tag = soup.select_one('#landingImage, #imgBlkFront')
                if tag and tag.get('data-a-dynamic-image'):
                    try:
                        import json
                        dyn = json.loads(tag['data-a-dynamic-image'])
                        if dyn:
                            image_url = list(dyn.keys())[0]
                    except Exception:
                        pass
        else:
            for selector in ['[itemprop="image"]', '.product-image img', '#main-image', '.gallery-image img', 'img.product-image']:
                tag = soup.select_one(selector)
                if tag:
                    image_url = tag.get('src') or tag.get('data-src') or tag.get('data-lazy')
                    if image_url:
                        image_url = urljoin(final_url, image_url)
                        break
        if not image_url:
            og = soup.find('meta', property='og:image')
            if og:
                image_url = urljoin(final_url, og.get('content', ''))
        
        # ── Extract additional images ──
        additional_imgs = []
        if is_amazon:
            # Amazon stores thumb images in altImages or uses script-based JSON
            gallery_selectors = ['#altImages img', '.imageThumbnail img', '#imageBlock_feature_div img']
        else:
            gallery_selectors = ['.product-gallery img', '.thumbnail img', '[data-gallery] img', '.product-images img']
        
        for selector in gallery_selectors:
            imgs = soup.select(selector)
            if imgs:
                for img in imgs[:10]:
                    src = img.get('data-old-hires') or img.get('src') or img.get('data-src') or img.get('data-lazy')
                    if src:
                        # Skip tiny placeholder images
                        if 'sprite' in src or '1x1' in src or 'grey-pixel' in src:
                            continue
                        # For Amazon thumbs, try to get hi-res by removing size suffix
                        if is_amazon and '_SS' in src:
                            src = re.sub(r'\._[A-Z]{2}\d+_', '.', src)
                        full_url = urljoin(final_url, src)
                        if full_url != image_url and full_url not in additional_imgs:
                            additional_imgs.append(full_url)
                if additional_imgs:
                    break
        
        return {
            'success': True,
            'name': name or 'منتج بدون اسم',
            'price': price or 0,
            'description': description,
            'image_url': image_url or '',
            'additional_images': additional_imgs,
            'source_site': source_site
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'انتهت مهلة الاتصال بالموقع'}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'فشل الاتصال بالموقع'}
    except Exception as e:
        return {'success': False, 'error': f'خطأ: {str(e)}'}


def download_image_from_url(image_url):
    """Download an image from URL and save it locally"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        }
        response = requests.get(image_url, headers=headers, timeout=15, stream=True, allow_redirects=True)
        response.raise_for_status()
        
        # Detect extension from content-type or URL
        content_type = response.headers.get('content-type', '')
        ext = 'jpg'
        if 'png' in content_type:
            ext = 'png'
        elif 'gif' in content_type:
            ext = 'gif'
        elif 'webp' in content_type:
            ext = 'webp'
        elif 'jpeg' not in content_type and 'jpg' not in content_type:
            # Try from URL path
            url_path = urlparse(image_url).path.lower()
            for e in ['png', 'gif', 'webp', 'svg']:
                if url_path.endswith(f'.{e}'):
                    ext = e
                    break
        
        # Verify we actually got an image
        first_chunk = next(response.iter_content(chunk_size=512), None)
        if not first_chunk or len(first_chunk) < 8:
            return None
        
        filename = f"{uuid4().hex}.{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(save_path, 'wb') as f:
            f.write(first_chunk)
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verify file size is reasonable (>1KB for a real image)
        if os.path.getsize(save_path) < 1024:
            os.remove(save_path)
            return None
        
        return filename
    except Exception as e:
        app.logger.error(f'Error downloading image {image_url}: {e}')
        return None


@admin.route('/dropshipping')
@admin_required
def dropshipping():
    items = DropshipProduct.query.order_by(DropshipProduct.created_at.desc()).all()
    categories = Category.query.all()
    return render_template('admin/dropshipping.html', items=items, categories=categories)


@admin.route('/dropshipping/scrape', methods=['POST'])
@admin_required
def dropshipping_scrape():
    url = request.form.get('url', '').strip()
    if not url:
        flash('الرجاء إدخال رابط المنتج', 'error')
        return redirect(url_for('admin.dropshipping'))
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Check if URL already scraped
    existing = DropshipProduct.query.filter_by(source_url=url).first()
    if existing:
        flash('هذا المنتج تم استيراده مسبقاً', 'warning')
        return redirect(url_for('admin.dropshipping'))
    
    result = scrape_product_data(url)
    
    if result['success']:
        item = DropshipProduct(
            source_url=url,
            source_site=result['source_site'],
            name=result['name'],
            price=result['price'],
            description=result['description'],
            image_url=result['image_url'],
            additional_images=json.dumps(result['additional_images']),
            status='pending'
        )
        db.session.add(item)
        db.session.commit()
        flash(f'تم جلب بيانات المنتج "{result["name"]}" بنجاح!', 'success')
    else:
        item = DropshipProduct(
            source_url=url,
            source_site=urlparse(url).netloc,
            status='error',
            error_message=result['error']
        )
        db.session.add(item)
        db.session.commit()
        flash(f'فشل جلب بيانات المنتج: {result["error"]}', 'error')
    
    return redirect(url_for('admin.dropshipping'))


@admin.route('/dropshipping/import/<int:item_id>', methods=['POST'])
@admin_required
def dropshipping_import(item_id):
    item = db.session.get(DropshipProduct, item_id)
    if not item:
        abort(404)
    
    try:
        name = request.form.get('name', item.name).strip()
        price_str = request.form.get('price', str(item.price or 0)).strip()
        price = float(price_str) if price_str else 0
        discount_str = request.form.get('discount', '0').strip()
        discount = float(discount_str) if discount_str else 0
        stock_str = request.form.get('stock', '10').strip()
        stock = int(stock_str) if stock_str else 10
        category_id_str = request.form.get('category_id', '1').strip()
        category_id = int(category_id_str) if category_id_str else 1
        description = request.form.get('description', item.description or '').strip()
        
        # Download main image
        main_image_filename = None
        if item.image_url:
            main_image_filename = download_image_from_url(item.image_url)
        
        if not main_image_filename:
            main_image_filename = 'static/images/placeholder.png'
        else:
            main_image_filename = f"static/uploads/{main_image_filename}"
        
        # Create product
        new_product = Product(
            name=name,
            description=description,
            price=price,
            discount=discount,
            stock=stock,
            image=main_image_filename,
            category_id=category_id
        )
        db.session.add(new_product)
        db.session.commit()
        
        # Download additional images
        if item.additional_images:
            try:
                add_imgs = json.loads(item.additional_images)
                for img_url in add_imgs[:5]:
                    filename = download_image_from_url(img_url)
                    if filename:
                        add_img = AdditionalImage(
                            image=f"static/uploads/{filename}",
                            product_id=new_product.id
                        )
                        db.session.add(add_img)
            except (json.JSONDecodeError, Exception) as e:
                app.logger.error(f'Error processing additional images: {e}')
        
        item.status = 'imported'
        item.imported_product_id = new_product.id
        db.session.commit()
        
        flash(f'تم استيراد المنتج "{name}" بنجاح كمنتج في متجرك!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error importing dropship product: {e}')
        flash(f'حدث خطأ أثناء الاستيراد: {str(e)}', 'error')
    
    return redirect(url_for('admin.dropshipping'))


@admin.route('/dropshipping/delete/<int:item_id>', methods=['POST'])
@admin_required
def dropshipping_delete(item_id):
    item = db.session.get(DropshipProduct, item_id)
    if not item:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash('تم حذف المنتج من قائمة الدروب شوبينج', 'success')
    return redirect(url_for('admin.dropshipping'))


@admin.route('/dropshipping/api/scrape', methods=['POST'])
@admin_required
def dropshipping_api_scrape():
    """AJAX endpoint to scrape product data without saving"""
    data = request.get_json()
    url = data.get('url', '').strip() if data else ''
    
    if not url:
        return jsonify({'success': False, 'error': 'الرجاء إدخال رابط'}), 400
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    result = scrape_product_data(url)
    return jsonify(result)

# ==================== END DROPSHIPPING ROUTES ====================

@admin.route('/shipping')
@admin_required
def shipping():
    try:
        # Get all cities with their related data
        cities = City.query.all()
        
        cities_data = []
        total_cities = len(cities)
        total_zones = 0
        total_districts = 0
        total_shipping_cost = 0.0
        cities_with_shipping = 0
        
        # Process each city and prepare data
        for city in cities:
            try:
                # Get shipping cost for this city
                shipping_cost = ShippingCost.query.filter_by(city_id=city.city_id).first()
                if not shipping_cost:
                    # Create default shipping cost if it doesn't exist
                    shipping_cost = ShippingCost(city_id=city.city_id, price=100)
                    db.session.add(shipping_cost)
                    
                # Count zones and districts with more robust handling
                zones_count = 0
                districts_count = 0
                
                # Handle zones
                if hasattr(city, 'zones') and city.zones is not None:
                    try:
                        if hasattr(city.zones, '__len__'):
                            zones_count = len(city.zones)
                        else:
                            zones_count = city.zones.count() if hasattr(city.zones, 'count') else 0
                    except Exception as zone_error:
                        app.logger.warning(f"Error counting zones for city {city.id}: {zone_error}")
                        zones_count = 0
                
                # Handle districts
                if hasattr(city, 'districts') and city.districts is not None:
                    try:
                        if hasattr(city.districts, '__len__'):
                            districts_count = len(city.districts)
                        else:
                            districts_count = city.districts.count() if hasattr(city.districts, 'count') else 0
                    except Exception as district_error:
                        app.logger.warning(f"Error counting districts for city {city.id}: {district_error}")
                        districts_count = 0
                
                # Safely add to totals
                total_zones += zones_count
                total_districts += districts_count
                
                if shipping_cost and hasattr(shipping_cost, 'price'):
                    total_shipping_cost += float(shipping_cost.price)
                    cities_with_shipping += 1
                
                # Prepare city data
                city_data = {
                    'id': city.id,
                    'name': city.name,
                    'city_id': city.city_id,
                    'created_at': city.created_at,
                    'zones_count': zones_count,
                    'districts_count': districts_count,
                    'zones': [],  # Don't pass the actual relationship objects
                    'districts': [],  # Don't pass the actual relationship objects
                    'shipping_price': float(shipping_cost.price) if shipping_cost and hasattr(shipping_cost, 'price') else 100.0
                }
                cities_data.append(city_data)
                
            except Exception as city_error:
                app.logger.error(f"Error processing city {city.id}: {city_error}")
                # Add basic city data even if there's an error
                city_data = {
                    'id': city.id,
                    'name': getattr(city, 'name', 'Unknown'),
                    'city_id': getattr(city, 'city_id', ''),
                    'created_at': getattr(city, 'created_at', datetime.now()),
                    'zones_count': 0,
                    'districts_count': 0,
                    'zones': [],
                    'districts': [],
                    'shipping_price': 100.0
                }
                cities_data.append(city_data)
        
        # Calculate average shipping cost
        avg_shipping_cost = total_shipping_cost / cities_with_shipping if cities_with_shipping > 0 else 0.0
        
        # Prepare statistics
        stats = {
            'total_cities': total_cities,
            'total_zones': total_zones,
            'total_districts': total_districts,
            'avg_shipping_cost': avg_shipping_cost
        }
        
        db.session.commit()
        return render_template('admin/shipping.html', cities=cities_data, stats=stats)
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error in shipping route: {str(e)}')
        import traceback
        app.logger.error(f'Full traceback: {traceback.format_exc()}')
        flash('حدث خطأ أثناء تحميل صفحة الشحن', 'error')
        return redirect(url_for('admin.home'))

@admin.route('/delete_city/<int:id>')
@admin_required
def delete_city(id):
    try:
        city = db.session.get(City, id)
        if not city:
            abort(404)
        
        # Delete associated shipping costs
        ShippingCost.query.filter_by(city_id=city.city_id).delete()
        
        # Delete associated zones
        Zone.query.filter_by(city_id=city.city_id).delete()
        
        # Delete associated districts
        District.query.filter_by(city_id=city.city_id).delete()
        
        # Delete the city
        db.session.delete(city)
        db.session.commit()
        
        flash('تم حذف المدينة بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting city: {str(e)}')
        flash('حدث خطأ أثناء حذف المدينة', 'error')
        
    return redirect(url_for('admin.shipping'))

@admin.route('/update_shipping_cost', methods=['POST'])
@admin_required
def update_shipping_cost():
    try:
        city_id = request.form.get('city_id')
        price = float(request.form.get('price', 0))
        
        if not city_id:
            flash('معرف المدينة مطلوب', 'error')
            return redirect(url_for('admin.shipping'))
            
        # Get or create shipping cost
        shipping_cost = ShippingCost.query.filter_by(city_id=city_id).first()
        if not shipping_cost:
            shipping_cost = ShippingCost(city_id=city_id, price=price)
            db.session.add(shipping_cost)
        else:
            shipping_cost.price = price
            
        db.session.commit()
        flash('تم تحديث تكلفة الشحن بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating shipping cost: {str(e)}')
        flash('حدث خطأ أثناء تحديث تكلفة الشحن', 'error')
        
    return redirect(url_for('admin.shipping'))

@admin.route('/orders')
@admin_required
def orders():
    try:
        # Get page parameter from the request, default to 1 if not provided
        page = request.args.get('page', 1, type=int)
        per_page = 12  # Show 12 orders per page for better grid layout
        
        # Get filter parameters from request
        search = request.args.get('search', '')
        status_filter = request.args.get('status', '')
        payment_filter = request.args.get('payment', '')
        shipping_filter = request.args.get('shipping', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        # Create a base query for orders with descending order by ID
        base_query = Order.query.order_by(Order.id.desc())
        
        # Apply filters to the base query
        if search:
            search_term = f"%{search}%"
            base_query = base_query.filter(
                or_(
                    Order.name.ilike(search_term),
                    Order.phone.ilike(search_term),
                    Order.id.in_([int(search) if search.isdigit() else 0])
                )
            )
        
        if status_filter:
            base_query = base_query.filter(Order.status == status_filter)
            
        if payment_filter:
            base_query = base_query.filter(Order.payment_method == payment_filter)
            
        if shipping_filter:
            base_query = base_query.filter(Order.shipping_status == shipping_filter)
        
        # Apply date range filters
        if start_date and end_date:
            try:
                # Convert dates to datetime objects
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                # Add one day to end date to include all records of the end date
                end = end + timedelta(days=1)
                base_query = base_query.filter(Order.created_at.between(start, end))
            except ValueError:
                # If date parsing fails, ignore the date filter
                app.logger.warning(f"Invalid date format: start_date={start_date}, end_date={end_date}")
        elif start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                base_query = base_query.filter(Order.created_at >= start)
            except ValueError:
                app.logger.warning(f"Invalid date format: start_date={start_date}")
        elif end_date:
            try:
                end = datetime.strptime(end_date, '%Y-%m-%d')
                # Add one day to end date to include all records of the end date
                end = end + timedelta(days=1)
                base_query = base_query.filter(Order.created_at <= end)
            except ValueError:
                app.logger.warning(f"Invalid date format: end_date={end_date}")
        
        # Get total count of filtered orders for stats
        total_filtered = base_query.count()
        
        # Apply pagination
        paginated_orders = base_query.paginate(page=page, per_page=per_page, error_out=False)
        orders = paginated_orders.items
        
        # Add additional information to each order
        for order in orders:
            # Get city information
            city = City.query.filter_by(city_id=order.city).first()
            order.city_name = city.name if city else "غير معروف"
            
            # Get order items count
            order.items_count = OrderItem.query.filter_by(order_id=order.id).count()
            
            # Get shipping status display name
            shipping_statuses = {
                'pending': 'قيد الانتظار',
                'shipped': 'تم الشحن',
                'delivered': 'تم التوصيل',
                'cancelled': 'ملغي',
                'returned': 'تم الإرجاع'
            }
            order.shipping_status_display = shipping_statuses.get(order.shipping_status, order.shipping_status)
            
            # Get payment status display name
            payment_statuses = {
                'pending': 'قيد الانتظار',
                'paid': 'تم الدفع',
                'failed': 'فشل الدفع',
                'refunded': 'تم الاسترجاع'
            }
            order.payment_status_display = payment_statuses.get(order.payment_status, order.payment_status)
            
            # Get payment method display name
            payment_methods = {
                'cash_on_delivery': 'الدفع عند الاستلام',
                'vodafone_cash': 'فودافون كاش',
                'visa': 'الدفع بالفيزا'
            }
            order.payment_method_display = payment_methods.get(order.payment_method, order.payment_method)
        
        # Get filter options for dropdowns
        payment_options = [
            {'value': 'cash_on_delivery', 'label': 'الدفع عند الاستلام'},
            {'value': 'vodafone_cash', 'label': 'فودافون كاش'},
            {'value': 'visa', 'label': 'فيزا / ماستركارد'}
        ]
        
        status_options = [
            {'value': 'pending', 'label': 'قيد الانتظار'},
            {'value': 'completed', 'label': 'مكتمل'},
            {'value': 'cancelled', 'label': 'ملغي'}
        ]
        
        shipping_options = [
            {'value': 'pending', 'label': 'قيد الانتظار'},
            {'value': 'shipped', 'label': 'تم الشحن'},
            {'value': 'delivered', 'label': 'تم التوصيل'},
            {'value': 'returned', 'label': 'تم الإرجاع'},
            {'value': 'cancelled', 'label': 'ملغي'}
        ]
        
        return render_template('admin/orders.html', 
                               orders=orders, 
                               pagination=paginated_orders,
                               total_filtered=total_filtered,
                               filters={
                                   'search': search,
                                   'status': status_filter,
                                   'payment': payment_filter,
                                   'shipping': shipping_filter,
                                   'start_date': start_date,
                                   'end_date': end_date
                               },
                               options={
                                   'payment': payment_options,
                                   'status': status_options,
                                   'shipping': shipping_options
                               })
        
    except Exception as e:
        app.logger.error(f'Error in orders route: {str(e)}')
        flash('حدث خطأ أثناء تحميل قائمة الطلبات', 'error')
        return redirect(url_for('admin.home'))

@admin.route('/order/<int:order_id>')
@admin_required
def order_detail(order_id):
    try:
        # Get the order record or return a 404 if not found
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        
        # Get city information
        city = City.query.filter_by(city_id=order.city).first()
        city_name = city.name if city else "غير معروف"
        
        # Get shipping cost
        shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
        shipping_price = shipping_cost.price if shipping_cost else 0
        
        # Get order items with product details
        order_items_with_product = (
            db.session.query(OrderItem, Product)
            .join(Product, OrderItem.product_id == Product.id)
            .filter(OrderItem.order_id == order_id)
            .all()
        )
        
        # Calculate order totals
        subtotal = 0
        order_items = []
        for order_item, product in order_items_with_product:
            item_total = product.price * order_item.quantity
            subtotal += item_total
            
            item_data = {
                'order_item': order_item,
                'product': {
                    'id': product.id,
                    'image': product.image,
                    'name': product.name,
                    'price': product.price,
                    'stock': product.stock,
                    'category': product.category.name if product.category else "غير معروف"
                },
                'item_total': item_total
            }
            order_items.append(item_data)
        
        # Calculate final totals
        total_amount = subtotal + shipping_price
        
        # Get payment method display name
        payment_methods = {
            'cash_on_delivery': 'الدفع عند الاستلام',
            'vodafone_cash': 'فودافون كاش',
            'visa': 'الدفع بالفيزا'
        }
        payment_method_display = payment_methods.get(order.payment_method, order.payment_method)
        
        # Get shipping status display name
        shipping_statuses = {
            'pending': 'قيد الانتظار',
            'shipped': 'تم الشحن',
            'delivered': 'تم التوصيل',
            'cancelled': 'ملغي'
        }
        shipping_status_display = shipping_statuses.get(order.shipping_status, order.shipping_status)
        
        # Get payment status display name
        payment_statuses = {
            'pending': 'قيد الانتظار',
            'paid': 'تم الدفع',
            'failed': 'فشل الدفع',
            'refunded': 'تم الاسترجاع'
        }
        payment_status_display = payment_statuses.get(order.payment_status, order.payment_status)
        
        # Prepare order summary
        order_summary = {
            'subtotal': subtotal,
            'shipping_cost': shipping_price,
            'total_amount': total_amount,
            'items_count': len(order_items),
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'payment_method': payment_method_display,
            'shipping_status': shipping_status_display,
            'payment_status': payment_status_display,
            'tracking_number': order.tracking_number or 'غير متوفر',
            'business_reference': order.business_reference or 'غير متوفر'
        }
        
        # Get all available products for adding new items
        available_products = Product.query.filter(Product.stock > 0).all()
        
        return render_template('admin/order.html',
                             order=order,
                             order_items=order_items,
                             order_summary=order_summary,
                             available_products=available_products,
                             city_name=city_name,
                             shipping_cost=shipping_cost)
                             
    except Exception as e:
        app.logger.error(f'Error in order_detail: {str(e)}')
        flash('حدث خطأ أثناء تحميل تفاصيل الطلب', 'error')
        return redirect(url_for('admin.orders'))

@admin.route('/add_item_to_order/<int:order_id>', methods=['POST'])
@admin_required
def add_item_to_order(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity', 1))
        
        if not product_id:
            flash('الرجاء اختيار منتج', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)
        
        # Validate stock
        if quantity > product.stock:
            flash('الكمية المطلوبة غير متوفرة في المخزون', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        # Check if item already exists in order
        existing_item = OrderItem.query.filter_by(
            order_id=order_id,
            product_id=product_id
        ).first()
        
        if existing_item:
            # Update existing item
            existing_item.quantity += quantity
        else:
            # Create new item
            order_item = OrderItem(
                order_id=order_id,
                product_id=product_id,
                quantity=quantity
            )
            db.session.add(order_item)
        
        # Update order total
        order.cod_amount += product.price * quantity
        
        # Update product stock
        product.stock -= quantity
        
        db.session.commit()
        flash('تمت إضافة المنتج إلى الطلب بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error adding item to order: {str(e)}')
        flash('حدث خطأ أثناء إضافة المنتج إلى الطلب', 'error')
        
    return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/delete_item_from_order/<int:order_id>/<int:item_id>', methods=['POST'])
@admin_required
def delete_item_from_order(order_id, item_id):
    try:
        order_item = db.session.get(OrderItem, item_id)
        if not order_item:
            abort(404)
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        product = db.session.get(Product, order_item.product_id)
        if not product:
            abort(404)
        
        # Validate order item belongs to order
        if order_item.order_id != order_id:
            flash('عنصر الطلب غير موجود', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
        
        # Update order total
        order.cod_amount -= product.price * order_item.quantity
        
        # Restore product stock
        product.stock += order_item.quantity
        
        # Delete order item
        db.session.delete(order_item)
        db.session.commit()
        
        flash('تم حذف المنتج من الطلب بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting item from order: {str(e)}')
        flash('حدث خطأ أثناء حذف المنتج من الطلب', 'error')
        
    return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/update_shipping_status/<int:order_id>', methods=['POST'])
@admin_required
def update_shipping_status(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        status = request.form.get('status')
        
        if not status:
            flash('حالة الشحن مطلوبة', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        valid_statuses = ['pending', 'shipped', 'delivered', 'cancelled', 'returned']
        if status not in valid_statuses:
            flash('حالة الشحن غير صالحة', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        order.shipping_status = status
        db.session.commit()
        
        flash('تم تحديث حالة الشحن بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating shipping status: {str(e)}')
        flash('حدث خطأ أثناء تحديث حالة الشحن', 'error')
        
    return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/delete_order/<int:order_id>', methods=['POST'])
@admin_required
def delete_order(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        
        # Restore product stock
        order_items = OrderItem.query.filter_by(order_id=order_id).all()
        for item in order_items:
            product = db.session.get(Product, item.product_id)
            if product:
                product.stock += item.quantity
        
        # Delete order items
        OrderItem.query.filter_by(order_id=order_id).delete()
        
        # Delete order
        db.session.delete(order)
        db.session.commit()
        
        flash('تم حذف الطلب بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting order: {str(e)}')
        flash('حدث خطأ أثناء حذف الطلب', 'error')
        
    return redirect(url_for('admin.orders'))

@admin.route('/export_orders')
@admin_required
def export_orders():
    try:
        # Get all orders with their items
        orders = Order.query.order_by(Order.id.desc()).all()
        
        data = []
        for order in orders:
            order_items = db.session.query(OrderItem, Product).join(Product, OrderItem.product_id == Product.id).filter(OrderItem.order_id == order.id).all()
            total_quantity = sum(item.OrderItem.quantity for item in order_items)
            product_names = ', '.join([item.Product.name for item in order_items if item.Product])
            city = City.query.filter_by(city_id=order.city).first()
            city_name = city.name if city else 'Unknown'
            
            # Prepare order data
            order_data = {
                'اسم العميل': order.name,
                'تليفون (محمول فقط)': order.phone,
                'المدينة': city_name,
                'المنطقة': order.zone_id,
                'العنوان': order.address,
                'قيمة التحصيل النقدي': order.cod_amount,
                'عدد القطع': total_quantity,
                'وصف الشحنة': product_names,
                'مرجع الطلب': order.business_reference or '',
                'قيمة الشحنة': order.cod_amount
            }
            data.append(order_data)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create the file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='الطلبات')
        
        output.seek(0)
        
        # Send the file as a response
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='الطلبات.xlsx'
        )
        
    except Exception as e:
        app.logger.error(f'Error exporting orders: {str(e)}')
        flash('حدث خطأ أثناء تصدير الطلبات', 'error')
        return redirect(url_for('admin.orders'))

@admin.route('/export_selected_orders', methods=['POST'])
@admin_required
def export_selected_orders():
    try:
        selected_order_ids = request.form.getlist('order_ids')
        if not selected_order_ids:
            flash('الرجاء اختيار طلبات للتصدير', 'error')
            return redirect(url_for('admin.orders'))
            
        order_ids = [int(order_id) for order_id in selected_order_ids]
        orders = Order.query.filter(Order.id.in_(order_ids)).all()
        
        data = []
        for order in orders:
            order_items = db.session.query(OrderItem, Product).join(Product, OrderItem.product_id == Product.id).filter(OrderItem.order_id == order.id).all()
            total_quantity = sum(item.OrderItem.quantity for item in order_items)
            product_names = ', '.join([item.Product.name for item in order_items if item.Product])
            city = City.query.filter_by(city_id=order.city).first()
            city_name = city.name if city else 'Unknown'
            
            # Prepare order data
            order_data = {
                'اسم العميل': order.name,
                'تليفون (محمول فقط)': order.phone,
                'المدينة': city_name,
                'المنطقة': order.zone_id,
                'العنوان': order.address,
                'قيمة التحصيل النقدي': order.cod_amount,
                'عدد القطع': total_quantity,
                'وصف الشحنة': product_names,
                'مرجع الطلب': order.business_reference or '',
                'قيمة الشحنة': order.cod_amount
            }
            data.append(order_data)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create the file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='الطلبات')
        
        output.seek(0)
        
        # Send the file as a response
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='الطلبات المحددة.xlsx'
        )
        
    except Exception as e:
        app.logger.error(f'Error exporting selected orders: {str(e)}')
        flash('حدث خطأ أثناء تصدير الطلبات المحددة', 'error')
        return redirect(url_for('admin.orders'))

@admin.route('/order/<int:order_id>/ship', methods=['POST'])
@admin_required
def ship_order(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        
        # Check if order is already shipped
        if order.shipping_status == 'shipped':
            flash('تم شحن هذا الطلب بالفعل', 'warning')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        # Check if order is cancelled
        if order.shipping_status == 'cancelled':
            flash('لا يمكن شحن طلب ملغي', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        # Update shipping status
        order.shipping_status = 'shipped'
        
        # Generate tracking number if not exists
        if not order.tracking_number:
            order.tracking_number = f"TRK-{utc_now().strftime('%Y%m%d%H%M%S')}-{order.id}"
        
        # Generate business reference if not exists
        if not order.business_reference:
            order.business_reference = f"ORD-{utc_now().strftime('%Y%m%d%H%M%S')}-{order.id}"
        
        db.session.commit()
        
        flash('تم تحديث حالة الشحن بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error shipping order: {str(e)}')
        flash('حدث خطأ أثناء تحديث حالة الشحن', 'error')
        
    return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/admin/order/<int:order_id>/update-shipping-price', methods=['POST'])
@admin_required
def update_order_shipping_price(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        new_shipping_price = float(request.form.get('shipping_price', 0))
        
        if new_shipping_price < 0:
            flash('تكلفة الشحن يجب أن تكون رقم موجب', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
        
        # Get or create shipping cost for the city
        shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
        if not shipping_cost:
            shipping_cost = ShippingCost(city_id=order.city, price=new_shipping_price)
            db.session.add(shipping_cost)
        else:
            shipping_cost.price = new_shipping_price
        
        # Update only the shipping cost, don't recalculate the total
        # This preserves any existing discounts
        order.shipping_cost = new_shipping_price
        
        db.session.commit()
        
        flash('تم تحديث تكلفة الشحن بنجاح', 'success')
        return redirect(url_for('admin.order_detail', order_id=order_id))
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء تحديث تكلفة الشحن', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/admin/order/<int:order_id>/update-cod-amount', methods=['POST'])
@admin_required
def update_order_cod_amount(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        new_cod_amount = float(request.form.get('cod_amount', 0))
        
        if new_cod_amount < 0:
            flash('المبلغ الكلي يجب أن يكون رقم موجب', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
        
        # Update COD amount
        order.cod_amount = new_cod_amount
        db.session.commit()
        
        flash('تم تحديث المبلغ الكلي بنجاح', 'success')
        return redirect(url_for('admin.order_detail', order_id=order_id))
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء تحديث المبلغ الكلي', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/order/<int:order_id>/update-status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        status = request.form.get('status')
        
        if not status:
            flash('حالة الطلب مطلوبة', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        valid_statuses = ['pending', 'completed', 'cancelled']
        if status not in valid_statuses:
            flash('حالة الطلب غير صالحة', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        order.status = status
        db.session.commit()
        
        flash('تم تحديث حالة الطلب بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating order status: {str(e)}')
        flash('حدث خطأ أثناء تحديث حالة الطلب', 'error')
        
    return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/test-db')
def test_db():
    try:
        # Test basic database connectivity
        db.session.execute(sa_text('SELECT 1'))
        
        # Test if required tables exist
        tables = {
            'Admins': Admins.query.first(),
            'Product': Product.query.first(),
            'Order': Order.query.first(),
            'Category': Category.query.first(),
            'City': City.query.first(),
            'ShippingCost': ShippingCost.query.first()
        }
        
        results = {
            'database_connection': 'success',
            'tables': {table: 'exists' if result else 'missing' for table, result in tables.items()}
        }
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'database_connection': 'failed'
        }), 500

@shop.route('/get_zones/<string:city_id>')
def get_zones(city_id):
    try:
        zones = Zone.query.filter_by(city_id=city_id).all()
        return jsonify(zones=[zone.serialize() for zone in zones])
    except Exception as e:
        app.logger.error(f"Error fetching zones: {str(e)}")
        return jsonify({'error': 'Failed to fetch zones'}), 500


@shop.route('/get_districts/<string:city_id>')
def get_districts(city_id):
    try:
        # First find the city by its city_id string
        city = City.query.filter_by(city_id=city_id).first()
        if not city:
            app.logger.error(f"City not found with city_id: {city_id}")
            return jsonify({'error': 'City not found'}), 404
            
        # Then get districts for this city
        districts = District.query.filter_by(city_id=city_id).all()
        app.logger.info(f"Found {len(districts)} districts for city_id: {city_id}")
        
        # Debug the districts data
        for district in districts:
            app.logger.info(f"District: id={district.id}, name={district.name}, city_id={district.city_id}")
            
        # Return districts in the format expected by the frontend
        return jsonify(districts=[district.serialize() for district in districts])
        
    except Exception as e:
        app.logger.error(f"Error fetching districts: {str(e)}")
        return jsonify({'error': 'Failed to fetch districts'}), 500

@shop.route('/get_shipping_cost/<string:city_id>')
def get_shipping_cost(city_id):
    try:
        city = City.query.filter_by(city_id=city_id).first()
        if not city:
            return jsonify({'error': 'City not found'}), 404
        
        # Get cart items to check for discounts
        user = Gusts.query.filter_by(session=session['session']).first()
        cart_items = Cart.query.filter_by(user_id=user.id).all()
        
        # Check for Eid Al-Adha offer first
        eid_offer_info = check_eid_shipping_offer(cart_items, city_id)
        
        # Check if the order qualifies for regular free shipping
        discount_info = check_shipping_discount(cart_items)
        
        # Get standard shipping cost
        shipping_cost = ShippingCost.query.filter_by(city_id=city.city_id).first()
        if not shipping_cost:
            # Return default shipping cost if not found
            standard_cost = 80
        else:
            standard_cost = shipping_cost.price
        
        # Apply Eid offer if eligible (takes priority over regular discounts)
        if eid_offer_info['eligible']:
            discount_amount = standard_cost * eid_offer_info['discount']
            final_cost = standard_cost - discount_amount
            discount_message = eid_offer_info['message']
            discount_applied = True
        # Apply regular discount if eligible and no Eid offer
        elif discount_info['eligible']:
            # Free shipping
            final_cost = 0
            discount_message = ""
            if discount_info['discount_type'] == "combo_1_2_3":
                discount_message = "Free shipping - Special offer for products #1, #2, and #3"
            discount_applied = True
        else:
            final_cost = standard_cost
            discount_message = None
            discount_applied = False
        
        return jsonify({
            'shipping_cost': final_cost,
            'standard_cost': standard_cost,
            'discount_applied': discount_applied,
            'discount_message': discount_message,
            'eid_offer_active': eid_offer_info.get('offer_active', False),
            'eid_offer_type': eid_offer_info.get('offer_type', None)
        })
        
    except Exception as e:
        app.logger.error(f"Error fetching shipping cost: {str(e)}")
        return jsonify({'error': 'Failed to fetch shipping cost'}), 500

@shop.route('/debug/cities')
def debug_cities():
    try:
        cities = City.query.all()
        return jsonify({
            'cities': [{'id': city.id, 'city_id': city.city_id, 'name': city.name} for city in cities]
        })
    except Exception as e:
        app.logger.error(f"Error fetching cities: {str(e)}")
        return jsonify({'error': 'Failed to fetch cities'}), 500


@admin.route('/export_income_stats', methods=['GET'])
@admin_required
def export_income_stats():
    try:
        # Get date range from request
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Base query for orders
        query = Order.query.filter(
            or_(
                Order.shipping_status == 'delivered',
                Order.shipping_status == 'returned'
            )
        )
        
        # Apply date filter if provided
        if (start_date and end_date):
            try:
                # Convert dates to datetime objects
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                # Add one day to end date to include the full day
                end = end + timedelta(days=1)
                query = query.filter(Order.created_at.between(start, end))
            except ValueError as e:
                app.logger.error(f'Error parsing dates: {str(e)}')
                flash('خطأ في تنسيق التواريخ', 'error')
                return redirect(url_for('admin.home'))
        
        # Define product costs
        product_costs = {
            'زيت': 140,
            'سبراي': 140,
            'سيروم الرموش': 35
        }

        # Get all orders
        orders = query.all()
        
        data = []
        total_cash_collection = 0
        total_shipping_cost = 0
        total_manufacturing_cost = 0
        total_net = 0
        delivered_count = 0
        returned_count = 0

        # Initialize product stats
        product_stats = {}
        
        for order in orders:
            # Get shipping cost for the order
            shipping_cost = ShippingCost.query.filter_by(city_id=order.city).first()
            shipping_price = shipping_cost.price if shipping_cost else 0
            
            # Calculate manufacturing cost (20 per order)
            manufacturing_cost = 20
            
            # Calculate net amount based on order status
            if order.shipping_status == 'delivered':
                cash_collection = float(order.cod_amount) if order.cod_amount else 0
                net_amount = cash_collection - shipping_price - manufacturing_cost
                delivered_count += 1

                # Process product details for delivered orders only
                order_items = (
                    db.session.query(OrderItem, Product)
                    .join(Product, OrderItem.product_id == Product.id)
                    .filter(OrderItem.order_id == order.id)
                    .all()
                )
                
                for item in order_items:
                    product_name = item.Product.name
                    quantity = item.OrderItem.quantity
                    
                    if product_name not in product_stats:
                        product_stats[product_name] = {
                            'quantity': 0,
                            'revenue': 0,
                            'cost': 0
                        }
                    
                    product_stats[product_name]['quantity'] += quantity
                    product_stats[product_name]['revenue'] += quantity * float(item.Product.price)
                    production_cost = product_costs.get(product_name, 0)
                    product_stats[product_name]['cost'] += quantity * production_cost

            else:  # returned
                cash_collection = 0
                net_amount = -shipping_price - manufacturing_cost  # Subtract both shipping and manufacturing costs
                returned_count += 1
            
            # Add to totals
            total_cash_collection += cash_collection
            total_shipping_cost += shipping_price
            total_manufacturing_cost += manufacturing_cost
            total_net += net_amount
            
            # Prepare order data
            order_data = {
                'اسم العميل': order.name,
                'تليفون (محمول فقط)': order.phone,
                'قيمة التحصيل النقدي': cash_collection,
                'قيمه الشحن': shipping_price,
                'تكلفة التصنيع': manufacturing_cost,
                'صافي': net_amount,
                'الحالة': 'تم التوصيل' if order.shipping_status == 'delivered' else 'مرتجع',
                'التاريخ': order.created_at.strftime('%Y-%m-%d %H:%M')
            }
            data.append(order_data)

        # Add summary row
        summary = {
            'اسم العميل': '',
            'تليفون (محمول فقط)': '',
            'قيمة التحصيل النقدي': '',
            'قيمه الشحن': '',
            'تكلفة التصنيع': '',
            'صافي': '',
            'الحالة': '',
            'التاريخ': ''
        }
        data.append(summary)
        
        # Add statistics row
        stats = {
            'اسم العميل': f'عدد الطلبات الموصلة: {delivered_count}',
            'تليفون (محمول فقط)': f'عدد الطلبات المرتجعة: {returned_count}',
            'قيمة التحصيل النقدي': f'اجمالي المستحق: {total_cash_collection}',
            'قيمه الشحن': f'اجمالي مصاريف الشحن: {total_shipping_cost}',
            'تكلفة التصنيع': f'اجمالي تكلفة التصنيع: {total_manufacturing_cost}',
            'صافي': f'صافي المستحق: {total_net}',
            'الحالة': '',
            'التاريخ': ''
        }
        data.append(stats)

        # Create DataFrame for orders
        df = pd.DataFrame(data)
        
        # Create DataFrame for product statistics
        product_data = []
        for product_name, stats in product_stats.items():
            product_row = {
                'المنتج': product_name,
                'الكمية المباعة': stats['quantity'],
                'الإيرادات': stats['revenue'],
                'تكلفة الإنتاج': stats['cost'],
                'صافي الربح': stats['revenue'] - stats['cost']
            }
            product_data.append(product_row)

        df_products = pd.DataFrame(product_data)
        
        # Create the file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Write orders sheet
            df.to_excel(writer, index=False, sheet_name='إحصائيات الدخل')
            
            # Write products sheet
            df_products.to_excel(writer, index=False, sheet_name='إحصائيات المنتجات')
            
            # Format orders sheet
            worksheet = writer.sheets['إحصائيات الدخل']
            
            # Set column widths for orders
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
            
            # Format the last two rows (summary and stats)
            for row in range(len(df) - 1, len(df) + 1):
                for col in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=row, column=col)
                    cell.font = cell.font.copy(bold=True)
                    if row == len(df):  # Stats row
                        cell.fill = cell.fill.copy(fill_type='solid', fgColor='F2F2F2')

            # Format products sheet
            worksheet_products = writer.sheets['إحصائيات المنتجات']
            
            # Set column widths for products
            for idx, col in enumerate(df_products.columns):
                max_length = max(
                    df_products[col].astype(str).apply(len).max(),
                    len(str(col))
                )
                worksheet_products.column_dimensions[chr(65 + idx)].width = max_length + 2
            
            # Format header row
            for col in range(1, len(df_products.columns) + 1):
                cell = worksheet_products.cell(row=1, column=col)
                cell.font = cell.font.copy(bold=True)
                cell.fill = cell.fill.copy(fill_type='solid', fgColor='F2F2F2')
        
        output.seek(0)
        
        # Send the file as a response
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='إحصائيات الدخل.xlsx'
        )
        
        return redirect(url_for('admin.home'))
        
    except Exception as e:
        app.logger.error(f'Error exporting income statistics: {str(e)}')
        flash('حدث خطأ أثناء تصدير إحصائيات الدخل', 'error')
        return redirect(url_for('admin.home'))

@admin.route('/api/recent-orders')
@admin_required
def get_recent_orders():
    try:
        # Get last 10 orders
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        
        orders_data = []
        for order in recent_orders:
            orders_data.append({
                'id': order.id,
                'name': order.name,
                'cod_amount': float(order.cod_amount),
                'shipping_status': order.shipping_status,
                'payment_status': order.payment_status,
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M'),
                'time_ago': get_time_ago(order.created_at)
            })
        
        return jsonify({
            'success': True,
            'orders': orders_data,
            'count': len(orders_data)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_time_ago(created_at):
    now = utc_now()
    diff = now - created_at
    
    if diff.days > 0:
        return f"منذ {diff.days} يوم"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"منذ {hours} ساعة"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"منذ {minutes} دقيقة"
    else:
        return "منذ لحظات"

@admin.route('/order/<int:order_id>/update-payment-method', methods=['POST'])
@admin_required
def update_payment_method(order_id):
    try:
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        payment_method = request.form.get('payment_method')
        
        if not payment_method:
            flash('طريقة الدفع مطلوبة', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        valid_payment_methods = ['cash_on_delivery', 'vodafone_cash', 'visa']
        if payment_method not in valid_payment_methods:
            flash('طريقة الدفع غير صالحة', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))
            
        # Update payment method
        order.payment_method = payment_method
        db.session.commit()
        
        flash('تم تحديث طريقة الدفع بنجاح!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating payment method: {str(e)}')
        flash('حدث خطأ أثناء تحديث طريقة الدفع', 'error')
        
    return redirect(url_for('admin.order_detail', order_id=order_id))

@admin.route('/backup_project', methods=['POST'])
@admin_required
def backup_project():
    """Handle full project backup request"""
    success, message = create_project_backup()
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.home'))

app.register_blueprint(shop)
app.register_blueprint(admin , url_prefix='/admin')
@app.errorhandler(404)
def page_not_found(e):
    return render_template("shop/400.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template("shop/500.html"), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Migrate: add description column to category if missing
        try:
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('category')]
            if 'description' not in columns:
                db.session.execute(db.text("ALTER TABLE category ADD COLUMN description TEXT DEFAULT ''"))
                db.session.commit()
                print('Migration: added description column to category table')
        except Exception as e:
            print(f'Migration check: {e}')
    debug_mode = os.getenv('FLASK_DEBUG', '1') in ('1', 'true', 'True')
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '8765'))
    app.run(debug=debug_mode, host=host, port=port)
