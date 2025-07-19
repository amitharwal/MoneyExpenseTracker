from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Create database object
db = SQLAlchemy()


# Stores user accounts
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    # Columns
    id = db.Column(db.Integer, primary_key=True)  # Unique ID for each user
    username = db.Column(db.String(80), unique=True, nullable=False)  # Login name
    email = db.Column(db.String(120), unique=True, nullable=False)  # Email address
    password_hash = db.Column(db.String(200))  # Encrypted password
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # When they joined

    # Relationship
    expenses = db.relationship('Expense', backref='user', lazy=True)

    def set_password(self, password):
        """Hash the password - never store plain text passwords!"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches the hash"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


# Stores all expenses
class Expense(db.Model):
    __tablename__ = 'expenses'

    # Columns
    id = db.Column(db.Integer, primary_key=True)  # Unique ID
    amount = db.Column(db.Float, nullable=False)  # How much was spent
    description = db.Column(db.String(200), nullable=False)  # What it was for
    category = db.Column(db.String(50), nullable=False)  # Category
    date = db.Column(db.Date, nullable=False)  # When it happened
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # When recorded

    # Links expense to a user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'description': self.description,
            'category': self.category,
            'date': self.date.strftime('%Y-%m-%d'),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self):
        return f'<Expense ${self.amount} - {self.description}>'