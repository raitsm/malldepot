from flask import Blueprint

bp_vendors = Blueprint('vendors', __name__, url_prefix='/vendors')

from app.vendors import routes
