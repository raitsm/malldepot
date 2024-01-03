from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone # UTC
from flask_login import UserMixin
from enum import Enum
from app import db


class UserRole(Enum):
    """
    Model to represent user access roles in a human-readable form. Used by User model.

    """
    ADMIN = "Administrator"
    OPERATOR = "Warehouse Operator"
    READ_ONLY = "Auditor"
    
    @classmethod
    def choices(cls):
        return [(choice, choice.value) for choice in cls]

    @classmethod
    def coerce(cls, item):
        return cls(int(item)) if not isinstance(item, cls) else item

    def __str__(self):
        return str(self.name)


class User(UserMixin, db.Model):
    """
    Model and support functions for user data.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    given_name = db.Column(db.String(64))
    surname = db.Column(db.String(64))
    email = db.Column(db.String(120), index=True, unique=True)
    phone = db.Column(db.String(20))
    last_logon = db.Column(db.DateTime)
    # role = db.Column(db.String(20))
    role = db.Column(db.Enum(UserRole), default=UserRole.READ_ONLY, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == UserRole.ADMIN

    def is_operator(self):
        return self.role == UserRole.OPERATOR

    def is_read_only(self):
        return self.role == UserRole.READ_ONLY
    
    # def last_logon_as_str(self):
    #     return self.last_logon

    def last_logon_as_str(self):
        return self.last_logon.strftime('%Y-%m-%d %H:%M:%S') if self.last_logon else 'Never logged in'
    
    def __repr__(self):
        return '<User {}>'.format(self.username)


class ItemStatus(Enum):
    """
    Model to represent stock item statuses in a human-readable form. Used by Item model.

    """
    NOT_FOR_SALE = "Not for sale"
    FOR_SALE = "For sale"

    def __str__(self):
        return str(self.name)


class Item(db.Model):
    """
    Model for stock items.
    """
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    picture = db.Column(db.String(256))  # URL or path to the image
    price_per_unit = db.Column(db.Float)
    # sales_margin = db.Column(db.Float, default=1)
    
    units_in_stock = db.Column(db.Integer)
    # available_for_sale = db.Column(db.Boolean)
    status = db.Column(db.Enum(ItemStatus), default=ItemStatus.NOT_FOR_SALE, nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    units_purchased = db.Column(db.Integer, default=0)              # field to record the number of units purchased
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    requires_sync = db.Column(db.Boolean, default=True, nullable=False)             # a flag indicating that the item must be included to sync
    vendor = db.relationship('Vendor', backref='items')

class DeletedItem(db.Model):
    """
    Model to store data on deleted stock items.
    The data is necessary for the periodic synchronisation with the store 
    (store is provided with a list of deleted items so it can make the changes on its own database).
    """
    __tablename__ = 'deleted_items'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    user_name = db.Column(db.String(64), nullable=False)          # name of user who deleted the item
    deletion_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    requires_sync = db.Column(db.Boolean, default=True, nullable=False)             # a flag indicating that the item must be included to sync
    vendor_name = db.Column(db.String(128), nullable=False)     # store vendor name for deleted items directly so that deleted items do not block vendor records from being deleted.
    description = db.Column(db.Text)                            

class VendorStatus(Enum):
    """
    Model to represent vendor statuses in a human-readable form. Used by Vendor model.

    """
    # ONBOARDING = "New Vendor"
    ACTIVE = "Active Vendor"
    CLOSED = "Closed Vendor"

    def __str__(self):
        return str(self.name)

     
class Vendor(db.Model):
    """
    Model to store data on vendors. 
    """
    __tablename__ = 'vendors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    address = db.Column(db.String(256))
    country = db.Column(db.String(50))
    contact_phone = db.Column(db.String(20))
    contact_email = db.Column(db.String(120))
    status = db.Column(db.Enum(VendorStatus), default=VendorStatus.ACTIVE, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class PurchaseHistory(db.Model):
    """
    Model to store purchase data received from the shop.
    """
    __tablename__ = 'purchase_history'

    id = db.Column(db.Integer, primary_key=True)
    purchase_code = db.Column(db.String(50))
    item_code = db.Column(db.String(32))        # 'code' in JSON
    item_name = db.Column(db.String(128))       # 'name' in JSON
    vendor_name = db.Column(db.String(128))
    quantity = db.Column(db.Integer)
    price_per_unit = db.Column(db.Float)
    # sales_margin = db.Column(db.Float)
    total_price = db.Column(db.Float)
    purchase_time = db.Column(db.DateTime)
    load_time = db.Column(db.DateTime)          # date&time when purchase transaction was loaded into warehouse
          

class APIConnection(db.Model):
    __tablename__ = "connections"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))


# API roles
class APIRole(Enum):
    """
    Access levels for API clients.
    """
    READ_ONLY = "Read-only"
    READ_WRITE = "Read-write"
    WRITE_ONLY = "Write-only"

    def __str__(self):
        return str(self.name)


class APIToken(db.Model):
    """
    Model for API tokens.
    A token shall include a system id and role.

    Other attributes are used to enable token management.

    """   
    __tablename__ = 'api_tokens'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(255), unique=True, nullable=False)
    system_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    role = db.Column(db.String(50))  # Role or access level
    revoked = db.Column(db.Boolean, default=False)
    last_used_at = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))      # user who created or updated the token

    def is_token_valid(self):
        # Check if the token is expired or revoked
        return not self.revoked and (self.expires_at is None or self.expires_at > datetime.utcnow())

class ConnectionType(Enum):
    """
    Model to store connection direction parameters in a human-readable form. Used by SyncHistory.
    """

    SYNC = "Sync"
    RESET = "Reset"

    def __str__(self):
        return str(self.name)


class SyncHistory(db.Model):
    """
    Model to store synchronisation log: 
    start & end time, sync type, updates sent & received

    """
    
    __tablename__ = "sync_history"
    
    id = db.Column(db.Integer, primary_key=True)
    remote_name = db.Column(db.String(50))                  # name of the remote system, based on system_id field in API token.
    timestamp_start = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp_end = db.Column(db.DateTime, default=datetime.utcnow)
    error_code = db.Column(db.Integer, default=0)                   # 0 means a successful session
    connection_type = db.Column(db.Enum(ConnectionType), default=ConnectionType.RESET)
    updates_received = db.Column(db.Integer, default=0)
    updates_sent = db.Column(db.Integer, default=0)



class IssueStatus(Enum):
    """
    Model to store issue statuses in a human-readable form. Used by Issue.
    """
    UNRESOLVED = "Not resolved"
    RESOLVED = "Resolved"

    def __str__(self):
        return str(self.name)


class Issue(db.Model):
    """
    Model to keep track of issues (problems/incidents).
    """
    __tablename__ = "issues"
    id = db.Column(db.Integer, primary_key=True)
    raised_time = db.Column(db.DateTime)
    message = db.Column(db.String(256))
    status = db.Column(db.Enum(IssueStatus), default=IssueStatus.UNRESOLVED)
    solved_time = db.Column(db.DateTime)

    def is_resolved(self):
        return self.status == IssueStatus.RESOLVED

    def resolve_issue(self):
        """
        Flag an issue as resolved. Record the time when issue was solved.
        NB, It is only a mock function. In real-world application, this should trigger a workflow.
        """
        self.status = IssueStatus.RESOLVED
        self.solved_time = datetime.now(timezone.utc)
    
    def reopen_issue(self):
        self.status = IssueStatus.UNRESOLVED


class StoreConnectionSettings(db.Model):
    """
    Model to store connection settings:
    ip v4 address, port number, JWT token used by the store.
    
    Currently built for a single store, but easy to extend to fit a multi-store operation.
    """
    
    __tablename__ = "store_connection_settings"
    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(50))
    ipv4_address = db.Column(db.String(16))
    port_number = db.Column(db.Integer, default=443)
    jwt_token = db.Column(db.String(1024))
    
    def get_ipv4_address(self):
        return self.ipv4_address
    
    def get_port_number(self):
        return self.port_number
    
    def get_jwt_token(self):
        return self.jwt_token