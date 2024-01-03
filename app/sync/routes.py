from flask import Blueprint, redirect, url_for, render_template, request, current_app, Response, flash
from flask_login import current_user, login_required
from .forms import SyncForm, StoreConnectionForm
from datetime import datetime, timedelta, timezone # UTC
import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from sqlalchemy import update, and_
from sqlalchemy.exc import SQLAlchemyError
# import json
from app import db
from app.decorators import role_required
from app.models import UserRole, APIToken, SyncHistory, \
                        Item, ItemStatus, DeletedItem, Issue, \
                        IssueStatus, StoreConnectionSettings, ConnectionType
from app.sync import bp_sync
from app.utilities.token_utilities import generate_token
from app.utilities.sync_utilities import download_data, upload_data, update_purchase_data, \
                                        update_stock_data, prepare_updates, prepare_updates_advanced, \
                                        set_single_value, set_single_value_on_list, build_api_url

DELETED_KEY = 'deleted'
NOT_FOR_SALE_KEY = 'not_for_sale'
OUT_OF_STOCK_KEY = 'out_of_stock'
STOCK_UPDATES_KEY = 'stock_updates'



@bp_sync.route('/manage_tokens', methods=['POST', 'GET'])
@role_required(UserRole.ADMIN)
def manage_store_connections_view():
    """
    Set up or adjust the settings used for API connection to the store.
    """
    connection = StoreConnectionSettings.query.first()
    is_new_connection = False

    submit_button_text = "Apply Settings"
    settings_updated = False
    
    # Check if the configuration already exists
    if not connection:
        is_new_connection = True
        # Use default values for the initial setup
        default_name = current_app.config.get('DEFAULT_STORE_NAME', 'Default Store')
        default_ip = current_app.config.get('DEFAULT_STORE_IPV4', '127.0.0.1')
        default_port = current_app.config.get('DEFAULT_STORE_PORT', 5050)
        default_token = ''  # Empty token for initial setup
        action = "Set Up Connection"
        # Create a new connection object with default values
        connection = StoreConnectionSettings(store_name=default_name, 
                                             ipv4_address=default_ip, 
                                             port_number=default_port, 
                                             jwt_token=default_token)
    else:
        action = "Update Connection Settings"

    form = StoreConnectionForm(obj=connection)

    if form.validate_on_submit():
        try:
            connection.store_name = form.store_name.data
            connection.ipv4_address = form.ipv4_address.data
            connection.port_number = form.port_number.data
            connection.jwt_token = form.jwt_token.data

            if is_new_connection:
                db.session.add(connection)

            db.session.commit()
            settings_updated = True
            return render_template('sync/edit_connection.html', 
                                form=form, 
                                action=action,
                                submit_button_text=submit_button_text,
                                settings_updated=settings_updated)  
            # return redirect(url_for('sync.manage_store_connections_view'))
        except SQLAlchemyError as e:
            print(f"Error updating settings: {e}") 
            settings_updated = False

    return render_template('sync/edit_connection.html', 
                           form=form, 
                           action=action,
                           submit_button_text=submit_button_text,
                           settings_updated=settings_updated)


