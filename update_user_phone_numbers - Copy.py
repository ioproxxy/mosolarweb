#!/usr/bin/env python3
"""
Update existing users with sample phone numbers for M-Pesa integration
"""

from main import app, db
from models import User

def update_user_phone_numbers():
    """Update existing users with sample Kenyan phone numbers"""
    
    with app.app_context():
        try:
            # Define phone numbers for existing users
            user_phone_updates = {
                'admin': '+254712345678',        # Admin user
                'support': '+254723456789',      # Support user  
                'customer': '+254734567890',     # Customer user
                'john.mwangi': '+254745678901',  # John Mwangi
                'installer': '+254756789012',    # Installer user
                'driver': '+254767890123'        # Driver user
            }
            
            print("Updating user phone numbers...")
            updated_count = 0
            
            for username, phone_number in user_phone_updates.items():
                user = User.query.filter_by(username=username).first()
                if user:
                    user.phone_number = phone_number
                    print(f"✓ Updated {username} with phone number {phone_number}")
                    updated_count += 1
                else:
                    print(f"✗ User '{username}' not found")
            
            # Also update users by email if they don't have usernames
            email_phone_updates = {
                'erp@pm.me': '+254778901234'  # For any user with this email
            }
            
            for email, phone_number in email_phone_updates.items():
                user = User.query.filter_by(email=email).first()
                if user and not user.phone_number:
                    user.phone_number = phone_number
                    print(f"✓ Updated user with email {email} with phone number {phone_number}")
                    updated_count += 1
            
            # Commit all changes
            db.session.commit()
            print(f"\n✅ Successfully updated {updated_count} users with phone numbers")
            print("All users now have M-Pesa compatible phone numbers!")
            
        except Exception as e:
            print(f"Error updating phone numbers: {e}")
            db.session.rollback()

if __name__ == "__main__":
    update_user_phone_numbers()