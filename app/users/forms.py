#
# users/forms.py - form definitions for user management related functions
#
from flask import current_app
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, SelectField, HiddenField, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp
from app.models import User, UserRole  # Import the UserRole enum

# Custom Validator Function
def validate_password_length(form, field):
    min_length = current_app.config['MIN_PASSWORD_LENGTH']
    if len(field.data) < min_length:
        raise ValidationError(f'Password must be at least {min_length} characters long.')

def validate_current_password(self, field):
    if not current_user.check_password(field.data):
        raise ValidationError('Incorrect current password.')

def role_query():
    return UserRole.querys

def coerce_user_role(name):
    print(name)
    for role in UserRole:
        print(">>", role.name)
        if role.name == name:
            return role
    raise ValueError("Invalid UserRole")

class UserForm(FlaskForm):
    id = HiddenField('User ID')
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])

    given_name = StringField('Given Name', validators=[DataRequired(), Length(min=1, max=64)])
    surname = StringField('Surname', validators=[DataRequired(), Length(min=1, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=1, max=20), Regexp('^[0-9\-\+]+$', message="Phone number must contain only numbers and -/+ characters")])

    role = SelectField('Role', coerce=str, choices=[(role, role.value) for role in UserRole], validators=[DataRequired()])
    

# adds the specific functionality for adding new users
class AddUserForm(UserForm):
    password = PasswordField('Password', validators=[
        DataRequired(),
        validate_password_length  # Custom validator for minimum length
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match.')
    ])


# adds the specific functionality for editing user accounts
class EditUserForm(UserForm):
    new_password = PasswordField('New Password', validators=[Optional(), validate_password_length])
    new_password2 = PasswordField('Confirm New Password', validators=[Optional(), EqualTo('new_password', message='Passwords must match')])

    def validate_new_password(form, field):
        if field.data and not form.new_password2.data:
            raise ValidationError("Please confirm the new password.")
                

# functionality for changing user's password
class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Current Password', validators=[
        DataRequired(),
        validate_current_password])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        validate_password_length  # Custom validator for minimum length
    ])
    new_password2 = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Change Password')

