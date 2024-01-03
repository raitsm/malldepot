# Routes related to stock item management.
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_paginate import Pagination, get_page_parameter
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone # UTC

from app import db
from app.models import Item, UserRole, DeletedItem, PurchaseHistory, Issue, IssueStatus
from . import bp_stock
from app.decorators import role_required
from .forms import ItemForm, AddItemForm, EditItemForm


@bp_stock.route('/view')
@role_required(UserRole.OPERATOR, UserRole.READ_ONLY)
def view_items():
    """
    Browse the stock at the warehouse.
    """
    items_per_page = current_app.config['ITEMS_PER_PAGE']
    page = request.args.get('page', 1, type=int)
    items = Item.query.options(joinedload(Item.vendor)).paginate(page=page, per_page=items_per_page, error_out=False)
    
    return render_template('stock/view_items.html', items=items.items, pagination=items)


@bp_stock.route('/add_item', methods=['GET', 'POST'])
@role_required(UserRole.OPERATOR)
def add_item():
    """
    Add new items to the stock.
    """
    if not current_user.is_operator():
        return "Access denied", 403

    form = AddItemForm()
    if form.validate_on_submit():
        try:
            item = Item(
                code= form.code.data,
                name=form.name.data,
                description=form.description.data,
                # picture=form.picture.data,
                price_per_unit=form.price_per_unit.data,
                units_in_stock=form.units_in_stock.data,
                status=form.status.data,
                vendor_id=form.vendor_id.data,
                user_id=current_user.id,
                requires_sync=True                          # all new items shall be synced with the store
            )
            db.session.add(item)
            db.session.commit()
            return redirect(url_for('stock.view_items'))

        except Exception as e:
            print(f"Error adding item: {e}")  # Use logging in production
    else:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                print(f"Error in {fieldName}: {err}")

    return render_template('stock/add_item.html', form=form, action="Add", submit_button_text="Add")


@bp_stock.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@role_required(UserRole.OPERATOR)
def edit_item(item_id):
    """
    Edit stock item attributes.
    """
    if not current_user.is_operator():
        return "Access denied", 403

    item = Item.query.get_or_404(item_id)
    form = ItemForm(obj=item)

    if form.validate_on_submit():
        item.code= form.code.data
        item.name=form.name.data
        item.description=form.description.data
        item.price_per_unit=form.price_per_unit.data
        item.units_in_stock=form.units_in_stock.data
        item.status=form.status.data
        item.vendor_id=form.vendor_id.data
        item.user_id=current_user.id
        item.requires_sync = True                   # any changed items shall be synced with the store
        db.session.commit()
        return redirect(url_for('stock.view_items'))  # back to view items
    else:
        # print("Form errors:", form.errors)
        pass
    return render_template('stock/edit_item.html', form=form, action="Edit", submit_button_text="Ok", item_id=item_id)


@bp_stock.route('/delete/<int:item_id>', methods=['GET', 'POST'])
@role_required(UserRole.OPERATOR)
def delete_item(item_id):
    """
    Delete an item.
    """
    item = Item.query.get_or_404(item_id)
    deleted_item = DeletedItem(code=item.code,
                               name=item.name,
                               user_name=current_user.username,
                               deletion_time=datetime.now(timezone.utc),
                               requires_sync=True,
                               vendor_name=item.vendor.name
                               )
    try:
        db.session.add(deleted_item)    # add item data to deleted_items for record keeping    
        db.session.delete(item)         # delete item from items table
        db.session.commit()
        # Redirect to view_users with a flag to trigger the JavaScript success popup
        return redirect(url_for('stock.view_items', item_deleted=True))
    except SQLAlchemyError as e:
        db.session.rollback()  # Rollback the session
        return redirect(url_for('stock.view_items', item_deleted=False)) # or return to some error page
        
    finally:
        # Close the session if you are done with it, especially if it's not scoped to the request
        db.session.close()


@bp_stock.route('/view_deleted')
@role_required(UserRole.OPERATOR)
def view_deleted_items():
    """
    View items removed from the warehouse.
    """
    items_per_page = current_app.config['ITEMS_PER_PAGE']
    page = request.args.get('page', 1, type=int)
    deleted_item_pagination = DeletedItem.query.paginate(page=page, per_page=items_per_page, error_out=False)
    deleted_item_items = deleted_item_pagination.items
    
    return render_template('stock/view_deleted_items.html', all_deleted_items=deleted_item_items, pagination=deleted_item_pagination)


@bp_stock.route('/view_purchases')
@role_required(UserRole.OPERATOR)
def view_purchase_data():
    """
    Browse purchase history
    """
    items_per_page = current_app.config['ITEMS_PER_PAGE']
    page = request.args.get('page', 1, type=int)
    # items = Item.query.paginate(page=page, per_page=ITEMS_PER_PAGE, error_out=False)
    purchase_pagination = PurchaseHistory.query.paginate(page=page, per_page=items_per_page, error_out=False)
    purchase_items = purchase_pagination.items
    
    return render_template('stock/view_purchases.html', all_purchases=purchase_items, pagination=purchase_pagination)


@bp_stock.route('/manage_issues')
@role_required(UserRole.OPERATOR, UserRole.ADMIN)
def view_manage_issues():
    """
    Browse and manage issues, such as exceeded quantities of stock items.
    """
    items_per_page = current_app.config['ITEMS_PER_PAGE']
    page = request.args.get('page', 1, type=int)
    issue_pagination = Issue.query.paginate(page=page, per_page=items_per_page, error_out=False)
    issue_items = issue_pagination.items

    return render_template('stock/view_issues.html', all_issues=issue_items, pagination=issue_pagination)


@bp_stock.route('/resolve_issue/<int:issue_id>')
@role_required(UserRole.OPERATOR, UserRole.ADMIN)
def resolve_issue_view(issue_id):
    """
    Flag an issue as resolved.
    """
    success = False
    issue_record = Issue.query.get_or_404(issue_id)
    if not issue_record.is_resolved():
        issue_record.resolve_issue()

    try:
        db.session.commit()
        success = True
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error("Error: could not toggle token status")
        success = False

    return redirect(url_for('stock.view_manage_issues'))

