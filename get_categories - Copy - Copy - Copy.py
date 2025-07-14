from app import app
from models import Category

with app.app_context():
    categories = Category.query.all()
    for cat in categories:
        print(f'ID: {cat.id}, Name: {cat.name}, Slug: {cat.slug}')