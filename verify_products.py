from app import app
from models import Product

with app.app_context():
    # Get latest products (recently added)
    products = Product.query.order_by(Product.id.desc()).limit(15).all()
    
    print("\nRecently added products:")
    print("-" * 80)
    for product in products:
        print(f"ID: {product.id}, Name: {product.name}")
        print(f"  Price: KSh {float(product.price):.2f}, Stock: {product.stock}")
        print(f"  Category ID: {product.category_id}, Featured: {product.featured}")
        print(f"  Image: {product.image_url}")
        print("-" * 80)