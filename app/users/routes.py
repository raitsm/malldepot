from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_paginate import Pagination, get_page_parameter
from werkzeug.security import check_password_hash
from . import bp_users
from .forms import AddUserForm, ChangePasswordForm, EditUserForm, UserForm
from app.models import User, UserRole
from app.decorators import role_required
from app import db

# User related forms are:
# view users, add user, edit user - access for ADMIN role only
# change password - access to all authenticated users (can change only own password)

@bp_users.route('/view')
@role_required(UserRole.ADMIN)
def view_users():
    ITEMS_PER_PAGE = 15
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=ITEMS_PER_PAGE, error_out=False)
    return render_template('users/view_users.html', users=users.items, pagination=users)


# Add User Route
@bp_users.route('/add', methods=['GET', 'POST'])
@role_required(UserRole.ADMIN)
def add_user():
    form = AddUserForm()
    if form.validate_on_submit():
        try:
            new_user = User(
                username=form.username.data,
                email=form.email.data,
                role=form.role.data,
                given_name=form.given_name.data,
                surname=form.surname.data,
                phone=form.phone.data
            )
            new_user.set_password(form.password.data)  # Set the password
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('users.view_users'))
            
            # return render_template('users/add_user.html', form=form, user_added=True, submit_button_text="Add")

        except Exception as e:
            print(f"Error adding user: {e}")  # Use logging in production
            # flash('Error adding user.')
    else:
        validation_errors = []
        for field_name, error_messages in form.errors.items():
            for err in error_messages:
                message = f"Error in {field_name}: {err}"
                print(f"Error in {field_name}: {err}")
                validation_errors.append(message)

    return render_template('users/add_user.html', form=form, action="Add", submit_button_text="Add", errors=validation_errors)



# Edit User Route
@bp_users.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@role_required(UserRole.ADMIN)
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    print("Username and role before rendering the form:", user.username, user.role.name)
    # user_role = user.role.name if user.role else None
    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        user.username = form.username.data
        user.given_name = form.given_name.data
        user.surname = form.surname.data
        user.email = form.email.data
        user.phone = form.phone.data
        # user.role = form.role
        user.role = form.role.data
        print(user.role)
        if form.new_password.data:
            user.set_password(form.new_password.data)
        print(user)
        db.session.commit()

        return redirect(url_for('users.view_users'))

    validation_errors = []
    for field_name, error_messages in form.errors.items():
        for err in error_messages:
            message = f"Error in {field_name}: {err}"
            print(f"Error in {field_name}: {err}")
            validation_errors.append(message)
    
    return render_template('users/edit_user.html', form=form, action="Edit", submit_button_text="Ok", user_id=user_id, errors=validation_errors)

# Delete user route
@bp_users.route('/delete/<int:user_id>', methods=['GET', 'POST'])
@role_required(UserRole.ADMIN)
def delete_user(user_id):
    print("deleting user", user_id)
    user = User.query.get_or_404(user_id)

    if current_user.id == user_id:
        form = EditUserForm(obj=user)
        delete_self_error_message = "You cannot delete your own account."
        return render_template('users/edit_user.html', 
                               form=form, 
                               user_id=user_id, 
                               delete_self_error_message=delete_self_error_message,
                               submit_button_text="Ok")

    try:
        db.session.delete(user)
        db.session.commit()
        # Redirect to view_users with a flag to trigger the JavaScript success popup
        return redirect(url_for('users.view_users', user_deleted=True))
    except Exception as e:
        print(f"Error deleting user: {e}")  # Use logging in production
        form = EditUserForm(obj=user)
        # Return to the edit_user page with a Bootstrap alert for error
        return render_template('users/edit_user.html', form=form, user_id=user_id, delete_error=True)


# Change Password route
@bp_users.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        
        if not current_user.check_password(form.old_password.data):
            flash('Incorrect current password.')
            return render_template('users/change_password.html', form=form)
        
        current_user.set_password(form.new_password.data)  # Set the new password
        db.session.commit()  # Commit the changes to the database
        # flash('Password changed successfully.')
        return render_template('users/change_password.html', form=form, password_changed=True)
        # return redirect(url_for('main.dashboard'))
    return render_template('users/change_password.html', form=form, action="Change Password")

