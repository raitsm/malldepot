from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from flask_paginate import Pagination, get_page_parameter

from app.models import Vendor, UserRole, Item
from .forms import VendorForm, AddVendorForm, EditVendorForm
from . import bp_vendors

from app.decorators import role_required
from app.vendors import bp_vendors
from app import db


@bp_vendors.route('/view')
@role_required(UserRole.OPERATOR, UserRole.READ_ONLY)
def view_vendors():
    ITEMS_PER_PAGE = 15
    page = request.args.get('page', 1, type=int)
    vendors = Vendor.query.paginate(page=page, per_page=ITEMS_PER_PAGE, error_out=False)
    return render_template('vendors/view_vendors.html', vendors=vendors.items, pagination=vendors)


@bp_vendors.route('/add_vendor', methods=['GET', 'POST'])
@role_required(UserRole.OPERATOR)
def add_vendor():
    if not current_user.is_operator():
        abort(403)  # Forbidden access
    form = AddVendorForm()
    if form.validate_on_submit():
        try:
            vendor = Vendor(name=form.name.data, 
                            address=form.address.data, 
                            country=form.country.data, 
                            contact_phone=form.contact_phone.data, 
                            contact_email=form.contact_email.data, 
                            status=form.status.data,
                            user_id=current_user.id)
            db.session.add(vendor)
            db.session.commit()
            return redirect(url_for('vendors.view_vendors'))
            # return render_template('vendors/add_vendor.html', form=form, vendor_added=True, submit_button_text="Add")
        except Exception as e:
            print(f"Error adding vendor: {e}")  # Use logging in production
    else:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                print(f"Error in {fieldName}: {err}")

    return render_template('vendors/add_vendor.html', form=form, action="Add", submit_button_text="Add")


@bp_vendors.route('/edit_vendor/<int:vendor_id>', methods=['GET', 'POST'])
@role_required(UserRole.OPERATOR)
def edit_vendor(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)  # Fetch vendor from database
    form = VendorForm(obj=vendor)
    print("Vendor name before rendering the form:", vendor.name)

    if form.validate_on_submit():
        # Update vendor data with form data
        vendor.name = form.name.data
        vendor.address = form.address.data
        vendor.country = form.country.data
        vendor.contact_phone = form.contact_phone.data
        vendor.contact_email = form.contact_email.data
        vendor.status = form.status.data
        vendor.user_id=current_user.id
        print(vendor)
        db.session.commit()
        return redirect(url_for('vendors.view_vendors'))  # Adjust the redirect as needed

    return render_template('vendors/edit_vendor.html', form=form, action="Edit", submit_button_text="Ok", vendor_id=vendor_id)


# Delete user route
@bp_vendors.route('/delete/<int:vendor_id>', methods=['GET', 'POST'])
@role_required(UserRole.OPERATOR)
def delete_vendor(vendor_id):
    print("deleting vendor", vendor_id)
    vendor = Vendor.query.get_or_404(vendor_id)
    items = Item.query.filter_by(vendor_id=vendor_id).first()
    if items:
        # Pass an error message to the template
        return redirect(url_for('vendors.edit_vendor', vendor_id=vendor_id, error="Cannot delete vendor because there are stock items linked to it."))

    try:
        db.session.delete(vendor)
        db.session.commit()
        # Redirect to view_users with a flag to trigger the JavaScript success popup
        return redirect(url_for('vendors.view_vendors', vendor_deleted=True))
    except Exception as e:
        print(f"Error deleting vendor: {e}")  # Use logging in production
        form = EditVendorForm(obj=vendor)
        # Return to the edit_user page with a Bootstrap alert for error
        return render_template('vendors/edit_vendor.html', form=form, vendor_id=vendor_id, delete_error=True)
