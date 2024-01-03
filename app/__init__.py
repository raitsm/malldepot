import logging
from logging.handlers import RotatingFileHandler
import os

from flask import Flask, current_app
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import json
from datetime import datetime
from config import Config
from app.utilities.jinja_filters import format_sales_margin

# logging.basicConfig(level=logging.INFO, encoding='utf-8')
class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super(CustomJSONEncoder, self).__init__(*args, **kwargs)
        self.datetime_format = current_app.config.get('DATETIME_FORMAT', '%Y-%m-%d %H:%M:%S')

    def default(self, obj):
        try:
            if isinstance(obj, datetime):
                return obj.strftime(self.datetime_format) # [:22]  # Use the format from config
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return json.JSONEncoder.default(self, obj)



db = SQLAlchemy()
migration = Migrate()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "Please identify yourself."

def create_app(config_class=Config):
    
        
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json_encoder = CustomJSONEncoder
    app.add_template_filter(format_sales_margin)
    
    db.init_app(app)
    migration.init_app(app, db)
    # login.init_app(app)

    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User  # Import here to avoid circular dependencies
        return User.query.get(int(user_id))

    # import all blueprints
    from app.main import bp_main
    from app.auth import bp_auth
    from app.users import bp_users
    from app.sync import bp_sync
    from app.vendors import bp_vendors
    from app.stock import bp_stock
    # from app.api import bp_api

    # register all blueprints
    app.register_blueprint(bp_main)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_users)
    app.register_blueprint(bp_sync)
    app.register_blueprint(bp_vendors)
    app.register_blueprint(bp_stock)
    # app.register_blueprint(bp_api)

    with app.app_context():
        db.create_all()

    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/malldepot.log',
                                        maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info('MallDepot launched.')


    return app    

