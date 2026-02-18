# دليل الاختبارات - Orfe Cosmetics Store

## نظرة عامة

تم إنشاء مجموعة اختبارات شاملة باستخدام `pytest` و `pytest-flask` لضمان جودة التطبيق وصحة عمله.

## محتويات الاختبارات

### 1. اختبارات النماذج (test_models.py)
- اختبار إنشاء وحفظ النماذج في قاعدة البيانات
- اختبار العلاقات بين الجداول (Category ↔ Product, Order ↔ OrderItem)
- اختبار المصادقة والتشفير للإداريين
- اختبار نموذج الدروب شوبينج

**مثال:**
```python
def test_create_product(self, db_session, sample_category):
    product = Product(name='هاتف Samsung', price=8000.0, ...)
    assert product.id is not None
```

### 2. اختبارات صفحات المتجر (test_shop_routes.py)
- اختبار الصفحة الرئيسية وعرض المنتجات
- اختبار البحث والفلترة (بالسعر، الفئة، الكلمات)
- اختبار صفحة تفاصيل المنتج وعداد المشاهدات
- اختبار عربة التسوق (إضافة، حذف، عرض)
- اختبار عملية الدفع

**مثال:**
```python
def test_filter_by_category(self, client, sample_product):
    response = client.get(f'/list?category={sample_category.id}')
    assert response.status_code == 200
```

### 3. اختبارات لوحة التحكم (test_admin_routes.py)
- اختبار تسجيل الدخول والخروج للإداري
- اختبار إدارة المنتجات (إضافة، تعديل، حذف)
- اختبار إدارة التصنيفات
- اختبار عرض الطلبات والإحصائيات
- اختبار الحماية (admin_required decorator)

**مثال:**
```python
def test_admin_login_success(self, client, sample_admin):
    response = client.post('/admin/login', data={...})
    assert response.status_code == 200
```

### 4. اختبارات الدروب شوبينج (test_dropshipping.py)
- اختبار سحب بيانات المنتجات من روابط خارجية
- اختبار استيراد المنتجات كمنتجات محلية
- اختبار تحميل الصور من الإنترنت
- اختبار معالجة الأخطاء (timeout, connection errors)
- اختبارات الـ API endpoints

**مثال:**
```python
@patch('app.scrape_product_data')
def test_scrape_product_success(self, mock_scrape, ...):
    mock_scrape.return_value = {'success': True, ...}
```

### 5. اختبارات الأدوات المساعدة (test_utils.py)
- اختبار دوال التحقق من الملفات
- اختبار إدارة الجلسات
- اختبار تنظيف عربات التسوق القديمة
- اختبار حماية CSRF

### 6. اختبارات الـ API (test_api_endpoints.py)
- اختبار API الطلبات الحديثة
- اختبار API سحب المنتجات
- اختبار حذف الصور الإضافية

## التثبيت

### 1. تثبيت المتطلبات
```bash
pip install -r requirements.txt
```

المتطلبات الأساسية للاختبارات:
- `pytest>=8.0.0` - إطار الاختبارات
- `pytest-flask>=1.3.0` - دعم Flask
- `pytest-cov>=4.1.0` - تغطية الكود

### 2. إعداد البيئة
```bash
# تفعيل البيئة الافتراضية (Windows)
.\.venv\Scripts\activate

# تفعيل البيئة الافتراضية (Linux/Mac)
source .venv/bin/activate
```

## تشغيل الاختبارات

### تشغيل جميع الاختبارات
```bash
pytest tests/ -v
```

### تشغيل اختبارات محددة
```bash
# اختبار ملف واحد
pytest tests/test_models.py -v

# اختبار class معينة
pytest tests/test_admin_routes.py::TestAdminAuth -v

# اختبار دالة واحدة
pytest tests/test_shop_routes.py::TestProductListing::test_filter_by_category -v
```

### خيارات مفيدة

```bash
# عرض المخرجات حتى الفاشلة
pytest tests/ -v -s

# التوقف عند أول فشل
pytest tests/ -x

# تشغيل الاختبارات بالتوازي (faster)
pytest tests/ -n auto

# عرض تغطية الكود
pytest tests/ --cov=app --cov-report=html
```

