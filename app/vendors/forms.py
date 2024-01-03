from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, Length, Email
from app.models import Vendor, VendorStatus

class VendorForm(FlaskForm):
    id = HiddenField('Vendor ID')
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=128)])
    address = StringField('Address', validators=[Length(max=256)])
    country = StringField('Country', validators=[Length(max=50)])
    contact_phone = StringField('Contact Phone', validators=[Length(max=20)])
    contact_email = StringField('Contact Email', validators=[Email()])
    # status = SelectField('Status', choices=[('onboarding', 'Onboarding'), ('active', 'Active'), ('offboarding', 'Offboarding'), ('inactive', 'Inactive')])
    status = SelectField('Status', coerce=str, choices=[(status, status.value) for status in VendorStatus], validators=[DataRequired()])

    # submit = SubmitField('Submit')


# adds the specific functionality for adding new vendors
class AddVendorForm(VendorForm):
    pass

# adds the specific functionality for editing vendor data
class EditVendorForm(VendorForm):
    pass
