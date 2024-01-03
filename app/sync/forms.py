# forms related to synchronisation between warehouse and webshop

from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, IPAddress

class SyncForm(FlaskForm):
    submit = SubmitField('Sync Data')

class StoreConnectionForm(FlaskForm):
    """
    Form to capture connection settings.
    NB, jwt_token shall be copy-pasted from the webshop.
    """
    store_name = StringField('Connection Name', validators=[DataRequired(), Length(min=1, max=50)])
    ipv4_address = StringField('IP Address', validators=[DataRequired(), IPAddress(ipv4=True, ipv6=False, message="Invalid IPv4 address.")])
    port_number = IntegerField('Port', validators=[DataRequired(), NumberRange(min=1, max=65535, message="Port number must be between 1 and 65535.")])
    jwt_token = TextAreaField('JWT Token', validators=[Length(max=1024)])
