import os
from flask import Flask
from .data.database import init_db


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['DOWNLOAD_FOLDER'] = os.environ.get('DOWNLOAD_FOLDER', 'downloads')

    os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

    with app.app_context():
        init_db()

    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app
