# ElectroShop Admin Panel

This is the admin panel for the ElectroShop e-commerce application. It provides an interface for managing products, categories, orders, customers, and admin users.

## Features

- Dashboard with key metrics and information
- Product management (add, edit, delete)
- Category management
- Order tracking and management
- Customer information
- Admin user management (for super admins)
- Responsive design using Tailwind CSS

## Running the Admin Panel

1. Make sure the main Flask application has been run at least once to initialize the database.

2. Navigate to the admin folder and run the admin application:
   ```
   cd admin
   python run.py
   ```

3. Open your browser and go to:
   ```
   http://localhost:5001
   ```

4. Login with the default credentials:
   - Username: admin
   - Password: admin

## Security Notes

- The admin panel runs on a different port (5001) than the main application.
- Change the default admin password after first login.
- Only give super admin privileges to trusted users.

## Default Permissions

There are two types of admin users:
- Regular Admin: Can manage products, categories, orders, and view customers
- Super Admin: Can also manage other admin users 