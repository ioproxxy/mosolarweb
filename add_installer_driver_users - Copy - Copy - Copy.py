#!/usr/bin/env python3
"""
Add installer and driver user profiles to Mo Solar Technologies
"""

from app import app, db
from models import User

def add_new_users():
    """Add installer and driver user profiles"""
    
    with app.app_context():
        # Check if installer and driver users already exist
        if User.query.filter_by(username='installer').first():
            print("Installer user already exists.")
        else:
            # 4. Solar Equipment Installer
            installer_user = User(
                username='installer',
                email='paul.otieno@mosolar.co.ke',
                first_name='Paul',
                last_name='Otieno',
                phone_number='+254744556677',
                address='Industrial Area, Enterprise Road',
                city='Nairobi',
                country='Kenya',
                postal_code='00200',
                role='installer',
                account_active=True
            )
            installer_user.set_password('Installer123!')
            db.session.add(installer_user)
            print("✅ Created installer user: paul.otieno@mosolar.co.ke")

        if User.query.filter_by(username='driver').first():
            print("Driver user already exists.")
        else:
            # 5. Driver/Delivery Personnel
            driver_user = User(
                username='driver',
                email='samuel.kiplimo@mosolar.co.ke',
                first_name='Samuel',
                last_name='Kiplimo',
                phone_number='+254755667788',
                address='Embakasi, Outer Ring Road',
                city='Nairobi',
                country='Kenya',
                postal_code='00100',
                role='driver',
                account_active=True
            )
            driver_user.set_password('Driver123!')
            db.session.add(driver_user)
            print("✅ Created driver user: samuel.kiplimo@mosolar.co.ke")
        
        try:
            db.session.commit()
            print("\n" + "="*60)
            print("NEW USER ACCOUNTS ADDED")
            print("="*60)
            
            print("\n🔧 INSTALLER USER (Solar Equipment Installer)")
            print(f"Username: installer")
            print(f"Password: Installer123!")
            print(f"Email: paul.otieno@mosolar.co.ke")
            print(f"Name: Paul Otieno")
            print(f"Role: Installer")
            print(f"Phone: +254744556677")
            
            print("\n🚚 DRIVER USER (Delivery Personnel)")
            print(f"Username: driver")
            print(f"Password: Driver123!")
            print(f"Email: samuel.kiplimo@mosolar.co.ke")
            print(f"Name: Samuel Kiplimo")
            print(f"Role: Driver")
            print(f"Phone: +254755667788")
            
            print("\n" + "="*60)
            print("All new users are active and ready to use!")
            print("You can login using either username or email address.")
            print("="*60)
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating users: {str(e)}")

if __name__ == '__main__':
    add_new_users()