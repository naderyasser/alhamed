#!/usr/bin/env python3
"""
سكريبت لمسح جميع المنتجات من قاعدة البيانات
"""
import sys
import os

# إضافة المسار الحالي للـ Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Product, Cart, OrderItem, AdditionalImage, AdditionalData

def clear_all_products():
    """مسح جميع المنتجات والبيانات المرتبطة بها"""
    with app.app_context():
        try:
            # عد المنتجات قبل الحذف
            product_count = Product.query.count()
            
            if product_count == 0:
                print("✓ لا توجد منتجات في قاعدة البيانات")
                return
            
            # تأكيد من المستخدم
            print(f"⚠️  سيتم حذف {product_count} منتج من قاعدة البيانات")
            confirm = input("هل أنت متأكد؟ اكتب 'نعم' للتأكيد: ")
            
            if confirm.strip() != 'نعم':
                print("❌ تم إلغاء العملية")
                return
            
            # حذف البيانات المرتبطة أولاً
            print("🗑️  جاري حذف عناصر السلة...")
            Cart.query.delete()
            
            print("🗑️  جاري حذف عناصر الطلبات...")
            OrderItem.query.delete()
            
            print("🗑️  جاري حذف الصور الإضافية...")
            AdditionalImage.query.delete()
            
            print("🗑️  جاري حذف البيانات الإضافية...")
            AdditionalData.query.delete()
            
            print("🗑️  جاري حذف المنتجات...")
            Product.query.delete()
            
            # حفظ التغييرات
            db.session.commit()
            
            print(f"✅ تم حذف {product_count} منتج بنجاح!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ حدث خطأ: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    clear_all_products()
