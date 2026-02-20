#!/usr/bin/env python3
"""
Script to delete all products from the database
"""
from app import app, db, Product, Cart, OrderItem, AdditionalImage, AdditionalData
import os

def delete_all_products():
    with app.app_context():
        try:
            # حذف كل العناصر المرتبطة أولاً
            print("جاري حذف عناصر السلة...")
            Cart.query.delete()
            
            print("جاري حذف عناصر الطلبات...")
            OrderItem.query.delete()
            
            print("جاري حذف الصور الإضافية...")
            AdditionalImage.query.delete()
            
            print("جاري حذف البيانات الإضافية...")
            AdditionalData.query.delete()
            
            # حذف كل المنتجات
            print("جاري حذف المنتجات...")
            products = Product.query.all()
            count = len(products)
            
            for product in products:
                # حذف صور المنتج من الملفات
                if product.image and product.image != 'default.jpg':
                    image_path = os.path.join('static', 'img', product.image)
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        print(f"تم حذف الصورة: {product.image}")
                
                db.session.delete(product)
            
            db.session.commit()
            print(f"\n✅ تم حذف {count} منتج بنجاح!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ حدث خطأ: {str(e)}")
            raise

if __name__ == '__main__':
    confirm = input("⚠️  هل أنت متأكد من حذف كل المنتجات؟ (yes/no): ")
    if confirm.lower() == 'yes':
        delete_all_products()
    else:
        print("تم الإلغاء")
