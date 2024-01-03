from flask import abort, request, jsonify
from flask_login import current_user
from functools import wraps
from .models import APIToken
from app.utilities.token_utilities import validate_token

# build a custom decorator to be used to implement role-based access
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)  # Forbidden access
            return f(*args, **kwargs)
        return decorated_function
    return decorator

#
# custom decorator to implement token-based access to API endpoints
# this decorator will accept one or more roles, eg @token_required(APIRole1, APIROle2)
# it also can be used if only a valid token is required and roles are not specified:
# @token_required() will grant access if the token is valid while ignoring any roles in the token
#
# NB, if multiple roles are specified in the decorator, any of these roles will be sufficient (OR effect) to access the
# underlying route. For AND effect, use chained decorators.
def token_required(*api_roles_required):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get('Authorization', '').split(' ')[1] if 'Authorization' in request.headers else None
            if not token:
                return jsonify({'error': 'Missing token'}), 401

            api_roles, is_valid = validate_token(token)
            if not is_valid:
                return jsonify({'error': 'Invalid or expired token'}), 401

            # If roles are specified in the decorator, check if the token has any of them
            if api_roles_required and not set(api_roles).intersection(api_roles_required):
                return jsonify({'error': 'Insufficient permissions'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