@bp_sync.route('/sync',  methods=['POST'])
@role_required(UserRole.ADMIN, UserRole.OPERATOR)
def sync():
    """
    Synchronize items and purchase data between warehouse and webshop.
    Receives from webshop:
    - purchase data
    Delivers to webshop:
    - updates to stock quantities of items
    - item availability status changes
    - data on items removed from the warehosue
    """
    current_app.logger.info("Sync initiated.")

    error_code = 0

    #
    # build the URLs for webshop endpoints
    #
    store_ip = current_app.config.get('DEFAULT_STORE_IPV4', '127.0.0.1')
    port_number = current_app.config.get('DEFAULT_STORE_PORT', 5050)
    session_token = current_app.config.get('DEFAULT_STORE_TOKEN', "")
    
    connection_settings = StoreConnectionSettings.query.first()
    
    if connection_settings:
        session_token = connection_settings.get_jwt_token()
        store_ip = connection_settings.get_ipv4_address()
        port_number = connection_settings.get_port_number()
        
    get_purchases_url = build_api_url(ipv4_address=store_ip, 
                                      port=port_number,
                                      api_endpoint=current_app.config['GET_PURCHASES_ENDPOINT'])    

    current_app.logger.info(f"Using {get_purchases_url} to get purchase data")

    bulk_upload_url = build_api_url(ipv4_address=store_ip,
                                    port=port_number,
                                    api_endpoint=current_app.config['BULK_UPDATE_ENDPOINT'])

    current_app.logger.info(f"Using {bulk_upload_url} to get purchase data")

    current_app.logger.info("Downloading purchase history from the store.")
    
    connection_start_time = datetime.now(timezone.utc)

    #
    # Retrieve purchases from the store
    #
    download_success, webshop_purchases, message = download_data(url=get_purchases_url, api_key=session_token)
    current_app.logger.info(f"Download result: {message}")

    if download_success:
        if webshop_purchases:
            if not update_purchase_data(items_to_sync=webshop_purchases): # store purchase history 
                # there has been an error in the db when updating purchase history, do not proceed further, return an error.
                message = "Failed to update purchase history in warehouse"
                error_code = 2
                pass                                                    
            if not update_stock_data(data_to_apply=webshop_purchases):          # update stock based on purchase data
                # there has been an error while applying the stock updates, do not proceed further, return an error.
                message = "Failed to update stock data in warehouse"
                error_code = 3
                pass

    else:
        message = "Error downloading purchase data"
        error_code = 1
        # there was a problem getting the updates from webshop, do not proceed further, return an error.

    if error_code != 0:

        sync_record = SyncHistory(remote_name="Storefront",
                                timestamp_start=connection_start_time,
                                timestamp_end=datetime.now(timezone.utc),
                                connection_type=ConnectionType.SYNC,
                                error_code = error_code)
        db.session.add(sync_record)
        db.session.commit()
    
        next_url = request.args.get('next') or url_for('main.index')
        return render_template('sync/sync_failure.html', next_url=next_url)
        
    
    # Prepare data upload from warehouse to the store
    # to ensure data integrity, all datasets will be wrapped into a single dataset sync_data.
    # sync_data dataset will be sent in one POST request and the items will be processedd separately by the store.
    # NB, with large data quantities, a more sophisticated alternative is required.
    sync_data = {}

    current_app.logger.info("Preparing updates for the store.")

    # collect data on deleted stock items. These are to be removed from the offering at the shop.
    item_updates = prepare_updates(model=DeletedItem, 
                                   attributes=['code','name'], 
                                   requires_sync=True)
    sync_data[DELETED_KEY] = item_updates

    # collect data on not-for-sale stock items. These are to be removed from the offering at the shop.
    item_updates = prepare_updates(model=Item, 
                                   attributes=['code','name'], 
                                   requires_sync=True, 
                                   status=ItemStatus.NOT_FOR_SALE)
    sync_data[NOT_FOR_SALE_KEY] = item_updates

    # collect data on out of stock items in the warehouse (stock quantity 0 or less). These are to be removed from the offering at the shop.
    item_updates = prepare_updates_advanced(model=Item, 
                                   attributes=['code','name'],
                                   requires_sync=True, 
                                   status=ItemStatus.FOR_SALE,
                                   units_in_stock=('<=', 0))        
    sync_data[OUT_OF_STOCK_KEY] = item_updates
    
    # collect data on any other updates
    item_updates = prepare_updates_advanced(model=Item, 
                                   attributes=['code','name','description','vendor.name',
                                               'price_per_unit','units_in_stock'],         # ,'sales_margin'
                                   requires_sync=True, 
                                   status=ItemStatus.FOR_SALE,
                                   units_in_stock=('>', 0))
    sync_data[STOCK_UPDATES_KEY] = item_updates

    current_app.logger.info("Uploading updatas to the store.")

    upload_result = upload_data(updates=sync_data, url=bulk_upload_url, api_key=session_token)

    if not upload_result:
        current_app.logger.error("Error uploading updates to the store.")

        error_code = 1
        
        sync_record = SyncHistory(remote_name="Storefront",
                                timestamp_start=connection_start_time,
                                timestamp_end=datetime.now(timezone.utc),
                                connection_type=ConnectionType.SYNC,
                                error_code = error_code)
        db.session.add(sync_record)
        db.session.commit()
    
        next_url = request.args.get('next') or url_for('main.index')
        return render_template('sync/sync_failure.html', next_url=next_url)



    # Now when all data has been transferred, reset sync flags on the transferred items.
    result = set_single_value_on_list(target_model=DeletedItem, 
                                        key_col_target='code',
                                        items_to_update=sync_data[DELETED_KEY],
                                        key_col_input='code',
                                        target_field_to_update='requires_sync',
                                        new_value=False)

    result = set_single_value_on_list(target_model=Item, 
                                        key_col_target='code',
                                        items_to_update=sync_data[OUT_OF_STOCK_KEY],
                                        key_col_input='code',
                                        target_field_to_update='requires_sync',
                                        new_value=False)

    result = set_single_value_on_list(target_model=Item, 
                                        key_col_target='code',
                                        items_to_update=sync_data[NOT_FOR_SALE_KEY],
                                        key_col_input='code',
                                        target_field_to_update='requires_sync',
                                        new_value=False)

    result = set_single_value_on_list(target_model=Item, 
                                        key_col_target='code',
                                        items_to_update=sync_data[STOCK_UPDATES_KEY],
                                        key_col_input='code',
                                        target_field_to_update='requires_sync',
                                        new_value=False)

    connection_end_time = datetime.now(timezone.utc)

    sync_record = SyncHistory(remote_name="Storefront",
                        timestamp_start=connection_start_time,
                        timestamp_end=connection_end_time,
                        connection_type=ConnectionType.SYNC,
                        error_code = error_code)
    db.session.add(sync_record)
    db.session.commit()

    current_app.logger.info("Sync complete.")

    next_url = request.args.get('next') or url_for('main.index')
    return render_template('sync/sync_success.html', next_url=next_url)
      

