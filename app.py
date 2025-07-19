from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
import os
from dotenv import load_dotenv
from models import db, User, Expense
from config import config

# Getting .env variables from said file
load_dotenv()

app = Flask(__name__)

# Development or production based on environment
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config.get(env, 'development'))  # Default to development

# Initialize database with app
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Where to redirect if not logged in


# This tells Flask-Login how to find a user
@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))


# Create database tables
with app.app_context():
    db.create_all()
    print("✅ Database tables created!")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()

        # Get form data
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400

        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)  # Hash the password

        # Save to database
        db.session.add(user)
        db.session.commit()

        # Log them in automatically
        login_user(user)

        return jsonify({'message': 'Registration successful!'}), 201

    # GET request - show registration page
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()

        # Get login credentials
        username = data.get('username')
        password = data.get('password')

        # Find user
        user = User.query.filter_by(username=username).first()

        # Check password
        if user and user.check_password(password):
            login_user(user, remember=True)  # Remember for 7 days
            return jsonify({'message': 'Login successful!'}), 200

        return jsonify({'error': 'Invalid username or password'}), 401

    # GET request - show login page
    return render_template('login.html')

@app.route('/logout')
@login_required  # Must be logged in to logout
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required  # Must be logged in to see dashboard
def home():
    return render_template('index.html', username=current_user.username)

@app.route('/api/expenses', methods=['GET'])
@login_required
def get_expenses():
    # Query only expenses belonging to current user
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()

    # Convert to list of dictionaries
    return jsonify([expense.to_dict() for expense in expenses])

@app.route('/api/expenses', methods=['POST'])
@login_required
def add_expense():
    data = request.json

    # Create new expense linked to current user
    expense = Expense(
        amount=float(data['amount']),
        description=data['description'],
        category=data['category'],
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        user_id=current_user.id  # Link to logged-in user
    )

    # Save to database
    db.session.add(expense)
    db.session.commit()

    return jsonify({
        'message': 'Expense added!',
        'expense': expense.to_dict()
    }), 201


@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    # Find expense and check ownership
    expense = Expense.query.filter_by(
        id=expense_id,
        user_id=current_user.id  # Security: only delete own expenses
    ).first()

    if not expense:
        return jsonify({'error': 'Expense not found'}), 404

    # Delete from database
    db.session.delete(expense)
    db.session.commit()

    return jsonify({'message': 'Expense deleted!'}), 200

@app.route('/api/export/csv')
@login_required
def export_csv():
    import csv
    import io

    # Get user's expenses
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['Date', 'Description', 'Category', 'Amount'])

    # Data
    for expense in expenses:
        writer.writerow([
            expense.date.strftime('%Y-%m-%d'),
            expense.description,
            expense.category,
            f"${expense.amount:.2f}"
        ])

    csv_content = output.getvalue()

    return csv_content, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': f'attachment; filename={current_user.username}_expenses.csv'
    }

@app.route('/api/analytics/summary')
@login_required
def get_analytics_summary():
    # We'll implement this in Phase 4
    return jsonify({'message': 'Analytics coming soon!'})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'error': 'Please login first'}), 401

if __name__ == '__main__':
    # Create folders if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    app.run(debug=True, port=5001)