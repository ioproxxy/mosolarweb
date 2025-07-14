from app import app
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, User, Product, Category, Order, OrderItem, Cart, CartItem, PaymentMethod, Review, InvoiceTemplate, DeliveryComment, InstallationComment
from payment import process_card_payment, process_mpesa_payment, validate_card_details
from pdf_generator import generate_invoice_pdf, get_default_template
from slugify import slugify
from flask import send_file
import random
import string

# Homepage
@app.route('/')
def index():
    """Homepage of the Mo Solar Technologies website"""
    # Get featured products (limit to 4)
    featured_products = Product.query.filter_by(featured=True).limit(4).all()
    
    return render_template('index.html', featured_products=featured_products)
    
# Display all products with optional filtering
@app.route('/products')
def products():
    """Display all products with optional filtering"""
    page = request.args.get('page', 1, type=int)
    category_slug = request.args.get('category')
    search_query = request.args.get('search')
    sort = request.args.get('sort', 'name_asc')
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)
    in_stock = request.args.get('in_stock')
    
    # Build query
    query = Product.query
    
    # Apply filters
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first()
        if category:
            query = query.filter_by(category_id=category.id)
    
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%') | 
                             Product.description.ilike(f'%{search_query}%'))
    
    if price_min is not None:
        query = query.filter(Product.price >= price_min)
    
    if price_max is not None:
        query = query.filter(Product.price <= price_max)
    
    if in_stock:
        query = query.filter(Product.stock > 0)
    
    # Apply sorting
    if sort == 'name_asc':
        query = query.order_by(Product.name.asc())
    elif sort == 'name_desc':
        query = query.order_by(Product.name.desc())
    elif sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'newest':
        query = query.order_by(Product.created_at.desc())
    
    # Paginate results
    per_page = 12
    products = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all categories for sidebar
    categories = Category.query.all()
    
    return render_template('products.html', 
                          products=products.items,
                          page=page,
                          pages=products.pages,
                          total=products.total,
                          categories=categories, 
                          current_category=category_slug, 
                          search_query=search_query, 
                          sort=sort)
    
# Display product details
@app.route('/products/<slug>')
def product_detail(slug):
    """Display product details"""
    product = Product.query.filter_by(slug=slug).first_or_404()
    
    # Get related products (same category, exclude current product)
    related_products = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id
    ).limit(4).all()
    
    # Get reviews
    reviews = Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).all()
    
    return render_template('product_detail.html', product=product, related_products=related_products, reviews=reviews)

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        login_identifier = request.form.get('username') or request.form.get('email')  # Can be email or username
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        print(f"DEBUG LOGIN: identifier={login_identifier}, password={'*' * len(password) if password else None}")
        
        # Try to find user by email first, then by username
        user = User.query.filter_by(email=login_identifier).first()
        if not user:
            user = User.query.filter_by(username=login_identifier).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            
            # If user has items in session cart, transfer them to database cart
            if 'cart' in session and session['cart']:
                # Get or create user cart
                cart = Cart.query.filter_by(user_id=user.id).first()
                if not cart:
                    cart = Cart(user_id=user.id)
                    db.session.add(cart)
                    db.session.commit()
                
                # Transfer items
                for product_id, item in session['cart'].items():
                    try:
                        product_id = int(product_id)
                        quantity = item.get('quantity', 1)
                        
                        # Verify the product exists in the database
                        product = Product.query.get(product_id)
                        if not product:
                            continue  # Skip this item if product doesn't exist
                        
                        # Check if product exists in user's cart
                        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
                        
                        if cart_item:
                            # Update quantity
                            cart_item.quantity += quantity
                        else:
                            # Add new item
                            cart_item = CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity)
                            db.session.add(cart_item)
                    except Exception as e:
                        # Log the error but continue processing other items
                        print(f"Error adding cart item: {e}")
                        # Rollback the current transaction
                        db.session.rollback()
                
                try:
                    # Commit all valid cart items
                    db.session.commit()
                except Exception as e:
                    # If there's an error during commit, rollback
                    print(f"Error committing cart items: {e}")
                    db.session.rollback()
                
                # Clear session cart
                session.pop('cart', None)
            
            next_page = request.args.get('next')
            flash('Login successful. Welcome back!', 'success')
            
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username/email or password. Please check your credentials and try again.', 'danger')
    
    return render_template('login.html')

# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not username or not email or not phone_number or not password:
            flash('All fields are required', 'danger')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
            
        # Validate phone number format (Kenyan mobile numbers)
        import re
        phone_pattern = r'^\+254[17]\d{8}$'
        if not re.match(phone_pattern, phone_number):
            flash('Please enter a valid Kenyan mobile number (e.g., +254712345678)', 'danger')
            return render_template('register.html')
            
        # Check if username, email, or phone number already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('register.html')
            
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('register.html')
            
        if User.query.filter_by(phone_number=phone_number).first():
            flash('Phone number already exists', 'danger')
            return render_template('register.html')
            
        # Create user
        user = User(
            username=username,
            email=email,
            phone_number=phone_number
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create empty cart for user
        cart = Cart(user_id=user.id)
        db.session.add(cart)
        db.session.commit()
        
        flash('Registration successful. You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# User logout
@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

# User profile page
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    if request.method == 'POST':
        # Update profile
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone_number = request.form.get('phone_number')
        address = request.form.get('address')
        city = request.form.get('city')
        country = request.form.get('country')
        postal_code = request.form.get('postal_code')
        
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.phone_number = phone_number
        current_user.address = address
        current_user.city = city
        current_user.country = country
        current_user.postal_code = postal_code
        
        db.session.commit()
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    # Get user's orders
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    
    return render_template('profile.html', user=current_user, orders=orders)

# Shopping cart page
@app.route('/cart')
def cart():
    """Shopping cart page"""
    # Drivers and installers cannot access shopping cart
    if current_user.is_authenticated and current_user.is_driver():
        flash('Access denied. Drivers cannot access shopping features.', 'error')
        return redirect(url_for('dashboard'))
    
    if current_user.is_authenticated and current_user.is_installer():
        flash('Access denied. Installers cannot use the shopping cart.', 'error')
        return redirect(url_for('installer_dashboard'))
        
    cart_items = []
    total = 0
    
    if current_user.is_authenticated:
        # Get cart from database
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        
        if cart:
            for item in cart.items:
                product = Product.query.get(item.product_id)
                if product:
                    subtotal = float(product.price) * item.quantity
                    cart_items.append({
                        'id': item.id,
                        'product': product,
                        'quantity': item.quantity,
                        'subtotal': subtotal
                    })
                    total += subtotal
    else:
        # Get cart from session
        cart_data = session.get('cart', {})
        
        for product_id, item in cart_data.items():
            product = Product.query.get(int(product_id))
            if product:
                quantity = item.get('quantity', 1)
                subtotal = float(product.price) * quantity
                cart_items.append({
                    'id': f"session_{product_id}",
                    'product': product,
                    'quantity': quantity,
                    'subtotal': subtotal
                })
                total += subtotal
    
    return render_template('cart.html', cart_items=cart_items, total=total)

# Add item to cart
@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    """Add item to cart"""
    # Drivers and installers cannot add items to cart
    if current_user.is_authenticated and current_user.is_driver():
        flash('Access denied. Drivers cannot access shopping features.', 'error')
        return redirect(url_for('products'))
    
    if current_user.is_authenticated and current_user.is_installer():
        flash('Access denied. Installers cannot access shopping features.', 'error')
        return redirect(url_for('products'))
        
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)
    
    if not product_id:
        flash('Product not found', 'danger')
        return redirect(url_for('products'))
    
    # Validate product exists and has stock
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('products'))
        
    if product.stock < quantity:
        flash(f'Only {product.stock} units available', 'danger')
        return redirect(url_for('product_detail', slug=product.slug))
    
    if current_user.is_authenticated:
        # Add to database cart
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        
        if not cart:
            cart = Cart(user_id=current_user.id)
            db.session.add(cart)
            db.session.commit()
        
        # Check if product already in cart
        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
        
        if cart_item:
            # Update quantity
            cart_item.quantity += quantity
        else:
            # Add new item
            cart_item = CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity)
            db.session.add(cart_item)
        
        db.session.commit()
    else:
        # Add to session cart
        cart = session.get('cart', {})
        
        # Convert product_id to string for session storage
        product_id_str = str(product_id)
        
        if product_id_str in cart:
            # Update quantity
            cart[product_id_str]['quantity'] += quantity
        else:
            # Add new item
            cart[product_id_str] = {'quantity': quantity}
        
        session['cart'] = cart
    
    flash(f'{product.name} added to cart', 'success')
    
    # Get referer or default to products page
    referer = request.headers.get('Referer')
    if referer and 'login' not in referer and 'register' not in referer:
        return redirect(referer)
    else:
        return redirect(url_for('products'))