@bp_sync.route('/store_reset', methods=['POST'])
@role_required(UserRole.ADMIN)
def webshop_reset():
    """
    Wipes stock items and purchase history data from the store. A clean start for the store.
    """

    error_code = 0
    print("MallDepot: Store reset initiated.")

    ssl_verification_flag = current_app.config['PROD_ENV']
   
    sync_data = {}

    store_ip = current_app.config.get('DEFAULT_STORE_IPV4', '127.0.0.1')
    port_number = current_app.config.get('DEFAULT_STORE_PORT', 5050)
    session_token = current_app.config.get('DEFAULT_STORE_TOKEN', "")
    
    connection_settings = StoreConnectionSettings.query.first()
    
    if connection_settings:
        session_token = connection_settings.get_jwt_token()
        store_ip = connection_settings.get_ipv4_address()
        port_number = connection_settings.get_port_number()
    
    store_reset_url= build_api_url(ipv4_address=store_ip, 
                             port=port_number,
                             api_endpoint=current_app.config['STORE_RESET_ENDPOINT'])    
    
    headers = {
        'Authorization': f'Bearer {session_token}'
    }
    connection_start_time = datetime.now(timezone.utc)    

    # Step 1, tell the store to wipe out the data
    try:
        clear_response = requests.post(url=store_reset_url, headers=headers, verify=ssl_verification_flag)
        print(clear_response, clear_response.status_code)

        if clear_response.status_code != 200:
            # Handle non-200 status codes here
            message = "ERROR: Non-200 response from webshop. Could not reset webshop."
            error_code = 1
        else:
            # Successful reset
            message = "Store reset successful."
            error_code = 0

    except RequestsConnectionError:
        # Handle connection error specifically
        message = "ERROR: Could not connect to webshop. Is the webshop server running?"
        error_code = 2
    
    if error_code != 0:
        
        sync_record = SyncHistory(remote_name="Storefront",
                                timestamp_start=connection_start_time,
                                timestamp_end=datetime.now(timezone.utc),
                                connection_type=ConnectionType.RESET,
                                error_code = error_code)
        db.session.add(sync_record)
        db.session.commit()

        return render_template('sync/post_reset.html', message=message)

    # Step 2: Upload new stock items to the webshop
    store_update_url = build_api_url(ipv4_address=store_ip,
                                     port=port_number,
                                     api_endpoint=current_app.config['BULK_UPDATE_ENDPOINT'])  
    
    # all items available for sale shall go to the shop
    item_updates = prepare_updates_advanced(model=Item, 
                                   attributes=['code','name','description','vendor.name',
                                               'price_per_unit','units_in_stock'],          # ,'sales_margin'
                                   status=ItemStatus.FOR_SALE,
                                   units_in_stock=('>', 0))

    sync_data[STOCK_UPDATES_KEY] = item_updates


    upload_result = upload_data(updates=sync_data, url=store_update_url, api_key=session_token)

    if not upload_result:
        message = "ERROR: could not upload data to store after reset."
        error_code = 1
        # print(message)
    else:
        message = "Store reset successful."
       
        result = set_single_value_on_list(target_model=Item, 
                                          key_col_target='code',
                                          items_to_update=sync_data[STOCK_UPDATES_KEY],
                                          key_col_input='code',
                                          target_field_to_update='requires_sync',
                                          new_value=False)

    connection_end_time = datetime.now(timezone.utc)

    sync_record = SyncHistory(remote_name="Storefront",
                            timestamp_start=connection_start_time,
                            timestamp_end=connection_end_time,
                            connection_type=ConnectionType.RESET,
                            error_code = error_code)
    db.session.add(sync_record)
    db.session.commit()
        
       
    return render_template('sync/post_reset.html', message=message)


# browse session history
@bp_sync.route('/sync_history')
@role_required(UserRole.ADMIN, UserRole.OPERATOR)
def browse_session_history():
    """
    Browse session history.
    """
    items_per_page = current_app.config['ITEMS_PER_PAGE']
    page = request.args.get('page', 1, type=int)
    sync_history_pagination = SyncHistory.query.paginate(page=page, per_page=items_per_page, error_out=False)
    sync_history_items = sync_history_pagination.items
    
    return render_template('sync/sync_history.html', sync_history=sync_history_items, pagination=sync_history_pagination)

