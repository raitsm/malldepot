import os
from dotenv import load_dotenv


basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """
    Configuration parameters for the app.
    Accessed as current_app.config['PARAMETER'] or current_app.config.get('PARAMETER')
    """
    
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'malldepot.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'something-extremely-secret-just-to-scare-everyone-away-until-a-proper-hash-value-is-here'
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    ITEMS_PER_PAGE = 5
    MIN_PASSWORD_LENGTH = 8
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
    SESSION_COOKIE_NAME = "malldepot-cookie"
    APP_ID = "MallDepot"    
    # DEFAULT_PROTOCOL = "http"   # "https"
    USE_HTTPS = True                # determines if to use HTTP or HTTPS
    PROD_ENV = False  # If False, SSL certificates will not be verified. Set to True for production.
    USE_PORT = 5000     # port number that the system will run on

    # default store settings to be used in connection setup
    DEFAULT_STORE_NAME = "Generic Storefront Webshop"
    DEFAULT_STORE_IPV4 = "127.0.0.1"
    DEFAULT_STORE_PORT = 5050
    DEFAULT_STORE_TOKEN = ""
    
    # standardised endpoint names for the webshop
    GET_PURCHASES_ENDPOINT = "/api/purchases"           # endpoint to receive the purchase history from
    BULK_UPDATE_ENDPOINT = "/api/bulk_update"           # endpoint to deliver stock item updates to
    STORE_RESET_ENDPOINT = "/api/items/delete_all"      # endpoint to delete the data from the store (stock items + purchases)
    DEFAULT_API_ENDPOINT = ""
    