# Update cart quantities
@app.route('/cart/update', methods=['POST'])
def update_cart():
    """Update cart quantities"""
    # Drivers and installers cannot update cart
    if current_user.is_authenticated and current_user.is_driver():
        return jsonify({'success': False, 'message': 'Access denied. Drivers cannot access shopping features.'})
    
    if current_user.is_authenticated and current_user.is_installer():
        return jsonify({'success': False, 'message': 'Access denied. Installers cannot access shopping features.'})
        
    item_id = request.form.get('item_id')
    quantity = request.form.get('quantity', 1, type=int)
    
    if not item_id:
        return jsonify({'success': False, 'message': 'Item not found'})
    
    if current_user.is_authenticated:
        # Update database cart
        if item_id.isdigit():  # Database cart item
            cart_item = CartItem.query.get(int(item_id))
            
            if not cart_item or cart_item.cart.user_id != current_user.id:
                return jsonify({'success': False, 'message': 'Item not found'})
            
            # Check product stock
            product = Product.query.get(cart_item.product_id)
            if not product or product.stock < quantity:
                return jsonify({
                    'success': False, 
                    'message': f'Only {product.stock if product else 0} units available'
                })
            
            cart_item.quantity = quantity
            db.session.commit()
            
            # Calculate new subtotal and cart total
            subtotal = float(product.price) * quantity
            
            # Get cart total
            cart = Cart.query.filter_by(user_id=current_user.id).first()
            total = 0
            for item in cart.items:
                product = Product.query.get(item.product_id)
                if product:
                    total += float(product.price) * item.quantity
            
            return jsonify({
                'success': True,
                'subtotal': subtotal,
                'total': total
            })
    else:
        # Update session cart
        if item_id.startswith('session_'):
            product_id = item_id.split('_')[1]
            cart = session.get('cart', {})
            
            if product_id in cart:
                # Check product stock
                product = Product.query.get(int(product_id))
                if not product or product.stock < quantity:
                    return jsonify({
                        'success': False, 
                        'message': f'Only {product.stock if product else 0} units available'
                    })
                
                cart[product_id]['quantity'] = quantity
                session['cart'] = cart
                
                # Calculate new subtotal and cart total
                subtotal = float(product.price) * quantity
                
                # Get cart total
                total = 0
                for pid, item in cart.items():
                    product = Product.query.get(int(pid))
                    if product:
                        total += float(product.price) * item.get('quantity', 1)
                
                return jsonify({
                    'success': True,
                    'subtotal': subtotal,
                    'total': total
                })
    
    return jsonify({'success': False, 'message': 'Failed to update cart'})

# Remove item from cart
@app.route('/cart/remove/<item_id>', methods=['DELETE', 'POST'])
def remove_from_cart(item_id):
    """Remove item from cart"""
    # Drivers and installers cannot remove cart items
    if current_user.is_authenticated and current_user.is_driver():
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Access denied. Drivers cannot access shopping features.'})
        else:
            flash('Access denied. Drivers cannot access shopping features.', 'error')
            return redirect(url_for('products'))
    
    if current_user.is_authenticated and current_user.is_installer():
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Access denied. Installers cannot access shopping features.'})
        else:
            flash('Access denied. Installers cannot access shopping features.', 'error')
            return redirect(url_for('products'))
            
    if current_user.is_authenticated:
        # Remove from database cart
        if request.method == 'POST' or (item_id.isdigit() and request.method == 'DELETE'):
            cart_item = CartItem.query.get(int(item_id))
            
            if cart_item and cart_item.cart.user_id == current_user.id:
                db.session.delete(cart_item)
                db.session.commit()
                
                if request.method == 'DELETE':
                    return jsonify({'success': True})
                else:
                    flash('Item removed from cart', 'success')
    else:
        # Remove from session cart
        if request.method == 'POST' or (item_id.startswith('session_') and request.method == 'DELETE'):
            if item_id.startswith('session_'):
                product_id = item_id.split('_')[1]
                cart = session.get('cart', {})
                
                if product_id in cart:
                    del cart[product_id]
                    session['cart'] = cart
                    
                    if request.method == 'DELETE':
                        return jsonify({'success': True})
                    else:
                        flash('Item removed from cart', 'success')
    
    if request.method == 'DELETE':
        return jsonify({'success': False, 'message': 'Item not found'})
    
    return redirect(url_for('cart'))

