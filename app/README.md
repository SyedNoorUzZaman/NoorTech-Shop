# ElectroShop - Electronic Products Marketplace

A web application for selling electronic products built with Flask, SQLite, and Tailwind CSS.

## Features

- User authentication (register, login, logout)
- Product browsing with categories
- Product search functionality
- Product details with related products
- Shopping cart
- Checkout process
- Order history and tracking

## Technologies Used

- Backend: Python Flask
- Database: SQLite
- Frontend: HTML, Tailwind CSS, JavaScript
- Authentication: Flask-Login

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd electric-product-market
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows:
     ```
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Run the application:
   ```
   python app.py
   ```

6. Access the application:
   - Locally:
     ```
     http://127.0.0.1:5000
     ```
   - From another device using the server's IP address:
     ```
     http://<server-ip-address>:5000
     ```
     Replace `<server-ip-address>` with your server's actual IP address (e.g., 192.168.1.100)

## Accessing via Server IP Address

The application is configured to listen on all network interfaces (0.0.0.0), which means you can access it from any device on the same network using the server's IP address.

To find your server's IP address:
- On Windows: Open Command Prompt and type `ipconfig`
- On Linux/macOS: Open Terminal and type `ifconfig` or `ip addr show`

Then access the application using: `http://<server-ip-address>:5000`

## Database Structure

The application uses SQLite with the following main tables:
- users: User accounts and authentication
- categories: Product categories
- products: Product information
- cart: Shopping cart items
- orders: Order information
- order_items: Items within each order

## Default Accounts

For testing, you can register a new account or use the application as a guest to browse products.

## License

This project is open-source and available under the MIT License. 