### تقرير تغطية الكود
```bash
# إنشاء تقرير HTML
pytest tests/ --cov=app --cov-report=html

# عرض التقرير في المتصفح
start htmlcov/index.html  # Windows
open htmlcov/index.html   # Mac
xdg-open htmlcov/index.html  # Linux
```

## تصنيف الاختبارات

الاختبارات مصنفة باستخدام markers:

```bash
# تشغيل اختبارات unit فقط
pytest tests/ -m unit

# تشغيل اختبارات integration فقط
pytest tests/ -m integration

# استبعاد الاختبارات البطيئة
pytest tests/ -m "not slow"
```

## الـ Fixtures المتاحة

تم إنشاء fixtures جاهزة في `conftest.py`:

- `app`: تطبيق Flask للاختبار
- `client`: عميل اختبار Flask
- `db_session`: جلسة قاعدة بيانات
- `sample_category`: فئة نموذجية
- `sample_product`: منتج نموذجي
- `sample_admin`: مشرف نموذجي
- `sample_guest`: ضيف نموذجي
- `sample_order`: طلب نموذجي
- `sample_dropship_product`: منتج دروب شوبينج نموذجي
- `authenticated_client`: عميل مسجل دخول كإداري

### مثال استخدام Fixtures
```python
def test_my_feature(client, sample_product, db_session):
    # client: عميل اختبار جاهز
    # sample_product: منتج جاهز في قاعدة البيانات
    # db_session: جلسة قاعدة بيانات
    response = client.get(f'/{sample_product.id}')
    assert response.status_code == 200
```

## هيكل الملفات

```
tests/
├── conftest.py              # Fixtures والإعدادات العامة
├── test_models.py           # اختبارات النماذج
├── test_shop_routes.py      # اختبارات صفحات المتجر
├── test_admin_routes.py     # اختبارات لوحة التحكم
├── test_dropshipping.py     # اختبارات الدروب شوبينج
├── test_utils.py            # اختبارات الدوال المساعدة
└── test_api_endpoints.py    # اختبارات الـ API
```

## إحصائيات الاختبارات

- **عدد الاختبارات الإجمالي**: ~90 اختبار
- **تغطية الكود**: تستهدف >80%
- **وقت التنفيذ**: ~10-15 ثانية

## نصائح للتطوير

### 1. كتابة اختبار جديد
```python
def test_feature_description(client, necessary_fixtures):
    """وصف واضح للاختبار"""
    # Arrange - إعداد البيانات
    data = {'key': 'value'}
    
    # Act - تنفيذ العملية
    response = client.post('/endpoint', data=data)
    
    # Assert - التحقق من النتيجة
    assert response.status_code == 200
```

### 2. استخدام Mocking
```python
from unittest.mock import patch, Mock

@patch('app.external_function')
def test_with_mock(mock_func, client):
    mock_func.return_value = 'expected_value'
    # اختبار بدون الاعتماد على موارد خارجية
```

### 3. اختبار قاعدة البيانات
```python
def test_database_operation(db_session, sample_product):
    # تعديل المنتج
    sample_product.price = 999.99
    db_session.commit()
    
    # التحقق من التحديث
    db_session.refresh(sample_product)
    assert sample_product.price == 999.99
```

## استكشاف الأخطاء

### مشكلة: فشل الاختبارات بسبب قاعدة البيانات
```bash
# حذف قاعدة البيانات واعادة إنشائها
rm instance/orfe-shop.sqlite3
python app.py
```

### مشكلة: خطأ في الـ imports
```bash
# التأكد من تثبيت جميع المتطلبات
pip install -r requirements.txt
```

### مشكلة: CSRF token errors
```python
# في conftest.py تأكد من:
app.config['WTF_CSRF_ENABLED'] = False  # للاختبارات فقط
```

## CI/CD Integration

يمكن دمج الاختبارات مع GitHub Actions:

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=app
```

## المساهمة

عند إضافة ميزة جديدة:
1. اكتب الاختبارات أولاً (TDD)
2. تأكد من نجاح جميع الاختبارات
3. حافظ على تغطية كود >80%

## الترخيص

هذه الاختبارات جزء من مشروع Orfe Cosmetics Store.