# Checkout page and order creation
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Checkout page and order creation"""
    # Drivers and installers cannot access checkout
    if current_user.is_driver():
        flash('Access denied. Drivers cannot access shopping features.', 'error')
        return redirect(url_for('dashboard'))
    
    if current_user.is_installer():
        flash('Access denied. Installers cannot access shopping features.', 'error')
        return redirect(url_for('installer_dashboard'))
        
    print(f"DEBUG: Checkout route called with method: {request.method}")
    print(f"DEBUG: Form data: {request.form}")
    print(f"DEBUG: Current user authenticated: {current_user.is_authenticated}")
    print(f"DEBUG: Current user: {current_user}")
    
    if not current_user.is_authenticated:
        print("DEBUG: User not authenticated, redirecting to login")
        flash('Please login to checkout', 'info')
        return redirect(url_for('login', next=url_for('checkout')))
    
    try:
        cart_items = []
        total = 0
        
        # Get cart items and total
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        
        if cart and cart.items:
            for item in cart.items:
                product = Product.query.get(item.product_id)
                if product and product.stock >= item.quantity:
                    subtotal = float(product.price) * item.quantity
                    cart_items.append({
                        'id': item.id,
                        'product': product,
                        'quantity': item.quantity,
                        'subtotal': subtotal
                    })
                    total += subtotal
                else:
                    # Remove items that are out of stock or don't exist
                    if item:
                        db.session.delete(item)
        
        if cart_items:
            db.session.commit()
        
        if not cart_items:
            flash('Your cart is empty or contains unavailable items', 'warning')
            return redirect(url_for('cart'))
            
        # Process checkout
        if request.method == 'POST':
            print(f"DEBUG: Processing POST request")
            print(f"DEBUG: All form fields: {dict(request.form)}")
            
            # Get form data
            payment_method_id = request.form.get('payment_method_id', type=int)
            shipping_address = request.form.get('shipping_address', '').strip()
            shipping_city = request.form.get('shipping_city', '').strip()
            shipping_country = request.form.get('shipping_country', '').strip()
            shipping_postal_code = request.form.get('shipping_postal_code', '').strip()
            contact_phone = request.form.get('contact_phone', '').strip()
            contact_email = request.form.get('contact_email', '').strip()
            
            print(f"DEBUG: Extracted data - Payment method ID: {payment_method_id}, Address: {shipping_address}, City: {shipping_city}")
            
            # Validate required fields
            missing_fields = []
            if not payment_method_id:
                missing_fields.append('Payment method')
            if not shipping_address:
                missing_fields.append('Shipping address')
            if not shipping_city:
                missing_fields.append('City')
            if not shipping_country:
                missing_fields.append('Country')
            if not shipping_postal_code:
                missing_fields.append('Postal code')
            if not contact_phone:
                missing_fields.append('Phone number')
            if not contact_email:
                missing_fields.append('Email address')
            
            if missing_fields:
                flash(f'Please fill in the following required fields: {", ".join(missing_fields)}', 'danger')
                payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
                return render_template('checkout.html', 
                                     cart_items=cart_items, 
                                     total=total, 
                                     cart_total=total,
                                     user=current_user, 
                                     payment_methods=payment_methods)
            
            # Validate payment method
            payment_method = PaymentMethod.query.get(payment_method_id)
            if not payment_method or not payment_method.is_active:
                flash('Invalid payment method selected', 'danger')
                payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
                return render_template('checkout.html', 
                                     cart_items=cart_items, 
                                     total=total, 
                                     cart_total=total,
                                     user=current_user, 
                                     payment_methods=payment_methods)
            
            # Create order
            try:
                order = Order(
                    user_id=current_user.id,
                    payment_method_id=payment_method_id,
                    status='pending',
                    total_amount=total,
                    shipping_address=shipping_address,
                    shipping_city=shipping_city,
                    shipping_country=shipping_country,
                    shipping_postal_code=shipping_postal_code,
                    contact_phone=contact_phone,
                    contact_email=contact_email
                )
                
                db.session.add(order)
                db.session.flush()  # Get order ID without committing
                
                # Add order items
                for item in cart_items:
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=item['product'].id,
                        quantity=item['quantity'],
                        price=item['product'].price
                    )
                    db.session.add(order_item)
                    
                    # Update product stock
                    product = item['product']
                    product.stock -= item['quantity']
                
                # Empty cart
                CartItem.query.filter_by(cart_id=cart.id).delete()
                
                db.session.commit()
                
                # Redirect to payment page
                if payment_method.code == 'card':
                    return redirect(url_for('payment', order_id=order.id, payment_type='card'))
                elif payment_method.code == 'mpesa':
                    return redirect(url_for('payment', order_id=order.id, payment_type='mpesa'))

                else:
                    flash('Invalid payment method', 'danger')
                    return redirect(url_for('checkout'))
                    
            except Exception as e:
                db.session.rollback()
                print(f"ERROR creating order: {str(e)}")
                print(f"ERROR traceback: {e.__class__.__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                app.logger.error(f'Error creating order: {str(e)}')
                flash('Error processing your order. Please try again.', 'danger')
                payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
                return render_template('checkout.html', 
                                     cart_items=cart_items, 
                                     total=total, 
                                     cart_total=total,
                                     user=current_user, 
                                     payment_methods=payment_methods)
        
        # GET request - show checkout form
        payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
        
        if not payment_methods:
            flash('No payment methods available. Please contact support.', 'danger')
            return redirect(url_for('cart'))
        
        # Check if we have a direct payment method specified via query parameter
        preferred_payment = request.args.get('payment')
        preferred_method_id = None
        
        if preferred_payment:
            for method in payment_methods:
                if method.code == preferred_payment:
                    preferred_method_id = method.id
                    break
        
        return render_template('checkout.html', 
                             cart_items=cart_items, 
                             total=total, 
                             cart_total=total,
                             user=current_user, 
                             payment_methods=payment_methods,
                             preferred_method_id=preferred_method_id)
                             
    except Exception as e:
        print(f"CHECKOUT ERROR: {str(e)}")
        print(f"CHECKOUT ERROR traceback: {e.__class__.__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        app.logger.error(f'Checkout error: {str(e)}')
        flash('An error occurred during checkout. Please try again.', 'danger')
        return redirect(url_for('cart'))

# Payment page for different payment methods
@app.route('/payment/<int:order_id>/<payment_type>', methods=['GET', 'POST'])
@login_required
def payment(order_id, payment_type):
    """Payment page for different payment methods"""
    # Drivers and installers cannot access payment processing
    if current_user.is_driver():
        flash('Access denied. Drivers cannot access shopping features.', 'error')
        return redirect(url_for('dashboard'))
    
    if current_user.is_installer():
        flash('Access denied. Installers cannot access shopping features.', 'error')
        return redirect(url_for('installer_dashboard'))
        
    order = Order.query.get_or_404(order_id)
    
    # Ensure order belongs to current user
    if order.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Ensure order is pending
    if order.status != 'pending':
        flash('Order has already been processed', 'warning')
        return redirect(url_for('order_confirmation', order_id=order.id))
    
    if payment_type == 'card':
        if request.method == 'POST':
            # Process card payment
            card_number = request.form.get('card_number')
            expiry = request.form.get('expiry')
            cvv = request.form.get('cvv')
            card_holder = request.form.get('card_holder')
            
            # Validate card details
            is_valid, error_message = validate_card_details(card_number, expiry, cvv, card_holder)
            
            if not is_valid:
                flash(error_message, 'danger')
                return render_template('payment.html', order=order, payment_type=payment_type)
            
            # Process payment
            result = process_card_payment(order, {
                'card_number': card_number,
                'expiry': expiry,
                'cvv': cvv,
                'card_holder': card_holder
            })
            
            if result['success']:
                # Update order status and payment reference
                order.status = 'paid'
                order.payment_reference = result.get('transaction_id', 'N/A')
                db.session.commit()
                
                flash('Payment successful! Your order has been confirmed.', 'success')
                return redirect(url_for('my_orders'))
            else:
                flash(result.get('message', 'Payment failed'), 'danger')
                return render_template('payment.html', order=order, payment_type=payment_type)
        
        return render_template('payment.html', order=order, payment_type=payment_type)
        
    elif payment_type == 'mpesa':
        if request.method == 'POST':
            # Process M-Pesa payment
            phone_number = request.form.get('phone_number')
            
            if not phone_number:
                flash('Phone number is required', 'danger')
                return render_template('payment.html', order=order, payment_type=payment_type)
            
            # Process payment
            try:
                result = process_mpesa_payment(order, phone_number)
                print(f"M-Pesa payment result: {result}")  # Debug logging
            except Exception as e:
                print(f"Error in process_mpesa_payment: {str(e)}")  # Debug logging
                import traceback
                traceback.print_exc()
                flash(f'Payment processing failed: {str(e)}', 'danger')
                return render_template('payment.html', order=order, payment_type=payment_type)
            
            if result['success']:
                # Update order status and payment reference
                try:
                    order.status = 'paid'
                    order.payment_reference = result.get('transaction_id', 'N/A')
                    db.session.commit()
                    print(f"M-Pesa: Order {order.id} status updated to paid")  # Debug logging
                    
                    # For test environment, automatically redirect to My Orders
                    if result.get('dev_mode', False):
                        flash('Payment processed successfully in test mode! Check your order in My Orders.', 'success')
                    else:
                        flash('Payment successful! Your order has been confirmed.', 'success')
                    return redirect(url_for('my_orders'))
                except Exception as e:
                    print(f"M-Pesa: Error updating order status: {str(e)}")  # Debug logging
                    db.session.rollback()
                    flash(f'Payment completed but order update failed: {str(e)}', 'danger')
                    return render_template('payment.html', order=order, payment_type=payment_type)
            else:
                flash(result.get('message', 'Payment failed'), 'danger')
                return render_template('payment.html', order=order, payment_type=payment_type)
        
        return render_template('payment.html', order=order, payment_type=payment_type)
        

    
    flash('Invalid payment method', 'danger')
    return redirect(url_for('checkout'))

# Payment success page
@app.route('/payment/success')
@login_required
def payment_success():
    """Payment success page"""
    return render_template('payment_success.html')

# Order confirmation page
@app.route('/order/<int:order_id>')
@login_required
def order_confirmation(order_id):
    """Order confirmation page"""
    order = Order.query.get_or_404(order_id)
    
    # Ensure order belongs to current user
    if order.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Get order items
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    
    return render_template('order_confirmation.html', order=order, order_items=order_items)

# Add product review
@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    """Add product review"""
    product = Product.query.get_or_404(product_id)
    
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment')
    
    if not rating or rating < 1 or rating > 5:
        flash('Rating is required and must be between 1 and 5', 'danger')
        return redirect(url_for('product_detail', slug=product.slug))
    
    # Check if user has already reviewed this product
    existing_review = Review.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    
    if existing_review:
        # Update existing review
        existing_review.rating = rating
        existing_review.comment = comment
        db.session.commit()
        flash('Your review has been updated', 'success')
    else:
        # Add new review
        review = Review(
            product_id=product_id,
            user_id=current_user.id,
            rating=rating,
            comment=comment
        )
        
        db.session.add(review)
        db.session.commit()
        
        flash('Your review has been added', 'success')
    
    return redirect(url_for('product_detail', slug=product.slug))

# Contact page
@app.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')

# About page
@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

# FAQ page
@app.route('/faq')
def faq():
    """Frequently Asked Questions page"""
    return render_template('faq.html')

# Eco-Impact Dashboard
@app.route('/eco-dashboard')
def eco_dashboard():
    """Eco-Impact visualization dashboard"""
    return render_template('eco_dashboard.html')

# Role-Based Dashboards
@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard - redirects to role-specific dashboard"""
    if current_user.is_admin():
        return redirect(url_for('admin_dashboard'))
    elif current_user.is_helpdesk():
        return redirect(url_for('support_dashboard'))
    elif current_user.is_installer():
        return redirect(url_for('installer_dashboard'))
    elif current_user.is_driver():
        return redirect(url_for('driver_dashboard'))
    else:
        return redirect(url_for('customer_dashboard'))

