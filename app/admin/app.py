from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import json
from datetime import datetime
from functools import wraps
import uuid
import shutil

# Configure app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'admin_secret_key'
app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'images')
app.config['MAIN_UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload size

# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MAIN_UPLOAD_FOLDER'], exist_ok=True)

# Check allowed file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Database connection
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    if 'db' in g:
        g.db.close()

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Check if admin table exists and create default admin
def create_admin_user():
    conn = get_db()
    
    # Check if admin_users table exists
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_users'")
    if not cursor.fetchone():
        print("Creating admin_users table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            is_super_admin BOOLEAN DEFAULT 0
        )
        ''')
        conn.commit()
    
    # Check if admin user exists
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

# Routes
@app.route('/')
@admin_required
def index():
    db = get_db()
    
    # Get counts for dashboard
    products_count = db.execute('SELECT COUNT(*) as count FROM products').fetchone()['count']
    orders_count = db.execute('SELECT COUNT(*) as count FROM orders').fetchone()['count']
    users_count = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    categories_count = db.execute('SELECT COUNT(*) as count FROM categories').fetchone()['count']
    
    # Get recent orders
    recent_orders = db.execute('''
    SELECT o.id, o.order_date, o.total_amount, o.status, u.username
    FROM orders o
    JOIN users u ON o.user_id = u.id
    ORDER BY o.order_date DESC LIMIT 5
    ''').fetchall()
    
    # Get low stock products
    low_stock = db.execute('''
    SELECT id, name, stock FROM products WHERE stock < 5
    ORDER BY stock ASC LIMIT 5
    ''').fetchall()
    
    return render_template(
        'index.html', 
        products_count=products_count,
        orders_count=orders_count,
        users_count=users_count,
        categories_count=categories_count,
        recent_orders=recent_orders,
        low_stock=low_stock
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        admin = db.execute('SELECT * FROM admin_users WHERE username = ?', (username,)).fetchone()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            session['is_super_admin'] = bool(admin['is_super_admin'])
            flash('Login successful', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

# Products
@app.route('/products')
@admin_required
def products():
    db = get_db()
    products = db.execute('''
    SELECT p.*, c.name as category_name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    ORDER BY p.id DESC
    ''').fetchall()
    
    return render_template('products.html', products=products)

@app.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    db = get_db()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        category_id = int(request.form['category_id'])
        image_url = request.form['image_url']
        
        # Handle image upload if provided
        if 'product_image' in request.files and request.files['product_image'].filename:
            file = request.files['product_image']
            if file and allowed_file(file.filename):
                # Create a unique filename to avoid collisions
                filename = secure_filename(file.filename)
                file_ext = os.path.splitext(filename)[1]
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                
                # Save file in admin static folder
                admin_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(admin_file_path)
                
                # Save a copy in the main static folder
                main_file_path = os.path.join(app.config['MAIN_UPLOAD_FOLDER'], unique_filename)
                shutil.copy2(admin_file_path, main_file_path)
                
                # Update image_url to point to the saved file in the main static folder
                image_url = f"static/images/{unique_filename}"
        elif not image_url:
            # If no image uploaded or URL provided, use placeholder
            image_url = "static/images/placeholder.jpg"
        
        db.execute('''
        INSERT INTO products (name, description, price, stock, category_id, image_url)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, price, stock, category_id, image_url))
        db.commit()
        
        flash('Product added successfully', 'success')
        return redirect(url_for('products'))
    
    # Get categories for dropdown
    categories = db.execute('SELECT id, name FROM categories ORDER BY name').fetchall()
    return render_template('product_form.html', categories=categories, product=None)

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        category_id = int(request.form['category_id'])
        image_url = request.form['image_url']
        
        # Handle image upload if provided
        if 'product_image' in request.files and request.files['product_image'].filename:
            file = request.files['product_image']
            if file and allowed_file(file.filename):
                # Create a unique filename to avoid collisions
                filename = secure_filename(file.filename)
                file_ext = os.path.splitext(filename)[1]
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                
                # Save file in admin static folder
                admin_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(admin_file_path)
                
                # Save a copy in the main static folder
                main_file_path = os.path.join(app.config['MAIN_UPLOAD_FOLDER'], unique_filename)
                shutil.copy2(admin_file_path, main_file_path)
                
                # Update image_url to point to the saved file in the main static folder
                image_url = f"static/images/{unique_filename}"
        elif not image_url:
            # If no image uploaded or URL provided, use placeholder
            image_url = "static/images/placeholder.jpg"
        
        db.execute('''
        UPDATE products 
        SET name = ?, description = ?, price = ?, stock = ?, category_id = ?, image_url = ?
        WHERE id = ?
        ''', (name, description, price, stock, category_id, image_url, product_id))
        db.commit()
        
        flash('Product updated successfully', 'success')
        return redirect(url_for('products'))
    
    # Get categories for dropdown
    categories = db.execute('SELECT id, name FROM categories ORDER BY name').fetchall()
    return render_template('product_form.html', categories=categories, product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    db = get_db()
    db.execute('DELETE FROM products WHERE id = ?', (product_id,))
    db.commit()
    
    flash('Product deleted successfully', 'success')
    return redirect(url_for('products'))

# Categories
@app.route('/categories')
@admin_required
def categories():
    db = get_db()
    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    
    return render_template('categories.html', categories=categories)

@app.route('/categories/add', methods=['GET', 'POST'])
@admin_required
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        
        db = get_db()
        db.execute('''
        INSERT INTO categories (name, description)
        VALUES (?, ?)
        ''', (name, description))
        db.commit()
        
        flash('Category added successfully', 'success')
        return redirect(url_for('categories'))
    
    return render_template('category_form.html', category=None)

@app.route('/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def edit_category(category_id):
    db = get_db()
    category = db.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
    
    if not category:
        flash('Category not found', 'error')
        return redirect(url_for('categories'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        
        db.execute('''
        UPDATE categories
        SET name = ?, description = ?
        WHERE id = ?
        ''', (name, description, category_id))
        db.commit()
        
        flash('Category updated successfully', 'success')
        return redirect(url_for('categories'))
    
    return render_template('category_form.html', category=category)

@app.route('/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def delete_category(category_id):
    db = get_db()
    
    # Check if category is used by any products
    product_count = db.execute('SELECT COUNT(*) as count FROM products WHERE category_id = ?', 
                               (category_id,)).fetchone()['count']
    
    if product_count > 0:
        flash(f'Cannot delete category: {product_count} products are using this category', 'error')
        return redirect(url_for('categories'))
    
    db.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    db.commit()
    
    flash('Category deleted successfully', 'success')
    return redirect(url_for('categories'))

# Orders
@app.route('/orders')
@admin_required
def orders():
    db = get_db()
    orders = db.execute('''
    SELECT o.*, u.username
    FROM orders o
    JOIN users u ON o.user_id = u.id
    ORDER BY o.order_date DESC
    ''').fetchall()
    
    return render_template('orders.html', orders=orders)

@app.route('/orders/<int:order_id>')
@admin_required
def order_detail(order_id):
    db = get_db()
    
    order = db.execute('''
    SELECT o.*, u.username, u.email
    FROM orders o
    JOIN users u ON o.user_id = u.id
    WHERE o.id = ?
    ''', (order_id,)).fetchone()
    
    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('orders'))
    
    order_items = db.execute('''
    SELECT oi.*, p.name, p.image_url
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    
    # Parse shipping info if available
    shipping_info = None
    if order['shipping_info']:
        try:
            shipping_info = json.loads(order['shipping_info'])
        except json.JSONDecodeError:
            shipping_info = None
    
    return render_template(
        'order_detail.html', 
        order=order, 
        order_items=order_items,
        shipping_info=shipping_info
    )

@app.route('/orders/<int:order_id>/update-status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    new_status = request.form['status']
    
    db = get_db()
    db.execute('UPDATE orders SET status = ? WHERE id = ?', (new_status, order_id))
    db.commit()
    
    flash('Order status updated successfully', 'success')
    return redirect(url_for('order_detail', order_id=order_id))

# Users
@app.route('/users')
@admin_required
def users():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY username').fetchall()
    
    return render_template('users.html', users=users)

@app.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    db = get_db()
    
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('users'))
    
    # Get user profile if exists
    profile = db.execute('SELECT * FROM user_profiles WHERE user_id = ?', (user_id,)).fetchone()
    
    # Get user orders
    orders = db.execute('''
    SELECT id, order_date, total_amount, status
    FROM orders
    WHERE user_id = ?
    ORDER BY order_date DESC
    ''', (user_id,)).fetchall()
    
    return render_template('user_detail.html', user=user, profile=profile, orders=orders)

# Admin users management
@app.route('/admin-users')
@admin_required
def admin_users():
    if not session.get('is_super_admin'):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    
    db = get_db()
    admins = db.execute('SELECT * FROM admin_users ORDER BY username').fetchall()
    
    return render_template('admin_users.html', admins=admins)

@app.route('/admin-users/add', methods=['GET', 'POST'])
@admin_required
def add_admin_user():
    if not session.get('is_super_admin'):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        is_super_admin = request.form.get('is_super_admin') == 'on'
        
        db = get_db()
        
        # Check if username already exists
        existing_user = db.execute('SELECT id FROM admin_users WHERE username = ?', (username,)).fetchone()
        if existing_user:
            flash('Username already exists', 'error')
            return render_template('admin_user_form.html')
        
        password_hash = generate_password_hash(password)
        
        db.execute('''
        INSERT INTO admin_users (username, password_hash, email, is_super_admin)
        VALUES (?, ?, ?, ?)
        ''', (username, password_hash, email, is_super_admin))
        db.commit()
        
        flash('Admin user added successfully', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin_user_form.html', admin=None)

@app.route('/admin-users/edit/<int:admin_id>', methods=['GET', 'POST'])
@admin_required
def edit_admin_user(admin_id):
    if not session.get('is_super_admin'):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    
    db = get_db()
    admin = db.execute('SELECT * FROM admin_users WHERE id = ?', (admin_id,)).fetchone()
    
    if not admin:
        flash('Admin user not found', 'error')
        return redirect(url_for('admin_users'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        is_super_admin = request.form.get('is_super_admin') == 'on'
        password = request.form.get('password')
        
        # Check if username already exists for different admin
        existing_user = db.execute('SELECT id FROM admin_users WHERE username = ? AND id != ?', 
                                  (username, admin_id)).fetchone()
        if existing_user:
            flash('Username already exists', 'error')
            return render_template('admin_user_form.html', admin=admin)
        
        if password:
            # Update with new password
            password_hash = generate_password_hash(password)
            db.execute('''
            UPDATE admin_users
            SET username = ?, password_hash = ?, email = ?, is_super_admin = ?
            WHERE id = ?
            ''', (username, password_hash, email, is_super_admin, admin_id))
        else:
            # Update without changing password
            db.execute('''
            UPDATE admin_users
            SET username = ?, email = ?, is_super_admin = ?
            WHERE id = ?
            ''', (username, email, is_super_admin, admin_id))
        
        db.commit()
        
        flash('Admin user updated successfully', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin_user_form.html', admin=admin)

@app.route('/admin-users/delete/<int:admin_id>', methods=['POST'])
@admin_required
def delete_admin_user(admin_id):
    if not session.get('is_super_admin'):
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    
    # Prevent deleting yourself
    if int(session['admin_id']) == admin_id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin_users'))
    
    db = get_db()
    db.execute('DELETE FROM admin_users WHERE id = ?', (admin_id,))
    db.commit()
    
    flash('Admin user deleted successfully', 'success')
    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    with app.app_context():
        create_admin_user()
    # Run app on all network interfaces (0.0.0.0) so it's accessible via server IP
    app.run(host='0.0.0.0', port=5001, debug=True) 