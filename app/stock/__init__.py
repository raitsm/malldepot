from flask import Blueprint

bp_stock = Blueprint('stock', __name__, url_prefix='/stock')

from app.stock import routes