@app.route('/dashboard/admin')
@login_required
def admin_dashboard():
    """Admin dashboard with comprehensive business overview"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    # Get dashboard data
    total_users = User.query.count()
    total_orders = Order.query.count()
    total_products = Product.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    low_stock_products = Product.query.filter(Product.stock <= 10).all()
    
    # Revenue calculation
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(
        Order.status.in_(['paid', 'shipped', 'delivered'])
    ).scalar() or 0
    total_revenue = float(total_revenue) if total_revenue else 0
    
    # Recent delivery and installation comments
    recent_delivery_comments = DeliveryComment.query.order_by(DeliveryComment.created_at.desc()).limit(5).all()
    recent_installation_comments = InstallationComment.query.order_by(InstallationComment.created_at.desc()).limit(5).all()
    
    return render_template('dashboards/admin_dashboard.html', 
                         total_users=total_users,
                         total_orders=total_orders,
                         total_products=total_products,
                         total_revenue=total_revenue,
                         recent_orders=recent_orders,
                         low_stock_products=low_stock_products,
                         recent_delivery_comments=recent_delivery_comments,
                         recent_installation_comments=recent_installation_comments)

@app.route('/dashboard/support')
@login_required
def support_dashboard():
    """Support dashboard for customer service operations"""
    if not current_user.is_helpdesk() and not current_user.is_admin():
        flash('Access denied. Support privileges required.', 'error')
        return redirect(url_for('index'))
    
    # Get support-specific data
    from models import SupportTicket
    pending_orders = Order.query.filter(Order.status == 'pending').all()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(15).all()
    customers = User.query.filter(User.role == 'customer').all()
    support_tickets = SupportTicket.query.filter(SupportTicket.status.in_(['open', 'in_progress'])).order_by(SupportTicket.created_at.desc()).limit(10).all()
    
    # Recent delivery and installation comments for support review
    recent_delivery_comments = DeliveryComment.query.order_by(DeliveryComment.created_at.desc()).limit(8).all()
    recent_installation_comments = InstallationComment.query.order_by(InstallationComment.created_at.desc()).limit(8).all()
    
    return render_template('dashboards/support_dashboard.html',
                         pending_orders=pending_orders,
                         recent_orders=recent_orders,
                         customers=customers,
                         support_tickets=support_tickets,
                         recent_delivery_comments=recent_delivery_comments,
                         recent_installation_comments=recent_installation_comments)

@app.route('/dashboard/installer')
@login_required
def installer_dashboard():
    """Installer dashboard for installation management"""
    if not current_user.is_installer():
        flash('Access denied. Installer privileges required.', 'error')
        return redirect(url_for('index'))
    
    # Get installer-specific data
    # Orders available for installation (paid, shipped, and delivered orders)
    paid_orders = Order.query.filter(Order.status == 'paid').all()
    in_progress_orders = Order.query.filter(Order.status == 'shipped').all()
    delivered_orders = Order.query.filter(Order.status == 'delivered').all()
    
    # All orders that can have installation comments (paid through delivered)
    installation_orders = Order.query.filter(Order.status.in_(['paid', 'shipped', 'delivered'])).order_by(Order.created_at.desc()).all()
    all_products = Product.query.all()
    
    return render_template('dashboards/installer_dashboard.html',
                         paid_orders=paid_orders,
                         in_progress_orders=in_progress_orders,
                         delivered_orders=delivered_orders,
                         installation_orders=installation_orders,
                         all_products=all_products)

@app.route('/dashboard/driver')
@login_required
def driver_dashboard():
    """Driver dashboard for delivery management"""
    if not current_user.is_driver():
        flash('Access denied. Driver privileges required.', 'error')
        return redirect(url_for('index'))
    
    # Get driver-specific data
    delivery_orders = Order.query.filter(Order.status.in_(['paid', 'shipped'])).all()
    completed_deliveries = Order.query.filter(Order.status == 'delivered').limit(10).all()
    
    return render_template('dashboards/driver_dashboard.html',
                         delivery_orders=delivery_orders,
                         completed_deliveries=completed_deliveries)

@app.route('/dashboard/customer')
@login_required
def customer_dashboard():
    """Customer dashboard for order tracking and account management"""
    if not current_user.is_customer():
        flash('Access denied. Customer account required.', 'error')
        return redirect(url_for('index'))
    
    # Get customer-specific data
    customer_orders = Order.query.filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()
    customer_reviews = Review.query.filter(Review.user_id == current_user.id).all()
    
    return render_template('dashboards/customer_dashboard.html',
                         customer_orders=customer_orders,
                         customer_reviews=customer_reviews)

# 404 Page not found
@app.errorhandler(404)
def page_not_found(e):
    """404 Page not found"""
    return render_template('errors/404.html'), 404

# 500 Server error
@app.errorhandler(500)
def server_error(e):
    """500 Server error"""
    return render_template('errors/500.html'), 500

# Return the number of items in the cart
@app.route('/api/cart/count')
def cart_count():
    """Return the number of items in the cart"""
    count = 0
    
    if current_user.is_authenticated:
        # Get cart for authenticated user
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if cart:
            count = sum(item.quantity for item in cart.items)
    else:
        # Get cart from session for non-authenticated user
        cart_data = session.get('cart', {})
        count = 0
        for product_id, item in cart_data.items():
            # Verify product exists
            product = Product.query.get(int(product_id))
            if product:
                count += item.get('quantity', 0)
    
    return jsonify({'count': count})

def initialize_payment_methods():
    """Initialize payment methods if they don't exist."""
    # Check if payment methods exist
    if PaymentMethod.query.count() == 0:
        # Add payment methods
        payment_methods = [
            {'name': 'Credit/Debit Card', 'code': 'card'},
            {'name': 'M-Pesa', 'code': 'mpesa'},

        ]
        
        for method in payment_methods:
            payment_method = PaymentMethod(name=method['name'], code=method['code'])
            db.session.add(payment_method)
        
        db.session.commit()

