from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import app
from models import db, User, Product, Category, Order, OrderItem, Cart, CartItem, PaymentMethod, Review
from payment import process_card_payment, process_mpesa_payment, process_airtel_payment, validate_card_details
import random
import string

def register_routes(app):
    @app.route('/')
    def index():
        """Homepage of the Mo Solar Technologies website"""
        # Get featured products (limit to 4)
        featured_products = Product.query.filter_by(featured=True).limit(4).all()

        return render_template('index.html', featured_products=featured_products)

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

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            remember = 'remember' in request.form

            user = User.query.filter_by(username=username).first()

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
                        product_id = int(product_id)
                        quantity = item.get('quantity', 1)

                        # Check if product exists in user's cart
                        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()

                        if cart_item:
                            # Update quantity
                            cart_item.quantity += quantity
                        else:
                            # Add new item
                            cart_item = CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity)
                            db.session.add(cart_item)

                    db.session.commit()

                    # Clear session cart
                    session.pop('cart', None)

                next_page = request.args.get('next')
                flash('Login successful. Welcome back!', 'success')

                return redirect(next_page or url_for('index'))
            else:
                flash('Invalid username or password', 'danger')

        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """User registration"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # Validate inputs
            if not username or not email or not password:
                flash('All fields are required', 'danger')
                return render_template('register.html')

            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return render_template('register.html')

            # Check if username or email already exists
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return render_template('register.html')

            if User.query.filter_by(email=email).first():
                flash('Email already exists', 'danger')
                return render_template('register.html')

            # Create user
            user = User(
                username=username,
                email=email
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

    @app.route('/logout')
    @login_required
    def logout():
        """User logout"""
        logout_user()
        flash('You have been logged out.', 'success')
        return redirect(url_for('index'))

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

    @app.route('/cart')
    def cart():
        """Shopping cart page"""
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

    @app.route('/cart/add', methods=['POST'])
    def add_to_cart():
        """Add item to cart"""
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

    @app.route('/cart/update', methods=['POST'])
    def update_cart():
        """Update cart quantities"""
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
                total = sum(float(Product.query.get(item.product_id).price) * item.quantity 
                            for item in cart.items)

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
                    total = sum(float(Product.query.get(int(pid)).price) * item.get('quantity', 1) 
                                for pid, item in cart.items())

                    return jsonify({
                        'success': True,
                        'subtotal': subtotal,
                        'total': total
                    })

        return jsonify({'success': False, 'message': 'Failed to update cart'})

    @app.route('/cart/remove/<item_id>', methods=['DELETE', 'POST'])
    def remove_from_cart(item_id):
        """Remove item from cart"""
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

    @app.route('/checkout', methods=['GET', 'POST'])
    def checkout():
        """Checkout page and order creation"""
        cart_items = []
        total = 0

        # Get cart items and total
        if current_user.is_authenticated:
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

            if not cart_items:
                flash('Your cart is empty', 'warning')
                return redirect(url_for('cart'))

            # Process checkout
            if request.method == 'POST':
                # Get form data
                payment_method_id = request.form.get('payment_method', type=int)
                shipping_address = request.form.get('shipping_address')
                shipping_city = request.form.get('shipping_city')
                shipping_country = request.form.get('shipping_country')
                shipping_postal_code = request.form.get('shipping_postal_code')
                contact_phone = request.form.get('contact_phone')
                contact_email = request.form.get('contact_email')

                # Validate required fields
                if not all([payment_method_id, shipping_address, shipping_city, shipping_country, 
                            shipping_postal_code, contact_phone, contact_email]):
                    flash('All fields are required', 'danger')
                    return render_template('checkout.html', cart_items=cart_items, total=total, user=current_user)

                # Create order
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
                db.session.commit()

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
                payment_method = PaymentMethod.query.get(payment_method_id)

                if payment_method and payment_method.code == 'card':
                    return redirect(url_for('payment', order_id=order.id, payment_type='card'))
                elif payment_method and payment_method.code == 'mpesa':
                    return redirect(url_for('payment', order_id=order.id, payment_type='mpesa'))
                elif payment_method and payment_method.code == 'airtel':
                    return redirect(url_for('payment', order_id=order.id, payment_type='airtel'))
                else:
                    flash('Invalid payment method', 'danger')
                    return redirect(url_for('checkout'))

            # Get payment methods
            payment_methods = PaymentMethod.query.filter_by(is_active=True).all()

            return render_template('checkout.html', cart_items=cart_items, total=total, 
                                  user=current_user, payment_methods=payment_methods)
        else:
            # Redirect to login
            flash('Please login to checkout', 'info')
            return redirect(url_for('login', next=url_for('checkout')))

    @app.route('/payment/<int:order_id>/<payment_type>', methods=['GET', 'POST'])
    @login_required
    def payment(order_id, payment_type):
        """Payment page for different payment methods"""
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
                    return render_template('payment_card.html', order=order)

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

                    flash('Payment successful', 'success')
                    return redirect(url_for('payment_success'))
                else:
                    flash(result.get('message', 'Payment failed'), 'danger')
                    return render_template('payment_card.html', order=order)

            return render_template('payment_card.html', order=order)

        elif payment_type == 'mpesa':
            if request.method == 'POST':
                # Process M-Pesa payment
                phone_number = request.form.get('phone_number')

                if not phone_number:
                    flash('Phone number is required', 'danger')
                    return render_template('payment_mpesa.html', order=order)

                # Process payment
                result = process_mpesa_payment(order, phone_number)

                if result['success']:
                    # Update order status and payment reference
                    order.status = 'paid'
                    order.payment_reference = result.get('transaction_id', 'N/A')
                    db.session.commit()

                    flash('Payment successful', 'success')
                    return redirect(url_for('payment_success'))
                else:
                    flash(result.get('message', 'Payment failed'), 'danger')
                    return render_template('payment_mpesa.html', order=order)

            return render_template('payment_mpesa.html', order=order)

        elif payment_type == 'airtel':
            if request.method == 'POST':
                # Process Airtel Money payment
                phone_number = request.form.get('phone_number')

                if not phone_number:
                    flash('Phone number is required', 'danger')
                    return render_template('payment_airtel.html', order=order)

                # Process payment
                result = process_airtel_payment(order, phone_number)

                if result['success']:
                    # Update order status and payment reference
                    order.status = 'paid'
                    order.payment_reference = result.get('transaction_id', 'N/A')
                    db.session.commit()

                    flash('Payment successful', 'success')
                    return redirect(url_for('payment_success'))
                else:
                    flash(result.get('message', 'Payment failed'), 'danger')
                    return render_template('payment_airtel.html', order=order)

            return render_template('payment_airtel.html', order=order)

        flash('Invalid payment method', 'danger')
        return redirect(url_for('checkout'))

    @app.route('/payment/success')
    @login_required
    def payment_success():
        """Payment success page"""
        return render_template('payment_success.html')

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

    @app.route('/contact')
    def contact():
        """Contact page"""
        maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
        return render_template('contact.html', maps_api_key=maps_api_key)

    @app.route('/about')
    def about():
        """About page"""
        return render_template('about.html')

    @app.errorhandler(404)
    def page_not_found(e):
        """404 Page not found"""
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        """500 Server error"""
        return render_template('errors/500.html'), 500

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
            count = sum(item.get('quantity', 0) for item in cart_data.values())

        return jsonify({'count': count})

    def initialize_payment_methods():
        """Initialize payment methods if they don't exist."""
        # Check if payment methods exist
        if PaymentMethod.query.count() == 0:
            # Add payment methods
            payment_methods = [
                {'name': 'Credit/Debit Card', 'code': 'card'},
                {'name': 'M-Pesa', 'code': 'mpesa'},
                {'name': 'Airtel Money', 'code': 'airtel'}
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
        solar_water_heaters = Category.query.filter_by(slug='solar-water-heaters').first()

        # If solar-water-heaters category doesn't exist, create it
        if not solar_water_heaters:
            solar_water_heaters = Category(
                name='Solar Water Heaters',
                description='Energy-efficient solar water heating solutions for residential and commercial use',
                slug='solar-water-heaters'
            )
            db.session.add(solar_water_heaters)
            db.session.commit()

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
                ''slug': 'mo-solar-technologies-250w-panel',
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
                'name': 'Must Solar 3kW Inverter', 
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

    @app.route('/inventory')
    @login_required
    def inventory():
        """
        Display inventory management page (admin only)
        """
        # Check if user is admin
        if current_user.username != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('index'))

        # Get all products with pagination
        page = request.args.get('page', 1, type=int)
        per_page = 10
        products = Product.query.paginate(page=page, per_page=per_page, error_out=False)

        # Get all categories for filtering
        categories = Category.query.all()

        return render_template('inventory.html', products=products.items, categories=categories)

    @app.route('/inventory/product', methods=['POST'])
    @login_required
    def add_product():
        """
        Add a new product or update an existing one
        """
        # Check if user is admin
        if current_user.username != 'admin':
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

    @app.route('/inventory/product/<int:product_id>', methods=['DELETE'])
    @login_required
    def delete_product(product_id):
        """
        Delete a product
        """
        # Check if user is admin
        if current_user.username != 'admin':
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

    @app.route('/inventory/stock', methods=['POST'])
    @login_required
    def update_stock():
        """
        Update product stock
        """
        # Check if user is admin
        if current_user.username != 'admin':
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

    @app.route('/test-mpesa', methods=['GET'])
    def test_mpesa():
        """Test endpoint for Mpesa integration"""
        try:
            mpesa = MPesa()

            # Test authentication
            token = mpesa.get_auth_token()

            # Test STK push with sample data
            result = mpesa.initiate_stk_push(
                phone_number="254712345678",  # Test phone number
                amount=1,  # Minimal amount for testing
                order_id="TEST001"
            )

            return jsonify({
                'success': True,
                'token': token,
                'stk_push_result': result
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/test-mpesa', methods=['GET'])
    def test_mpesa():
        """Test endpoint for Mpesa integration"""
        try:
            # Get M-Pesa credentials from environment
            business_shortcode = os.getenv("MPESA_BUSINESS_SHORTCODE")
            consumer_key = os.getenv("MPESA_CONSUMER_KEY")
            consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
            
            if not all([business_shortcode, consumer_key, consumer_secret]):
                return jsonify({
                    'success': False,
                    'error': 'Missing required M-Pesa credentials in environment variables'
                })

            mpesa = MPesa()
            
            # Test authentication
            token = mpesa.get_auth_token()
            
            # Test STK push with sample data
            result = mpesa.initiate_stk_push(
                phone_number="254712345678",  # Test phone number
                amount=1,  # Minimal amount for testing
                order_id="TEST001"
            )
            
            return jsonify({
                'success': True,
                'token': token,
                'stk_push_result': result
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/mpesa/callback', methods=['POST'])
    def mpesa_callback():
        """Handle M-Pesa payment callback"""
        data = request.get_json()

        if "Body" in data and "stkCallback" in data["Body"]:
            result = data["Body"]["stkCallback"]

            if result["ResultCode"] == 0:
                # Payment successful
                merchant_request_id = result["MerchantRequestID"]
                checkout_request_id = result["CheckoutRequestID"]

                # Find order by checkout request ID and update its status
                # You'll need to store the checkout_request_id when initiating payment
                order = Order.query.filter_by(payment_reference=checkout_request_id).first()

                if order:
                    order.status = 'paid'
                    db.session.commit()

            return jsonify({'success': True}), 200

        return jsonify({'success': False, 'message': 'Invalid callback data'}), 400


# Register routes
register_routes(app)