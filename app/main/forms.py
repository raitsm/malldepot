from flask_wtf import FlaskForm
from wtforms import SubmitField

class SupportForm(FlaskForm):
    submit = SubmitField('OK')