def seed_db():
    """Seed the database with sample data."""
    # Check if database already has data
    if Category.query.count() > 0 or Product.query.count() > 0:
        return
    
    # Add categories
    categories = [
        {'name': 'Solar Panels', 'description': 'High-efficiency solar panels for residential and commercial use', 'slug': 'solar-panels'},
        {'name': 'Inverters', 'description': 'Convert DC power from solar panels into AC power for home use', 'slug': 'inverters'},
        {'name': 'Batteries', 'description': 'Store solar energy for use during nighttime or power outages', 'slug': 'batteries'},
        {'name': 'Solar Water Heaters', 'description': 'Efficient water heating using solar energy', 'slug': 'solar-water-heaters'},
        {'name': 'CCTV', 'description': 'Security camera systems for residential and commercial use', 'slug': 'cctv'},
        {'name': 'Electronics', 'description': 'Electronic devices and components for various applications', 'slug': 'electronics'},
        {'name': 'Electricals', 'description': 'Electrical equipment and supplies', 'slug': 'electricals'},
        {'name': 'Accessories', 'description': 'Mounting hardware, cables, and other solar accessories', 'slug': 'accessories'}
    ]
    
    for cat in categories:
        category = Category(name=cat['name'], description=cat['description'], slug=cat['slug'])
        db.session.add(category)
    
    db.session.commit()
    
    # Get category IDs for reference
    solar_panels = Category.query.filter_by(slug='solar-panels').first()
    inverters = Category.query.filter_by(slug='inverters').first()
    batteries = Category.query.filter_by(slug='batteries').first()
    accessories = Category.query.filter_by(slug='accessories').first()
    
    # Get solar water heaters category
    solar_water_heaters = Category.query.filter_by(slug='solar-water-heaters').first()
    
    # Add products
    products = [
        {
            'name': 'Mo Solar Technologies 100W Panel', 
            'description': 'High-quality 100W monocrystalline solar panel. Efficient and durable for small applications like camping or small off-grid systems.',
            'price': 6500, 
            'stock': 50, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': solar_panels.id,
            'slug': 'mo-solar-technologies-100w-panel',
            'featured': True
        },
        {
            'name': 'Mo Solar Technologies 250W Panel', 
            'description': 'Premium 250W monocrystalline solar panel. Perfect for residential installations with high efficiency and 25-year warranty.',
            'price': 12500, 
            'stock': 30, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': solar_panels.id,
            'slug': 'mo-solar-technologies-250w-panel',
            'featured': False
        },
        {
            'name': 'Mo Solar Technologies 500W Panel', 
            'description': 'Commercial-grade 500W solar panel. High power output for larger installations and businesses.',
            'price': 24000, 
            'stock': 20, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': solar_panels.id,
            'slug': 'mo-solar-technologies-500w-panel',
            'featured': False
        },
        {
            'name': 'Must Solar 5kW Inverter', 
            'description': 'Premium Must Solar 5kW pure sine wave inverter for medium to large solar installations. Features LCD display, MPPT technology, and high efficiency rate.',
            'price': 65000, 
            'stock': 10, 
            'image_url': '/static/images/products/must-solar-inverter.jpg', 
            'category_id': inverters.id,
            'slug': 'must-solar-5kw-inverter',
            'featured': True
        },
        {
            'name': 'Mo Solar Technologies 3kW Inverter', 
            'description': 'High-capacity 3kW inverter suitable for most home installations. Features smart monitoring and grid tie capability.',
            'price': 35000, 
            'stock': 15, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': inverters.id,
            'slug': 'mo-solar-technologies-3kw-inverter',
            'featured': False
        },
        {
            'name': 'Must LiFePO4 100Ah Battery', 
            'description': 'Deep cycle 100Ah LiFePO4 lithium battery for solar energy storage. Long-lasting, lightweight and maintenance-free with advanced LiFePO4 technology. Up to 4000 charge cycles and 10-year warranty.',
            'price': 45000, 
            'stock': 15, 
            'image_url': '/static/images/products/must-lifepo4-battery.jpg', 
            'category_id': batteries.id,
            'slug': 'must-lifepo4-100ah-battery',
            'featured': True
        },
        {
            'name': 'Mo Solar Technologies 200Ah Battery', 
            'description': 'High-capacity 200Ah battery for homes and businesses. Provides reliable backup power for extended periods.',
            'price': 32000, 
            'stock': 20, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': batteries.id,
            'slug': 'mo-solar-technologies-200ah-battery',
            'featured': False
        },
        {
            'name': 'AquaHeat Solar Water Heater 200L', 
            'description': 'Premium AquaHeat 200-liter solar water heating system. High-efficiency vacuum tubes with pressurized tank. Perfect for small to medium families with 5-year warranty.',
            'price': 85000, 
            'stock': 8, 
            'image_url': '/static/images/products/aquaheat-solar-water-heater.jpg', 
            'category_id': solar_water_heaters.id,
            'slug': 'aquaheat-solar-water-heater-200l',
            'featured': True
        },
        {
            'name': 'Seven Stars Solar Water Heater 150L', 
            'description': 'Seven Stars 150-liter solar water heating system with pressurized tank and integrated water storage. Complete with mounting hardware and 5-year warranty.',
            'price': 75000, 
            'stock': 5, 
            'image_url': '/static/images/products/seven-stars-solar-water-heater.jpg', 
            'category_id': solar_water_heaters.id,
            'slug': 'seven-stars-solar-water-heater-150l',
            'featured': False
        },
        {
            'name': 'Solar Panel Mounting Kit', 
            'description': 'Complete mounting kit for rooftop solar panel installation. Includes rails, clamps, and hardware.',
            'price': 7500, 
            'stock': 35, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': accessories.id,
            'slug': 'solar-panel-mounting-kit',
            'featured': True
        },
        {
            'name': 'Solar DC Cable Set', 
            'description': 'High-quality DC cables for connecting solar panels to inverters. UV-resistant and durable for outdoor use.',
            'price': 3500, 
            'stock': 60, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': accessories.id,
            'slug': 'solar-dc-cable-set',
            'featured': False
        },
        {
            'name': 'Solar Charge Controller', 
            'description': '30A MPPT solar charge controller for efficient battery charging. Features LCD display and multiple protection functions.',
            'price': 5500, 
            'stock': 45, 
            'image_url': '/static/images/products/mo-solar-logo.jpg', 
            'category_id': accessories.id,
            'slug': 'solar-charge-controller',
            'featured': False
        }
    ]
    
    for prod in products:
        product = Product(
            name=prod['name'],
            description=prod['description'],
            price=prod['price'],
            stock=prod['stock'],
            image_url=prod['image_url'],
            category_id=prod['category_id'],
            slug=prod['slug'],
            featured=prod['featured']
        )
        db.session.add(product)
    
    db.session.commit()

# Initialize database
with app.app_context():
    initialize_payment_methods()
    seed_db()

# Inventory management page (admin only)
@app.route('/inventory')
@login_required
def inventory():
    """
    Display inventory management page (admin only)
    """
    # Check if user is admin
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
        
    # Get all products with pagination
    # Get filter parameters
    category_filter = request.args.get('category')
    stock_filter = request.args.get('stock')
    search_query = request.args.get('search', '').strip()
    
    # Build query with filters
    query = Product.query
    
    if category_filter:
        query = query.filter(Product.category_id == category_filter)
        
    if stock_filter:
        if stock_filter == 'low':
            query = query.filter(Product.stock < 10, Product.stock > 0)
        elif stock_filter == 'out':
            query = query.filter(Product.stock == 0)
            
    if search_query:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search_query}%'),
                Product.description.ilike(f'%{search_query}%'),
                Product.id.like(f'%{search_query}%')
            )
        )
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    products = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all categories for filtering
    categories = Category.query.all()
    
    # Get inventory stats
    total_products = Product.query.count()
    low_stock_count = Product.query.filter(Product.stock < 10, Product.stock > 0).count()
    out_of_stock_count = Product.query.filter(Product.stock == 0).count()
    
    stats = {
        'total': total_products,
        'low_stock': low_stock_count,
        'out_of_stock': out_of_stock_count,
        'in_stock': total_products - out_of_stock_count
    }
    
    return render_template('admin_inventory.html', 
                         products=products.items, 
                         categories=categories,
                         pagination=products,
                         stats=stats,
                         current_filters={
                             'category': category_filter,
                             'stock': stock_filter,
                             'search': search_query
                         })
    
