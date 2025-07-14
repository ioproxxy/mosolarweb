#!/usr/bin/env python3
"""
Create sample user profiles for Mo Solar Technologies
- 1 Super User (Admin)
- 1 Help Desk User 
- 1 General User (Customer)
- 1 Solar Equipment Installer
- 1 Driver/Delivery Personnel
"""

from app import app, db
from models import User

def create_sample_users():
    """Create three sample user profiles"""
    
    with app.app_context():
        # Check if users already exist
        if User.query.filter_by(username='admin').first():
            print("Sample users already exist. Skipping creation.")
            return
        
        # 1. Super User (Admin)
        admin_user = User(
            username='admin',
            email='admin@mosolar.co.ke',
            first_name='Moses',
            last_name='Kiprotich',
            phone_number='+254722123456',
            address='Industrial Area, Off Mombasa Road',
            city='Nairobi',
            country='Kenya',
            postal_code='00100',
            role='admin',
            account_active=True
        )
        admin_user.set_password('Admin123!')
        
        # 2. Help Desk User (Customer Support)
        support_user = User(
            username='support',
            email='support@mosolar.co.ke',
            first_name='Grace',
            last_name='Wanjiku',
            phone_number='+254733456789',
            address='CBD, Kimathi Street',
            city='Nairobi',
            country='Kenya',
            postal_code='00100',
            role='helpdesk',
            account_active=True
        )
        support_user.set_password('Support123!')
        
        # 3. General User (Customer)
        customer_user = User(
            username='customer',
            email='john.mwangi@gmail.com',
            first_name='John',
            last_name='Mwangi',
            phone_number='+254700987654',
            address='Karen Shopping Centre',
            city='Nairobi',
            country='Kenya',
            postal_code='00502',
            role='customer',
            account_active=True
        )
        customer_user.set_password('Customer123!')
        
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
        
        # Add users to database
        db.session.add(admin_user)
        db.session.add(support_user)
        db.session.add(customer_user)
        db.session.add(installer_user)
        db.session.add(driver_user)
        
        try:
            db.session.commit()
            print("✅ Sample user profiles created successfully!")
            print("\n" + "="*50)
            print("SAMPLE USER ACCOUNTS")
            print("="*50)
            
            print("\n🔐 ADMIN USER (Super User)")
            print(f"Username: admin")
            print(f"Password: Admin123!")
            print(f"Email: admin@mosolar.co.ke")
            print(f"Name: Moses Kiprotich")
            print(f"Role: Administrator")
            print(f"Phone: +254722123456")
            
            print("\n🎧 HELP DESK USER (Customer Support)")
            print(f"Username: support")
            print(f"Password: Support123!")
            print(f"Email: support@mosolar.co.ke")
            print(f"Name: Grace Wanjiku")
            print(f"Role: Help Desk")
            print(f"Phone: +254733456789")
            
            print("\n👤 CUSTOMER USER (General User)")
            print(f"Username: customer")
            print(f"Password: Customer123!")
            print(f"Email: john.mwangi@gmail.com")
            print(f"Name: John Mwangi")
            print(f"Role: Customer")
            print(f"Phone: +254700987654")
            
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
            
            print("\n" + "="*50)
            print("All users are active and ready to use!")
            print("="*50)
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating users: {str(e)}")

if __name__ == '__main__':
    create_sample_users()