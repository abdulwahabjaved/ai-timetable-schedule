from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    # FIX 1: correct config import path
    # if config.py is inside app folder
    from app.config import DevelopmentConfig
    app.config.from_object(DevelopmentConfig)

    # FIX 2: init db only ONCE
    db.init_app(app)

    with app.app_context():
        # IMPORTANT: ensure models use SAME db instance
        from app import models  # not just "from . import models"
        db.create_all()

    from app.routes import main
    app.register_blueprint(main)

    # Prevent browser from caching HTML pages — ensures fresh data after upload
    @app.after_request
    def add_no_cache_headers(response):
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    return app