# Add a new product or update an existing one
@app.route('/inventory/product', methods=['POST'])
@login_required
def add_product():
    """
    Add a new product or update an existing one
    """
    # Check if user is admin
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
    # Get form data
    product_id = request.form.get('product_id')
    name = request.form.get('name')
    category_id = request.form.get('category_id')
    price = request.form.get('price')
    stock = request.form.get('stock')
    description = request.form.get('description')
    image_url = request.form.get('image_url')
    slug = request.form.get('slug')
    featured = 'featured' in request.form
    
    # Validate data
    if not name or not category_id or not price or not slug:
        return jsonify({'success': False, 'message': 'Required fields are missing'}), 400
        
    # Check if category exists
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'success': False, 'message': 'Invalid category'}), 400
        
    # Check if slug is unique (unless updating)
    existing_product = Product.query.filter_by(slug=slug).first()
    if existing_product and (not product_id or int(product_id) != existing_product.id):
        return jsonify({'success': False, 'message': 'Slug already exists. Please choose a different one.'}), 400
        
    if product_id:  # Update existing product
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
            
        product.name = name
        product.category_id = category_id
        product.price = price
        product.description = description
        product.image_url = image_url
        product.slug = slug
        product.featured = featured
        product.updated_at = datetime.utcnow()
        
        # Only update stock if it's different
        if int(stock) != product.stock:
            product.stock = stock
            
        db.session.commit()
        message = 'Product updated successfully'
    else:  # Add new product
        product = Product(
            name=name,
            category_id=category_id,
            price=price,
            stock=stock,
            description=description,
            image_url=image_url,
            slug=slug,
            featured=featured
        )
        
        db.session.add(product)
        db.session.commit()
        message = 'Product added successfully'
        
    return jsonify({'success': True, 'message': message, 'product_id': product.id})

# Delete a product
@app.route('/inventory/product/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    """
    Delete a product
    """
    # Check if user is admin
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
    product = Product.query.get_or_404(product_id)
    
    # Check if product is in any orders
    order_items = OrderItem.query.filter_by(product_id=product_id).first()
    if order_items:
        # Don't allow deletion if product is in orders
        return jsonify({'success': False, 'message': 'Cannot delete product that has been ordered. Consider marking it as out of stock instead.'}), 400
        
    # Remove from any carts
    cart_items = CartItem.query.filter_by(product_id=product_id).all()
    for item in cart_items:
        db.session.delete(item)
        
    # Delete reviews
    reviews = Review.query.filter_by(product_id=product_id).all()
    for review in reviews:
        db.session.delete(review)
        
    db.session.delete(product)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Product deleted successfully'})
    
# Update product stock
@app.route('/inventory/stock', methods=['POST'])
@login_required
def update_stock():
    """
    Update product stock
    """
    # Check if user is admin
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
    # Get form data
    product_id = request.form.get('product_id')
    action = request.form.get('action')
    quantity = request.form.get('quantity', type=int)
    note = request.form.get('note', '')
    
    # Validate data
    if not product_id or not action or quantity is None:
        return jsonify({'success': False, 'message': 'Required fields are missing'}), 400
        
    product = Product.query.get_or_404(product_id)
    
    # Update stock based on action
    if action == 'add':
        product.stock += quantity
    elif action == 'remove':
        product.stock = max(0, product.stock - quantity)
    elif action == 'set':
        product.stock = max(0, quantity)
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
    product.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': 'Stock updated successfully',
        'new_stock': product.stock
    })

# Get product by ID for editing
@app.route('/api/product/<int:product_id>', methods=['GET'])
@login_required
def get_product(product_id):
    """
    Get product details by ID for editing
    """
    # Check if user is admin
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
    product = Product.query.get_or_404(product_id)
    
    return jsonify({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'category_id': product.category_id,
            'price': float(product.price),
            'stock': product.stock,
            'description': product.description or '',
            'image_url': product.image_url or '',
            'slug': product.slug,
            'featured': product.featured
        }
    })

# Bulk actions for products
@app.route('/api/products/bulk', methods=['POST'])
@login_required
def bulk_product_actions():
    """
    Handle bulk actions on products
    """
    # Check if user is admin
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
    data = request.get_json()
    action = data.get('action')
    product_ids = data.get('product_ids', [])
    
    if not action or not product_ids:
        return jsonify({'success': False, 'message': 'Action and product IDs required'}), 400
        
    products = Product.query.filter(Product.id.in_(product_ids)).all()
    
    if not products:
        return jsonify({'success': False, 'message': 'No products found'}), 404
        
    try:
        if action == 'delete':
            # Check if any product is in orders
            for product in products:
                order_items = OrderItem.query.filter_by(product_id=product.id).first()
                if order_items:
                    return jsonify({'success': False, 'message': f'Cannot delete "{product.name}" - it has been ordered. Consider marking it as out of stock instead.'}), 400
            
            # Delete products
            for product in products:
                db.session.delete(product)
            message = f'Successfully deleted {len(products)} products'
            
        elif action == 'feature':
            for product in products:
                product.featured = True
                product.updated_at = datetime.utcnow()
            message = f'Successfully featured {len(products)} products'
            
        elif action == 'unfeature':
            for product in products:
                product.featured = False
                product.updated_at = datetime.utcnow()
            message = f'Successfully unfeatured {len(products)} products'
            
        elif action == 'mark_out_of_stock':
            for product in products:
                product.stock = 0
                product.updated_at = datetime.utcnow()
            message = f'Successfully marked {len(products)} products as out of stock'
            
        else:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
            
        db.session.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error performing bulk action: {str(e)}'}), 500

# Generate slug from product name
@app.route('/api/generate-slug', methods=['POST'])
@login_required
def generate_slug_api():
    """
    Generate a URL-friendly slug from product name
    """
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Access denied'}), 403
        
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Product name required'}), 400
        
    # Generate base slug
    base_slug = slugify(name)
    
    # Check if slug exists and add number if needed
    slug = base_slug
    counter = 1
    
    while Product.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
        
    return jsonify({'success': True, 'slug': slug})


# Chat and Support Ticket Routes
@app.route('/chat')
def chat():
    """Live chat interface"""
    return render_template('chat.html')


@app.route('/api/chat/start', methods=['POST'])
def start_chat():
    """Start a new chat session"""
    import uuid
    
    session_token = str(uuid.uuid4())
    user_id = current_user.id if current_user.is_authenticated else None
    
    # Create new chat session
    from models import ChatSession, ChatMessage
    chat_session = ChatSession(
        user_id=user_id,
        session_token=session_token,
        is_active=True
    )
    db.session.add(chat_session)
    db.session.commit()
    
    # Add welcome message
    welcome_message = ChatMessage(
        session_id=chat_session.id,
        user_id=None,
        message="Hello! Welcome to Mo Solar Technologies support. How can I help you today?",
        is_staff_message=False,
        is_system_message=True
    )
    db.session.add(welcome_message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'session_token': session_token,
        'session_id': chat_session.id
    })


@app.route('/api/chat/send', methods=['POST'])
def send_chat_message():
    """Send a message in chat"""
    data = request.get_json()
    session_token = data.get('session_token')
    message_text = data.get('message')
    
    if not session_token or not message_text:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    from models import ChatSession, ChatMessage
    chat_session = ChatSession.query.filter_by(session_token=session_token, is_active=True).first()
    if not chat_session:
        return jsonify({'success': False, 'message': 'Invalid or expired session'}), 404
    
    # Add user message
    user_message = ChatMessage(
        session_id=chat_session.id,
        user_id=current_user.id if current_user.is_authenticated else None,
        message=message_text,
        is_staff_message=False,
        is_system_message=False
    )
    db.session.add(user_message)
    
    # Auto-reply logic for common questions
    auto_reply = get_auto_reply(message_text)
    if auto_reply:
        reply_message = ChatMessage(
            session_id=chat_session.id,
            user_id=None,
            message=auto_reply,
            is_staff_message=False,
            is_system_message=True
        )
        db.session.add(reply_message)
    else:
        # Create a support ticket for complex queries
        from models import SupportTicket
        ticket_subject = f"Live Chat: {message_text[:50]}..."
        
        # Check if ticket already exists for this session
        if not chat_session.ticket_id:
            support_ticket = SupportTicket(
                user_id=current_user.id if current_user.is_authenticated else 1,  # Default to admin for anonymous
                subject=ticket_subject,
                status='open',
                priority='medium'
            )
            db.session.add(support_ticket)
            db.session.flush()  # Get the ticket ID
            
            chat_session.ticket_id = support_ticket.id
            
            # Add initial ticket message
            from models import TicketMessage
            ticket_message = TicketMessage(
                ticket_id=support_ticket.id,
                user_id=current_user.id if current_user.is_authenticated else 1,
                message=message_text,
                is_staff_reply=False
            )
            db.session.add(ticket_message)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Message sent successfully'})


@app.route('/api/chat/messages/<session_token>')
def get_chat_messages(session_token):
    """Get messages for a chat session"""
    from models import ChatSession, ChatMessage
    
    chat_session = ChatSession.query.filter_by(session_token=session_token).first()
    if not chat_session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    
    messages = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(ChatMessage.created_at).all()
    
    return jsonify({
        'success': True,
        'messages': [{
            'id': msg.id,
            'message': msg.message,
            'is_staff_message': msg.is_staff_message,
            'is_system_message': msg.is_system_message,
            'created_at': msg.created_at.strftime('%H:%M'),
            'user_name': msg.user.first_name if msg.user and msg.user.first_name else 'You'
        } for msg in messages]
    })


@app.route('/support/tickets')
@login_required
def support_tickets():
    """View support tickets (helpdesk staff only)"""
    if not current_user.is_helpdesk() and not current_user.is_admin():
        flash('Access denied. Helpdesk privileges required.', 'error')
        return redirect(url_for('index'))
    
    from models import SupportTicket
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    
    return render_template('support/tickets.html', tickets=tickets)


@app.route('/support/ticket/<int:ticket_id>')
@login_required
def view_ticket(ticket_id):
    """View individual support ticket"""
    from models import SupportTicket
    
    ticket = SupportTicket.query.get_or_404(ticket_id)
    
    # Check permissions
    if not (current_user.is_helpdesk() or current_user.is_admin() or current_user.id == ticket.user_id):
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    return render_template('support/ticket_detail.html', ticket=ticket)


@app.route('/support/ticket/<int:ticket_id>/reply', methods=['POST'])
@login_required
def reply_to_ticket(ticket_id):
    """Reply to a support ticket"""
    from models import SupportTicket, TicketMessage
    
    ticket = SupportTicket.query.get_or_404(ticket_id)
    
    # Check permissions
    if not (current_user.is_helpdesk() or current_user.is_admin() or current_user.id == ticket.user_id):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    message_text = request.form.get('message')
    new_status = request.form.get('status')
    
    if not message_text:
        return jsonify({'success': False, 'message': 'Message is required'}), 400
    
    # Create ticket reply
    reply = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user.id,
        message=message_text,
        is_staff_reply=current_user.is_helpdesk() or current_user.is_admin()
    )
    db.session.add(reply)
    
    # Update ticket status
    if current_user.is_helpdesk() or current_user.is_admin():
        if new_status and new_status in ['open', 'in_progress', 'resolved', 'closed']:
            ticket.status = new_status
        elif ticket.status == 'open':
            ticket.status = 'in_progress'
    
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash('Reply sent successfully', 'success')
    return redirect(url_for('view_ticket', ticket_id=ticket.id))


@app.route('/my-tickets')
@login_required
def my_tickets():
    """View current user's support tickets"""
    from models import SupportTicket
    
    tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).all()
    
    return render_template('support/my_tickets.html', tickets=tickets)


