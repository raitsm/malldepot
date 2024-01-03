# forms related to stock item management

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, BooleanField, SubmitField, HiddenField, SelectField
from wtforms.validators import DataRequired, NumberRange, Length, InputRequired
from app.models import Item, ItemStatus, Vendor, VendorStatus


class ItemForm(FlaskForm):
    """
    Base form for item management.
    """
    id = HiddenField('Item ID')
    code = StringField('Code', validators=[DataRequired(), Length(min=2, max=128)])
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=128)])
    description = TextAreaField('Description')
    picture = StringField('Picture URL')
    price_per_unit = DecimalField('Price Per Unit', validators=[InputRequired(), NumberRange(min=0)])
    units_in_stock = IntegerField('Units in Stock', validators=[InputRequired(), NumberRange(min=0)])
    status = SelectField('Status', coerce=str, choices=[(status, status.value) for status in ItemStatus], validators=[DataRequired()])
    vendor_id = SelectField('Vendor', coerce=int, choices=[], validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super(ItemForm, self).__init__(*args, **kwargs)
        self.vendor_id.choices = [(v.id, v.name) for v in Vendor.query.filter(Vendor.status != VendorStatus.CLOSED).all()]


# adds the specific functionality for adding new vendors
class AddItemForm(ItemForm):
    pass

# adds the specific functionality for editing vendor data
class EditItemForm(ItemForm):
    pass
