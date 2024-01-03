import jwt
from datetime import datetime, timedelta
from flask import current_app
from app.models import APIToken
from app import db

def generate_token(system_id, expires_in, roles=[]):
    payload = {
        'exp': datetime.utcnow() + timedelta(seconds=expires_in),
        'iat': datetime.utcnow(),
        'system_id': system_id,
        'roles': roles
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    # Store token in database
    new_token = APIToken(token=token, system_id=system_id, expires_at=payload['exp'])
    db.session.add(new_token)
    db.session.commit()
    return token


# token validator
#
def validate_token(token):
    """
        Function checks if the supplied API token is registered with the database,
        if the token is not expired (using expiration date in the database)
        if the token is not revoked (using revocation status in the database)

        Requires access to SECRET_KEY used to encode the API tokens issued

        Args:
        token: API token to analyse

    Returns:
        If token valid, returns a list of api_roles included to the token and True as validation result
        If token is invalid, returns None + False as validation result
    """
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        api_token = APIToken.query.filter_by(token=token).first()

        if api_token and not api_token.revoked:
            if api_token.expires_at and api_token.expires_at < datetime.utcnow():
                return None, False

            # Extract roles from the payload; it can be a list of roles
            api_roles = payload.get('api_roles', [])
            return api_roles, True

    except jwt.ExpiredSignatureError:
        return None, False
    except jwt.InvalidTokenError:
        return None, False

    return None, False
