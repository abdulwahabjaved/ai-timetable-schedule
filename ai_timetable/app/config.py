# config.py — Application Configuration

import os

class Config:
    # Secret key (change this in production)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Database (SQLite for now, can switch to MySQL/PostgreSQL later)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///timetable.db'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Optional: performance tuning
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


# Easy access
config = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig,
    'default': DevelopmentConfig
}