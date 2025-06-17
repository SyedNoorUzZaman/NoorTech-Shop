from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['DATABASE'] = os.path.join(app.root_path, 'database.db')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add Jinja filter for JSON handling
@app.template_filter('tojson')
def to_json(value):
    return json.dumps(value)

@app.template_filter('fromjson')
def from_json(value):
    return json.loads(value)

class User(UserMixin):
    def __init__(self, id, username, email, password_hash, profile=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.profile = profile

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            is_super_admin BOOLEAN DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
        );
        
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            image_url TEXT,
            category_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        );
        
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_date TIMESTAMP,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            shipping_info TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            first_name TEXT,
            last_name TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        ''')
        
        # Insert sample categories if they don't exist
        categories = [
            ('Computers', 'Laptops, Desktops, and Accessories'),
            ('Mobile Phones', 'Smartphones and Accessories'),
            ('Keyboards', 'Mechanical and Membrane Keyboards'),
            ('Monitors', 'Gaming and Professional Monitors'),
            ('Audio', 'Headphones, Speakers, and Microphones')
        ]
        
        for cat in categories:
            conn.execute('INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)', cat)
        
        # Insert sample products if no products exist
        if conn.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
            products = [
                ('MacBook Pro 16"', 'Apple M2 Pro, 16GB RAM, 512GB SSD', 2499.99, 10, '/static/images/MacBook-Pro-16.jpg', 1),
                ('Dell XPS 15', 'Intel i9, 32GB RAM, 1TB SSD', 1899.99, 8, '/static/images/Dell-XPS-15.jpg', 1),
                ('iPhone 15 Pro', '256GB, Sierra Blue', 1099.99, 20, '/static/images/iPhone-15-Pro.jpg', 2),
                ('Samsung Galaxy S23', '128GB, Phantom Black', 899.99, 15, '/static/images/Samsung-Galaxy-S23.jpg', 2),
                ('Logitech MX Keys', 'Wireless Illuminated Keyboard', 119.99, 30, '/static/images/Logitech-MX-Keys.jpeg', 3),
                ('Keychron Q1', 'Mechanical Keyboard with QMK', 169.99, 12, '/static/images/Keychron-Q1.jpg', 3),
                ('LG UltraGear 27"', '4K Gaming Monitor, 144Hz', 499.99, 7, '/static/images/LG-UltraGear-27.jpg', 4),
                ('Sony WH-1000XM5', 'Wireless Noise-Cancelling Headphones', 349.99, 25, '/static/images/Sony-WH-1000XM5.jpg', 5)
            ]
            
            for prod in products:
                conn.execute('''
                INSERT INTO products (name, description, price, stock, image_url, category_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', prod)
        
        conn.commit()

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if user_data is None:
        conn.close()
        return None
    
    # Get user profile if exists
    profile_data = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    
    profile = dict(profile_data) if profile_data else None
    
    return User(
        id=user_data['id'],
        username=user_data['username'],
        email=user_data['email'],
        password_hash=user_data['password_hash'],
        profile=profile
    )

@app.route('/')
def home():
    conn = get_db_connection()
    featured_products = conn.execute('''
    SELECT p.*, c.name as category_name
    FROM products p
    JOIN categories c ON p.category_id = c.id
    ORDER BY p.id DESC LIMIT 8
    ''').fetchall()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()
    
    return render_template('index.html', products=featured_products, categories=categories)

@app.route('/products')
def products():
    category_id = request.args.get('category', type=int)
    search_query = request.args.get('search', '')
    
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    
    query = '''
    SELECT p.*, c.name as category_name 
    FROM products p
    JOIN categories c ON p.category_id = c.id
    '''
    params = []
    
    if category_id:
        query += ' WHERE p.category_id = ?'
        params.append(category_id)
        if search_query:
            query += ' AND (p.name LIKE ? OR p.description LIKE ?)'
            params.extend(['%' + search_query + '%', '%' + search_query + '%'])
    elif search_query:
        query += ' WHERE p.name LIKE ? OR p.description LIKE ?'
        params.extend(['%' + search_query + '%', '%' + search_query + '%'])
    
    query += ' ORDER BY p.name'
    
    products = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('products.html', products=products, categories=categories, 
                          current_category=category_id, search_query=search_query)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db_connection()
    product = conn.execute('''
    SELECT p.*, c.name as category_name 
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE p.id = ?
    ''', (product_id,)).fetchone()
    
    related_products = conn.execute('''
    SELECT p.*, c.name as category_name 
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE p.category_id = ? AND p.id != ?
    LIMIT 4
    ''', (product['category_id'], product_id)).fetchall()
    
    conn.close()
    
    if product is None:
        flash('Product not found', 'error')
        return redirect(url_for('products'))
    
    return render_template('product_detail.html', product=product, related_products=related_products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                password_hash=user_data['password_hash']
            )
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        
        flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
            conn.close()
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        if conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
            conn.close()
            flash('Username already taken', 'error')
            return render_template('register.html')
        
        password_hash = generate_password_hash(password)
        
        conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                   (username, email, password_hash))
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/cart')
@login_required
def view_cart():
    conn = get_db_connection()
    cart_items = conn.execute('''
    SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.image_url
    FROM cart c
    JOIN products p ON c.product_id = p.id
    WHERE c.user_id = ?
    ''', (current_user.id,)).fetchall()
    
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    conn.close()
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    
    conn = get_db_connection()
    # Check if product exists and has enough stock
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    
    if not product:
        conn.close()
        flash('Product not found', 'error')
        return redirect(url_for('products'))
    
    if product['stock'] < quantity:
        conn.close()
        flash('Not enough stock available', 'error')
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Check if product already in cart
    cart_item = conn.execute('''
    SELECT * FROM cart WHERE user_id = ? AND product_id = ?
    ''', (current_user.id, product_id)).fetchone()
    
    if cart_item:
        # Update quantity
        new_quantity = cart_item['quantity'] + quantity
        if new_quantity > product['stock']:
            conn.close()
            flash('Cannot add more of this item (stock limit)', 'error')
            return redirect(url_for('product_detail', product_id=product_id))
        
        conn.execute('''
        UPDATE cart SET quantity = ? WHERE id = ?
        ''', (new_quantity, cart_item['id']))
    else:
        # Add new item to cart
        conn.execute('''
        INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)
        ''', (current_user.id, product_id, quantity))
    
    conn.commit()
    conn.close()
    
    flash('Product added to cart', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/update_cart', methods=['POST'])
@login_required
def update_cart():
    cart_id = request.form['cart_id']
    quantity = int(request.form['quantity'])
    
    conn = get_db_connection()
    if quantity > 0:
        # Check if quantity exceeds stock
        cart_item = conn.execute('''
        SELECT c.*, p.stock FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.id = ? AND c.user_id = ?
        ''', (cart_id, current_user.id)).fetchone()
        
        if cart_item and quantity <= cart_item['stock']:
            conn.execute('UPDATE cart SET quantity = ? WHERE id = ? AND user_id = ?',
                       (quantity, cart_id, current_user.id))
        else:
            flash('Cannot update quantity (stock limit)', 'error')
    else:
        conn.execute('DELETE FROM cart WHERE id = ? AND user_id = ?',
                   (cart_id, current_user.id))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Get form data for the order
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        address = request.form.get('address', '')
        city = request.form.get('city', '')
        state = request.form.get('state', '')
        zip_code = request.form.get('zip', '')
        phone = request.form.get('phone', '')
        
        # Check if user wants to save delivery info
        save_info = request.form.get('save_info') == 'on'
        
        if save_info:
            # Check if profile exists
            profile = conn.execute('SELECT id FROM user_profiles WHERE user_id = ?', (current_user.id,)).fetchone()
            
            if profile:
                # Update existing profile
                conn.execute('''
                UPDATE user_profiles
                SET first_name = ?, last_name = ?, address = ?, city = ?, state = ?, zip = ?, phone = ?
                WHERE user_id = ?
                ''', (first_name, last_name, address, city, state, zip_code, phone, current_user.id))
            else:
                # Create new profile
                conn.execute('''
                INSERT INTO user_profiles (user_id, first_name, last_name, address, city, state, zip, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (current_user.id, first_name, last_name, address, city, state, zip_code, phone))
        
        # Get cart items
        cart_items = conn.execute('''
        SELECT c.quantity, p.id as product_id, p.price, p.stock
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
        ''', (current_user.id,)).fetchall()
        
        # Check if cart is empty
        if not cart_items:
            conn.close()
            flash('Your cart is empty', 'error')
            return redirect(url_for('view_cart'))
        
        # Check if all items are in stock
        for item in cart_items:
            if item['quantity'] > item['stock']:
                conn.close()
                flash(f'Some items are out of stock', 'error')
                return redirect(url_for('view_cart'))
        
        # Calculate total
        total_amount = sum(item['price'] * item['quantity'] for item in cart_items)
        
        # Create order with shipping info
        shipping_info = {
            'first_name': first_name,
            'last_name': last_name,
            'address': address,
            'city': city,
            'state': state,
            'zip': zip_code,
            'phone': phone
        }
        
        cur = conn.cursor()
        cur.execute('''
        INSERT INTO orders (user_id, order_date, total_amount, status, shipping_info)
        VALUES (?, ?, ?, ?, ?)
        ''', (current_user.id, datetime.now().isoformat(), total_amount, 'Pending', json.dumps(shipping_info)))
        
        order_id = cur.lastrowid
        
        # Add order items and update stock
        for item in cart_items:
            conn.execute('''
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES (?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['quantity'], item['price']))
            
            conn.execute('''
            UPDATE products SET stock = stock - ? WHERE id = ?
            ''', (item['quantity'], item['product_id']))
        
        # Clear cart
        conn.execute('DELETE FROM cart WHERE user_id = ?', (current_user.id,))
        
        conn.commit()
        conn.close()
        
        flash('Order placed successfully!', 'success')
        return redirect(url_for('order_confirmation', order_id=order_id))
    
    cart_items = conn.execute('''
    SELECT c.quantity, p.id as product_id, p.name, p.price, p.image_url
    FROM cart c
    JOIN products p ON c.product_id = p.id
    WHERE c.user_id = ?
    ''', (current_user.id,)).fetchall()
    
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    # Get user profile if exists for auto-filling
    profile = None
    if current_user.is_authenticated:
        profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', (current_user.id,)).fetchone()
    
    conn.close()
    
    if not cart_items:
        flash('Your cart is empty', 'error')
        return redirect(url_for('view_cart'))
    
    return render_template('checkout.html', cart_items=cart_items, total=total, profile=profile)

@app.route('/order_confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    conn = get_db_connection()
    
    order = conn.execute('''
    SELECT * FROM orders WHERE id = ? AND user_id = ?
    ''', (order_id, current_user.id)).fetchone()
    
    if not order:
        conn.close()
        flash('Order not found', 'error')
        return redirect(url_for('home'))
    
    order_items = conn.execute('''
    SELECT oi.*, p.name, p.image_url
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    
    conn.close()
    
    return render_template('order_confirmation.html', order=order, order_items=order_items)

@app.route('/orders')
@login_required
def order_history():
    conn = get_db_connection()
    
    orders = conn.execute('''
    SELECT * FROM orders WHERE user_id = ? ORDER BY order_date DESC
    ''', (current_user.id,)).fetchall()
    
    conn.close()
    
    return render_template('orders.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    conn = get_db_connection()
    
    order = conn.execute('''
    SELECT * FROM orders WHERE id = ? AND user_id = ?
    ''', (order_id, current_user.id)).fetchone()
    
    if not order:
        conn.close()
        flash('Order not found', 'error')
        return redirect(url_for('orders'))
    
    order_items = conn.execute('''
    SELECT oi.*, p.name, p.image_url
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    
    conn.close()
    
    return render_template('order_detail.html', order=order, order_items=order_items)

@app.route('/track', methods=['GET', 'POST'])
def track_order():
    order = None
    order_items = None
    tracking_id = request.args.get('order_id') or (request.form.get('order_id') if request.method == 'POST' else None)
    
    if tracking_id:
        try:
            order_id = int(tracking_id)
            conn = get_db_connection()
            
            order = conn.execute('''
            SELECT id, order_date, status, total_amount FROM orders WHERE id = ?
            ''', (order_id,)).fetchone()
            
            if order:
                order_items = conn.execute('''
                SELECT oi.quantity, oi.price, p.name, p.image_url
                FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ?
                ''', (order_id,)).fetchall()
                
            conn.close()
        except ValueError:
            flash('Invalid order ID', 'error')
    
    return render_template('track_order.html', order=order, order_items=order_items, tracking_id=tracking_id)

@app.route('/profile')
@login_required
def view_profile():
    return render_template('profile.html')

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        address = request.form.get('address', '')
        city = request.form.get('city', '')
        state = request.form.get('state', '')
        zip_code = request.form.get('zip', '')
        phone = request.form.get('phone', '')
        
        conn = get_db_connection()
        
        # Check if profile exists
        profile = conn.execute('SELECT id FROM user_profiles WHERE user_id = ?', (current_user.id,)).fetchone()
        
        if profile:
            # Update existing profile
            conn.execute('''
            UPDATE user_profiles
            SET first_name = ?, last_name = ?, address = ?, city = ?, state = ?, zip = ?, phone = ?
            WHERE user_id = ?
            ''', (first_name, last_name, address, city, state, zip_code, phone, current_user.id))
        else:
            # Create new profile
            conn.execute('''
            INSERT INTO user_profiles (user_id, first_name, last_name, address, city, state, zip, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (current_user.id, first_name, last_name, address, city, state, zip_code, phone))
        
        conn.commit()
        conn.close()
        
        # Reload user to refresh profile data
        load_user(current_user.id)
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('view_profile'))
        
    return render_template('edit_profile.html')

def create_admin_user():
    """Create default admin user if it doesn't exist"""
    with get_db_connection() as conn:
        admin = conn.execute('SELECT * FROM admin_users WHERE username = ?', ('admin',)).fetchone()
        if not admin:
            # Create default admin user with username: admin, password: admin
            password_hash = generate_password_hash('admin')
            conn.execute(
                'INSERT INTO admin_users (username, password_hash, email, is_super_admin) VALUES (?, ?, ?, ?)',
                ('admin', password_hash, 'admin@example.com', 1)
            )
            conn.commit()
            print("Default admin user created: username='admin', password='admin'")

if __name__ == '__main__':
    # Create DB tables if they don't exist
    if not os.path.exists(app.config['DATABASE']):
        init_db()
        
    # Create admin user if it doesn't exist
    create_admin_user()
        
    # Run app on all network interfaces (0.0.0.0) so it's accessible via server IP
    app.run(host='0.0.0.0', port=5000, debug=True) 