from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db
from decimal import Decimal

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(256), nullable=True)
    city = db.Column(db.String(64), nullable=True)
    country = db.Column(db.String(64), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), default='customer', nullable=False)  # admin, helpdesk, customer, installer, driver
    account_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    orders = db.relationship('Order', backref='user', lazy=True)
    cart = db.relationship('Cart', backref='user', uselist=False, lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship('Review', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_helpdesk(self):
        return self.role == 'helpdesk'
    
    def is_customer(self):
        return self.role == 'customer'
    
    def is_installer(self):
        return self.role == 'installer'
        
    def is_driver(self):
        return self.role == 'driver'
    
    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    
    products = db.relationship('Product', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0, nullable=False)
    image_url = db.Column(db.String(256), nullable=True)
    slug = db.Column(db.String(128), unique=True, nullable=False)
    featured = db.Column(db.Boolean, default=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    reviews = db.relationship('Review', backref='product', lazy=True)
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    def average_rating(self):
        if not self.reviews:
            return 0
        
        total = sum(review.rating for review in self.reviews)
        return total / len(self.reviews)

class Cart(db.Model):
    __tablename__ = 'carts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('CartItem', backref='cart', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Cart {self.id} for User {self.user_id}>'
    
    def total(self):
        total = sum(item.subtotal() for item in self.items)
        return total

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    
    def __repr__(self):
        return f'<CartItem {self.id} - {self.quantity} x Product {self.product_id}>'
    
    def subtotal(self):
        return Decimal(self.product.price) * self.quantity

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    orders = db.relationship('Order', backref='payment_method', lazy=True)
    
    def __repr__(self):
        return f'<PaymentMethod {self.name}>'

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_methods.id'), nullable=False)
    status = db.Column(db.String(32), default='pending', nullable=False)  # pending, paid, shipped, delivered, cancelled
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_address = db.Column(db.String(256), nullable=False)
    shipping_city = db.Column(db.String(64), nullable=False)
    shipping_country = db.Column(db.String(64), nullable=False)
    shipping_postal_code = db.Column(db.String(20), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)
    contact_email = db.Column(db.String(120), nullable=False)
    payment_reference = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")
    delivery_comments = db.relationship('DeliveryComment', backref='order', lazy=True, cascade="all, delete-orphan")
    installation_comments = db.relationship('InstallationComment', backref='order', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Order {self.id}>'

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    
    def __repr__(self):
        return f'<OrderItem {self.id}>'
    
    def subtotal(self):
        return self.price * self.quantity

class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Review {self.id} - {self.rating} stars>'


class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(32), default='open', nullable=False)  # open, in_progress, resolved, closed
    priority = db.Column(db.String(32), default='medium', nullable=False)  # low, medium, high, urgent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='support_tickets', lazy=True)
    messages = db.relationship('TicketMessage', backref='ticket', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<SupportTicket {self.id} - {self.subject}>'


class TicketMessage(db.Model):
    __tablename__ = 'ticket_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_staff_reply = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='ticket_messages', lazy=True)
    
    def __repr__(self):
        return f'<TicketMessage {self.id} for Ticket {self.ticket_id}>'


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for anonymous chats
    session_token = db.Column(db.String(128), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<ChatSession {self.id} - Active: {self.is_active}>'


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    is_staff_message = db.Column(db.Boolean, default=False, nullable=False)
    is_system_message = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChatMessage {self.id} in Session {self.session_id}>'


class InvoiceTemplate(db.Model):
    __tablename__ = 'invoice_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    template_type = db.Column(db.String(32), nullable=False)  # 'invoice', 'receipt', 'quote'
    company_name = db.Column(db.String(256), default='Mo Solar Technologies')
    company_address = db.Column(db.Text, nullable=True)
    company_phone = db.Column(db.String(32), nullable=True)
    company_email = db.Column(db.String(128), nullable=True)
    company_logo_url = db.Column(db.String(256), nullable=True)
    header_text = db.Column(db.Text, nullable=True)
    footer_text = db.Column(db.Text, nullable=True)
    terms_conditions = db.Column(db.Text, nullable=True)
    payment_instructions = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<InvoiceTemplate {self.name}>'


class DeliveryComment(db.Model):
    __tablename__ = 'delivery_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    delivery_status = db.Column(db.String(32), nullable=False)  # delivered, attempted, rescheduled, issue
    delivery_rating = db.Column(db.Integer, nullable=True)  # 1-5 rating for delivery experience
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    driver = db.relationship('User', backref='delivery_comments', lazy=True)
    
    def __repr__(self):
        return f'<DeliveryComment {self.id} for Order {self.order_id}>'


class InstallationComment(db.Model):
    __tablename__ = 'installation_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    installer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    installation_status = db.Column(db.String(32), nullable=False)  # scheduled, in_progress, completed, on_hold, cancelled
    technical_notes = db.Column(db.Text, nullable=True)  # Technical specifications or issues
    completion_percentage = db.Column(db.Integer, default=0, nullable=False)  # 0-100%
    estimated_completion_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    installer = db.relationship('User', backref='installation_comments', lazy=True)
    
    def __repr__(self):
        return f'<InstallationComment {self.id} for Order {self.order_id}>'