def get_auto_reply(message):
    """Get automated reply for common questions"""
    message_lower = message.lower()
    
    # FAQ-style auto replies
    if any(word in message_lower for word in ['price', 'cost', 'how much']):
        return "Our solar panels start from KSh 15,000. You can view all our products and prices at our Products page. Would you like me to connect you with a sales representative for a detailed quote?"
    
    elif any(word in message_lower for word in ['installation', 'install', 'setup']):
        return "We provide professional installation services for all our solar products. Our certified technicians will handle the complete setup. Installation typically takes 1-2 days depending on system size. Would you like to schedule a site assessment?"
    
    elif any(word in message_lower for word in ['warranty', 'guarantee']):
        return "All our solar panels come with a 25-year manufacturer warranty and 5-year installation warranty. We also provide ongoing maintenance support. Need specific warranty details for a product?"
    
    elif any(word in message_lower for word in ['delivery', 'shipping']):
        return "All deliveries are sourced from our headquarters at CBD, Sheikh Karume Road, Young Business Center, Ground Floor, Shop 13. We offer free delivery within Nairobi and Kiambu. Delivery to other counties available with charges. Standard delivery takes 2-3 business days. Would you like to check delivery options for your area?"
    
    elif any(word in message_lower for word in ['mpesa', 'payment', 'pay']):
        return "We accept M-Pesa and credit card payments. You can pay during checkout or contact us for payment plans on larger systems. Need help with payment options?"
    
    elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
        return "Hello! I'm here to help you with any questions about our solar products and services. What would you like to know?"
    
    elif any(word in message_lower for word in ['thank', 'thanks']):
        return "You're welcome! Is there anything else I can help you with regarding our solar solutions?"
    
    else:
        return None  # No auto-reply, create ticket


# Invoice and PDF routes
@app.route('/admin/invoice-templates')
@login_required
def invoice_templates():
    """Manage invoice templates (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    templates = InvoiceTemplate.query.all()
    return render_template('admin_invoice_templates.html', templates=templates)


@app.route('/admin/invoice-templates/add', methods=['GET', 'POST'])
@login_required
def add_invoice_template():
    """Add new invoice template"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        template = InvoiceTemplate(
            name=request.form['name'],
            template_type=request.form['template_type'],
            company_name=request.form['company_name'],
            company_address=request.form['company_address'],
            company_phone=request.form['company_phone'],
            company_email=request.form['company_email'],
            company_logo_url=request.form.get('company_logo_url'),
            header_text=request.form.get('header_text'),
            footer_text=request.form.get('footer_text'),
            terms_conditions=request.form.get('terms_conditions'),
            payment_instructions=request.form.get('payment_instructions'),
            is_active=True
        )
        
        db.session.add(template)
        db.session.commit()
        
        flash('Invoice template created successfully!', 'success')
        return redirect(url_for('invoice_templates'))
    
    return render_template('admin_add_invoice_template.html')


