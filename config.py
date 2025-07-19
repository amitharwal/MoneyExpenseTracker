import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-this'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # Stay logged in for 7 days

    # Categories for expenses
    EXPENSE_CATEGORIES = [
        'Food',
        'Transport',
        'Shopping',
        'Bills',
        'Entertainment',
        'Health',
        'Other'
    ]

class DevelopmentConfig(Config):
    DEBUG = True
    # Use SQLite locally if no DATABASE_URL is set
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///expenses.db'

class ProductionConfig(Config):
    DEBUG = False

# Choose config based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}