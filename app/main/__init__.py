from flask import Blueprint

bp_main = Blueprint('main', __name__)

from app.main import routes
