# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Orfe-Cosmatics is a multi-platform business suite containing three Flask applications:

1. **Main App** (`app.py`) - E-commerce platform for cosmetics/beauty products
2. **EduCore** (`EduCore/`) - Educational platform with courses, quizzes, and certificates
3. **JinToGoDash** (`JinToGoDash/`) - Logistics and shipment management system

All applications use SQLite databases, Flask-SQLAlchemy ORM, and Jinja2 templating with Tailwind CSS.

## Running the Applications

```bash
# Main E-Commerce App (port 5000)
pip install -r requirements.txt
python app.py

# EduCore Educational Platform (port 6000)
pip install -r EduCore/requirements.txt
python EduCore/run.py

# JinToGoDash Logistics System (port 1234)
pip install -r JinToGoDash/requirements.txt
python JinToGoDash/main.py
```

## Database Migrations (JinToGoDash only)

```bash
cd JinToGoDash
flask db migrate -m "description"
flask db upgrade
```

## Architecture

### Main App (`app.py`)
- Monolithic Flask application (~131KB) with inline model definitions
- Models: Admins, Guests, Products, Categories, Cart, Orders, AdditionalImages, AdditionalData
- Database: `instance/orfe-shop.sqlite3`
- Integrations: Bosta API (shipping via `models/bosta.py`), Fawaterk API (payments)
- Features: automatic project backup with Git, Honeybadger error tracking (optional)

### EduCore (`EduCore/`)
- Blueprint-based architecture with factory pattern (`create_app()`)
- Entry point: `run.py` which imports from `models.py` and `routes/`
- Blueprints: auth, dashboard, courses, profile, instructor, purchase, quiz, admin
- Database: `EduCore/educore.db`
- Authentication: Flask-Login
- Models: User, Course, Lesson, Enrollment, Quiz, QuizQuestion, Purchase, Certificate, DiscountCode, etc.
- Test credentials: username `ahmed`, password `password123`

### JinToGoDash (`JinToGoDash/`)
- Enterprise-grade Flask with Flask-Migrate
- Entry point: `main.py` → `app/__init__.py` (factory pattern)
- Blueprints in `app/blueprints/`: auth, dashboard, shipments, clients, customs, expenses, analytics, reports, data, errors, settings
- Models in `app/models/`: user.py, models.py (shipments, clients), expense.py
- Database: uses Flask-Migrate for schema management
- Features: CSRF protection, Arabic PDF support (WeasyPrint, arabic-reshaper)

## External Services

- **Bosta API**: Egyptian shipping service integration (`models/bosta.py`)
- **Fawaterk API**: Payment gateway (configured in main app.py)
- **Honeybadger**: Error tracking (optional, gracefully fails if unavailable)

## Language & Localization

- UI and comments are in Arabic (Egyptian Arabic)
- Arabic text rendering in PDFs uses `arabic-reshaper` and `python-bidi`

## Key Files

- `app.py` - Main e-commerce application entry point and all models/routes
- `models/bosta.py` - Bosta shipping API wrapper
- `EduCore/run.py` - EduCore entry point with app factory
- `EduCore/models.py` - All EduCore database models
- `JinToGoDash/main.py` - JinToGoDash entry point
- `JinToGoDash/app/__init__.py` - JinToGoDash app factory
- `JinToGoDash/config.py` - JinToGoDash configuration management
