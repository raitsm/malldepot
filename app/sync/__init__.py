from flask import Blueprint

bp_sync = Blueprint('sync', __name__, url_prefix='/sync')

from app.sync import routes
