from app import app, db
from models import Product
import os
import shutil
import uuid
from slugify import slugify
from datetime import datetime

# Function to save product images to static/images/products folder
def save_product_image(source_path, product_name):
    # Create directory if it doesn't exist
    target_dir = "static/images/products"
    os.makedirs(target_dir, exist_ok=True)
    
    # Generate a unique filename
    filename = f"{slugify(product_name)}_{uuid.uuid4().hex[:8]}.jpg"
    target_path = os.path.join(target_dir, filename)
    
    # Copy the image
    shutil.copy(source_path, target_path)
    
    # Return the path to be stored in the database
    return f"/static/images/products/{filename}"

# Define new products with their details
new_products = [
    {
        "name": "Neelux 30W LED Solar Flood Light",
        "description": "IP66 waterproof LED solar flood light with a 30W power rating. Features bright white illumination and comes with an integrated solar panel for eco-friendly lighting solutions.",
        "price": 2200,
        "stock": 15,
        "category_id": 1,  # Solar Panels category
        "image_path": "attached_assets/IMG-20250407-WA0121.jpg",
        "featured": True
    },
    {
        "name": "Standard 550W Solar Panel",
        "description": "High-efficiency 550W monocrystalline solar panel for residential and commercial installations. Built with premium materials for durability and optimal performance in various weather conditions.",
        "price": 23500,
        "stock": 20,
        "category_id": 1,  # Solar Panels category
        "image_path": "attached_assets/IMG-20250407-WA0142.jpg",
        "featured": True
    },
    {
        "name": "V380 Solar-Powered Security Camera",
        "description": "Wireless security camera with integrated solar panel for continuous operation. Features motion detection, night vision, and remote viewing through mobile app.",
        "price": 5800,
        "stock": 12,
        "category_id": 6,  # CCTV category
        "image_path": "attached_assets/IMG-20250407-WA0145.jpg",
        "featured": False
    },
    {
        "name": "DAT DT-9036B Solar Lighting System",
        "description": "Complete solar lighting kit with 3 LED bulbs, solar panel, and portable power bank. Ideal for homes without grid electricity or for emergency backup lighting.",
        "price": 3200,
        "stock": 18,
        "category_id": 7,  # Electronics category
        "image_path": "attached_assets/IMG-20250407-WA0139.jpg",
        "featured": False
    },
    {
        "name": "Newvew Rechargeable Emergency Light NV-Y10",
        "description": "Portable emergency light with rechargeable battery. Features a compact design, handle for easy carrying, and bright illumination for emergency situations.",
        "price": 850,
        "stock": 30,
        "category_id": 7,  # Electronics category
        "image_path": "attached_assets/IMG-20250407-WA0126.jpg",
        "featured": False
    },
    {
        "name": "Newvew 5W Powerful Bright Searchlight",
        "description": "Handheld searchlight with 5W power and extended battery life. Perfect for security, camping, or emergency situations requiring powerful illumination.",
        "price": 1200,
        "stock": 25,
        "category_id": 7,  # Electronics category
        "image_path": "attached_assets/IMG-20250407-WA0125.jpg",
        "featured": False
    },
    {
        "name": "PPE Electrical Cable 1.5mm² Twin with Earth",
        "description": "High-quality electrical cable with 1.5mm² cross-section, featuring twin conductors with earth. 90-meter roll suitable for home and commercial electrical wiring.",
        "price": 7500,
        "stock": 40,
        "category_id": 8,  # Electricals category
        "image_path": "attached_assets/IMG-20250407-WA0124.jpg",
        "featured": False
    },
    {
        "name": "Solar Flood Light with Remote STL-101D1 500W",
        "description": "Powerful 500W solar flood light with remote control for easy operation. Features motion sensor, timer function, and durable weatherproof construction.",
        "price": 12500,
        "stock": 10,
        "category_id": 1,  # Solar Panels category
        "image_path": "attached_assets/IMG-20250407-WA0120.jpg",
        "featured": True
    },
    {
        "name": "Luminous NRG T+ 200Ah Tubular Battery",
        "description": "High-capacity 200Ah tubular battery designed for solar power systems. Features extra backup power and extended life for reliable energy storage.",
        "price": 28500,
        "stock": 15,
        "category_id": 3,  # Batteries category
        "image_path": "attached_assets/IMG-20250407-WA0104.jpg",
        "featured": True
    },
    {
        "name": "Amizar 200Ah Solar Inverter Battery",
        "description": "Premium 200Ah battery specifically designed for solar inverter systems. Offers high performance, durability, and optimal energy storage for consistent power supply.",
        "price": 25800,
        "stock": 12,
        "category_id": 3,  # Batteries category
        "image_path": "attached_assets/IMG-20250407-WA0101.jpg",
        "featured": False
    },
    {
        "name": "Felicity 6KW High Frequency Solar System",
        "description": "Complete 6KW solar power system including 9x 550W mono panels, 6KW inverter, and 48V 300Ah battery. Ideal for homes and small businesses requiring reliable power.",
        "price": 350000,
        "stock": 5,
        "category_id": 2,  # Inverters category
        "image_path": "attached_assets/IMG-20250407-WA0095.jpg",
        "featured": True
    },
    {
        "name": "LFP.6144.W LiFePO4 Battery 51.2V 120Ah",
        "description": "Advanced lithium iron phosphate battery with 51.2V 120Ah capacity. Supports 6kW inverter, features 1C charge/discharge rate, and conforms to IEC62619 and UL1973 standards.",
        "price": 150000,
        "stock": 8,
        "category_id": 3,  # Batteries category
        "image_path": "attached_assets/IMG-20250407-WA0093.jpg",
        "featured": True
    }
]

with app.app_context():
    # Add each product to the database
    for product_data in new_products:
        # Save image and get path
        image_url = save_product_image(product_data["image_path"], product_data["name"])
        
        # Create slug from name
        slug = slugify(product_data["name"])
        
        # Check if product with same slug exists
        existing_product = Product.query.filter_by(slug=slug).first()
        if existing_product:
            # Append timestamp to make slug unique
            slug = f"{slug}-{int(datetime.now().timestamp())}"
        
        # Create new product
        new_product = Product(
            name=product_data["name"],
            description=product_data["description"],
            price=product_data["price"],
            stock=product_data["stock"],
            image_url=image_url,
            slug=slug,
            featured=product_data["featured"],
            category_id=product_data["category_id"]
        )
        
        # Add to database
        db.session.add(new_product)
    
    # Commit all changes
    db.session.commit()
    
    print(f"Successfully added {len(new_products)} new products to the database.")