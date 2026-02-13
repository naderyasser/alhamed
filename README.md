# 🛍️ Orfe Cosmetics - E-commerce Platform

<div align="center">
  <img src="https://k.top4top.io/p_3515e1v1u1.png" alt="Orfe Cosmetics Logo" width="200"/>
  
  **A complete Arabic e-commerce platform for beauty products**
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
  [![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
</div>

## 📋 Overview

Orfe Cosmetics is a full-featured e-commerce platform built with Flask, designed specifically for Arabic-speaking markets. It provides a complete solution for online beauty product sales with advanced features for both customers and administrators.

## ✨ Features

### 🛒 Customer Features
- **Product Browsing**: Browse products by category with advanced filtering and search
- **Shopping Cart**: Full cart management with quantity controls
- **Multiple Payment Methods**: 
  - Credit Card (via Fawaterak)
  - Vodafone Cash
  - Cash on Delivery
- **Smart Shipping**: Dynamic shipping costs based on city and district
- **Promotions & Discounts**: 
  - Automatic promotional discounts
  - Combo offers
  - Special holiday promotions
- **Order Tracking**: Real-time order status updates
- **WhatsApp Integration**: Direct contact via WhatsApp for support

### 👨‍💼 Admin Features
- **Dashboard**: Comprehensive analytics and statistics
- **Product Management**: Full CRUD operations for products
- **Category Management**: Organize products by categories
- **Order Management**: 
  - View and manage all orders
  - Update shipping status
  - Track order details
  - Export to Excel
- **Shipping Management**: 
  - Manage cities, zones, and districts
  - Configure shipping costs
- **Revenue Analytics**: 
  - Income statistics
  - Product performance reports
  - Export financial reports
- **Backup System**: Automated project backups
- **Discord Notifications**: Real-time order alerts

## 🚀 Tech Stack

- **Backend**: Flask (Python 3.8+)
- **Server**: Gunicorn (3 workers)
- **Database**: SQLite
- **Payment**: Fawaterak API
- **Shipping**: Bosta Service
- **Notifications**: Discord Webhooks
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Git

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/naderyasser/Ecommerce.git
cd Ecommerce
```

2. **Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize the database**
```bash
python app.py
```

6. **Run the application**
```bash
python app.py
```

The application will be available at `http://localhost:6000`

### Production Deployment

For production, use Gunicorn:
```bash
gunicorn -w 3 -b 0.0.0.0:6000 app:app
```

## 📁 Project Structure

```
Orfe-cosmatics/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env.example         # Environment variables template
├── .gitignore          # Git ignore rules
├── models/             # Database models
│   ├── __init__.py
│   ├── admin.py
│   ├── product.py
│   └── ...
├── templates/          # HTML templates
│   ├── shop/         # Customer-facing templates
│   └── admin/        # Admin panel templates
├── static/            # Static assets
│   ├── css/
│   ├── js/
│   └── img/
├── instance/          # Database and session files
├── data/             # Additional data files
└── logs/             # Application logs
```

## 🔑 Default Admin Credentials

⚠️ **Important**: Change these credentials immediately after first login!

- **Email**: `orfecosmetics@gmail.com`
- **Password**: `Orfe196196`

Access admin panel at: `http://localhost:6000/admin`

## 🗄️ Database Schema

### Core Tables
- `Admins` - Administrator accounts
- `Product` - Product catalog
- `Category` - Product categories
- `Order` - Customer orders
- `OrderItem` - Order line items
- `Cart` - Shopping cart items
- `Guests` - Guest customers
- `City` - Shipping cities
- `Zone` - City zones
- `District` - City districts
- `ShippingCost` - Shipping cost configuration
- `PromoCode` - Discount codes

## 🌐 API Endpoints

### Public APIs
- `GET /api/cities` - List all cities
- `GET /api/zones?city_id=<id>` - Get zones for a city
- `GET /api/districts?city_id=<id>` - Get districts for a city
- `GET /api/shipping-cost?city_id=<id>` - Calculate shipping cost

### Admin APIs
- `GET /admin/orders` - List all orders
- `GET /admin/order/<id>` - Get order details
- `POST /admin/add_product` - Add new product
- `POST /admin/update_shipping_cost` - Update shipping cost

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite:///instance/orfe-shop.sqlite3

# Payment API
FAWATERAK_API_KEY=your-api-key
FAWATERAK_API_URL=https://app.fawaterk.com/api/v2/createInvoiceLink

# Error Tracking (Optional)
HONEYBADGER_API_KEY=your-honeybadger-key
HONEYBADGER_ENVIRONMENT=production

# Discord Webhook (Optional)
DISCORD_WEBHOOK_URL=your-webhook-url

# Server
HOST=0.0.0.0
PORT=6000
DEBUG=False
```

## 📊 Features in Detail

### Smart Discount System
- **Promotional Discounts**: Automatic percentage discounts for limited periods
- **Combo Offers**: Free shipping for specific product combinations
- **Holiday Specials**: Special offers for occasions (Eid, etc.)

### Advanced Shipping
- **Multi-level Geography**: City → Zone → District hierarchy
- **Dynamic Pricing**: Shipping costs vary by location
- **Discount Integration**: Free shipping based on order content

### Payment Integration
- **Fawaterak**: Secure online payments
- **Vodafone Cash**: Mobile wallet payments
- **COD**: Traditional cash on delivery

## 🤝 Contributing

We welcome contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support & Contact

- **Email**: orfecosmetics@gmail.com
- **Website**: [orfe-cosmetics.com](https://orfe-cosmetics.com)
- **Issues**: [GitHub Issues](https://github.com/naderyasser/Ecommerce/issues)

## 🙏 Acknowledgments

- Flask Framework
- Bootstrap 5
- Fawaterak Payment Gateway
- Bosta Shipping Service
- Honeybadger Error Tracking

## 📸 Screenshots

<div align="center">
  <h3>Storefront</h3>
  <img src="https://via.placeholder.com/800x400?text=Storefront+Screenshot" alt="Storefront" width="800"/>
  
  <h3>Admin Dashboard</h3>
  <img src="https://via.placeholder.com/800x400?text=Admin+Dashboard+Screenshot" alt="Admin Dashboard" width="800"/>
</div>

---

<div align="center">
  <b>Built with ❤️ by Orfe Cosmetics Team</b>
  
  [⬆ Back to top](#-orfe-cosmetics---e-commerce-platform)
</div>