@app.route('/admin/invoice-templates/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
def edit_invoice_template(template_id):
    """Edit invoice template"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    template = InvoiceTemplate.query.get_or_404(template_id)
    
    if request.method == 'POST':
        template.name = request.form['name']
        template.template_type = request.form['template_type']
        template.company_name = request.form['company_name']
        template.company_address = request.form['company_address']
        template.company_phone = request.form['company_phone']
        template.company_email = request.form['company_email']
        template.company_logo_url = request.form.get('company_logo_url')
        template.header_text = request.form.get('header_text')
        template.footer_text = request.form.get('footer_text')
        template.terms_conditions = request.form.get('terms_conditions')
        template.payment_instructions = request.form.get('payment_instructions')
        template.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Invoice template updated successfully!', 'success')
        return redirect(url_for('invoice_templates'))
    
    return render_template('admin_edit_invoice_template.html', template=template)


@app.route('/download-invoice/<int:order_id>')
@login_required
def download_invoice(order_id):
    """Download invoice PDF for an order"""
    order = Order.query.get_or_404(order_id)
    
    # Check if user owns this order or is admin
    if order.user_id != current_user.id and not current_user.is_admin():
        flash('Access denied. You can only download your own invoices.', 'error')
        return redirect(url_for('index'))
    
    try:
        # Generate PDF
        pdf_buffer = generate_invoice_pdf(order)
        
        # Return PDF as download
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f'invoice-{order.id:06d}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        flash('Error generating invoice PDF. Please try again.', 'error')
        return redirect(url_for('profile'))


@app.route('/orders')
@login_required
def my_orders():
    """View user's orders with PDF download links"""
    # Drivers, installers, and support staff cannot access My Orders
    if current_user.is_driver():
        flash('Access denied. Drivers cannot access order history.', 'error')
        return redirect(url_for('dashboard'))
    
    if current_user.is_installer():
        flash('Access denied. Installers cannot access order history.', 'error')
        return redirect(url_for('installer_dashboard'))
    
    if current_user.is_helpdesk():
        flash('Access denied. Support staff cannot access personal order history.', 'error')
        return redirect(url_for('support_dashboard'))
        
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def delete_order(order_id):
    """Delete an unpaid order"""
    # Drivers, installers, and support staff cannot delete orders
    if current_user.is_driver() or current_user.is_installer() or current_user.is_helpdesk():
        flash('Access denied. Only customers can delete orders.', 'error')
        return redirect(url_for('dashboard'))
        
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first()
    
    if not order:
        flash('Order not found or you do not have permission to delete it.', 'error')
        return redirect(url_for('my_orders'))
    
    # Only allow deletion of pending orders (not yet paid)
    if order.status != 'pending':
        flash('Only pending orders can be deleted.', 'error')
        return redirect(url_for('my_orders'))
    
    try:
        # Return stock to inventory for each item
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                product.stock += item.quantity
        
        # Delete the order (this will cascade delete order items)
        db.session.delete(order)
        db.session.commit()
        
        flash('Order deleted successfully. Items have been returned to inventory.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting order. Please try again.', 'error')
        print(f"Error deleting order: {e}")
    
    return redirect(url_for('my_orders'))

@app.route('/payment/process/<int:order_id>', methods=['POST'])
@login_required
def process_payment_directly(order_id):
    """Process payment for an existing order directly"""
    # Drivers, installers, and support staff cannot process payments
    if current_user.is_driver() or current_user.is_installer() or current_user.is_helpdesk():
        return jsonify({'success': False, 'message': 'Access denied. Only customers can process payments.'})
    
    try:
        # Get the order
        order = Order.query.filter_by(id=order_id, user_id=current_user.id).first()
        if not order:
            return jsonify({'success': False, 'message': 'Order not found'}), 404
            
        # Only process pending orders
        if order.status != 'pending':
            return jsonify({'success': False, 'message': 'Order cannot be paid for in its current status'}), 400
            
        # Get payment data from request
        data = request.get_json()
        payment_method_id = data.get('payment_method_id')
        phone_number = data.get('phone_number')
        
        if not payment_method_id:
            return jsonify({'success': False, 'message': 'Payment method is required'}), 400
            
        # Get payment method
        payment_method = PaymentMethod.query.get(payment_method_id)
        if not payment_method:
            return jsonify({'success': False, 'message': 'Invalid payment method'}), 400
            
        # Process payment based on method
        if payment_method.code == 'mpesa':
            if not phone_number:
                return jsonify({'success': False, 'message': 'Phone number is required for M-Pesa'}), 400
                
            from payment import process_mpesa_payment
            result = process_mpesa_payment(order, phone_number)
            
            if result.get('success'):
                # Update order status and payment reference
                order.status = 'paid'
                order.payment_reference = result.get('transaction_id')
                db.session.commit()
                
                return jsonify({
                    'success': True, 
                    'payment_method': 'mpesa',
                    'message': 'M-Pesa payment initiated successfully',
                    'transaction_id': result.get('transaction_id'),
                    'redirect_url': '/orders'
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': result.get('message', 'M-Pesa payment failed')
                }), 400
                

                
        elif payment_method.code == 'card':
            # For card payments, we'll simulate success
            from payment import process_card_payment
            result = process_card_payment(order)
            
            if result.get('success'):
                order.status = 'paid'
                order.payment_reference = result.get('transaction_id')
                db.session.commit()
                
                return jsonify({
                    'success': True, 
                    'payment_method': 'card',
                    'redirect_url': '/orders',
                    'message': 'Card payment completed successfully',
                    'transaction_id': result.get('transaction_id')
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': result.get('message', 'Card payment failed')
                }), 400
        else:
            return jsonify({'success': False, 'message': 'Unsupported payment method'}), 400
            
    except Exception as e:
        print(f"Payment processing error: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Payment processing failed'}), 500


# Delivery Comments Routes
@app.route('/delivery/comment', methods=['POST'])
@login_required
def add_delivery_comment():
    """Add delivery comment (driver only)"""
    if not current_user.is_driver():
        return jsonify({'success': False, 'message': 'Access denied. Driver privileges required.'}), 403
    
    try:
        order_id = request.form.get('order_id')
        comment = request.form.get('comment')
        delivery_status = request.form.get('delivery_status')
        delivery_rating = request.form.get('delivery_rating', type=int)
        
        if not all([order_id, comment, delivery_status]):
            return jsonify({'success': False, 'message': 'All required fields must be provided'}), 400
        
        # Verify order exists
        order = Order.query.get_or_404(order_id)
        
        # Create delivery comment
        delivery_comment = DeliveryComment(
            order_id=order_id,
            driver_id=current_user.id,
            comment=comment,
            delivery_status=delivery_status,
            delivery_rating=delivery_rating
        )
        
        db.session.add(delivery_comment)
        
        # Update order status if delivery is completed
        if delivery_status == 'delivered':
            order.status = 'delivered'
        
        db.session.commit()
        
        flash('Delivery comment added successfully', 'success')
        return jsonify({'success': True, 'message': 'Delivery comment added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error adding delivery comment: {str(e)}'}), 500


# Installation Comments Routes
@app.route('/installation/comment', methods=['POST'])
@login_required
def add_installation_comment():
    """Add installation comment (installer only)"""
    if not current_user.is_installer():
        return jsonify({'success': False, 'message': 'Access denied. Installer privileges required.'}), 403
    
    try:
        order_id = request.form.get('order_id')
        comment = request.form.get('comment')
        installation_status = request.form.get('installation_status')
        technical_notes = request.form.get('technical_notes')
        completion_percentage = request.form.get('completion_percentage', type=int)
        estimated_completion_date = request.form.get('estimated_completion_date')
        
        if not all([order_id, comment, installation_status]):
            return jsonify({'success': False, 'message': 'Order ID, comment, and installation status are required'}), 400
        
        # Verify order exists
        order = Order.query.get_or_404(order_id)
        
        # Parse estimated completion date if provided
        est_completion_date = None
        if estimated_completion_date:
            try:
                est_completion_date = datetime.strptime(estimated_completion_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Create installation comment
        installation_comment = InstallationComment(
            order_id=order_id,
            installer_id=current_user.id,
            comment=comment,
            installation_status=installation_status,
            technical_notes=technical_notes,
            completion_percentage=completion_percentage or 0,
            estimated_completion_date=est_completion_date
        )
        
        db.session.add(installation_comment)
        
        # Update order status based on installation status
        if installation_status == 'completed':
            order.status = 'shipped'  # Ready for delivery
        
        db.session.commit()
        
        flash('Installation comment added successfully', 'success')
        return jsonify({'success': True, 'message': 'Installation comment added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error adding installation comment: {str(e)}'}), 500


# API Routes to get comments for dashboards
@app.route('/api/delivery-comments/<int:order_id>')
@login_required
def get_delivery_comments(order_id):
    """Get delivery comments for an order"""
    if not (current_user.is_admin() or current_user.is_helpdesk() or current_user.is_driver()):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    comments = DeliveryComment.query.filter_by(order_id=order_id).order_by(DeliveryComment.created_at.desc()).all()
    
    return jsonify({
        'success': True,
        'comments': [{
            'id': comment.id,
            'comment': comment.comment,
            'delivery_status': comment.delivery_status,
            'delivery_rating': comment.delivery_rating,
            'driver_name': f"{comment.driver.first_name} {comment.driver.last_name}" if comment.driver.first_name else comment.driver.username,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
        } for comment in comments]
    })


@app.route('/api/installation-comments/<int:order_id>')
@login_required
def get_installation_comments(order_id):
    """Get installation comments for an order"""
    if not (current_user.is_admin() or current_user.is_helpdesk() or current_user.is_installer()):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    comments = InstallationComment.query.filter_by(order_id=order_id).order_by(InstallationComment.created_at.desc()).all()
    
    return jsonify({
        'success': True,
        'comments': [{
            'id': comment.id,
            'comment': comment.comment,
            'installation_status': comment.installation_status,
            'technical_notes': comment.technical_notes,
            'completion_percentage': comment.completion_percentage,
            'estimated_completion_date': comment.estimated_completion_date.strftime('%Y-%m-%d') if comment.estimated_completion_date else None,
            'installer_name': f"{comment.installer.first_name} {comment.installer.last_name}" if comment.installer.first_name else comment.installer.username,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
        } for comment in comments]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
