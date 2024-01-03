# utility functions used by data sync
# data preparation, filtering, upload, download

from datetime import datetime, timezone # UTC
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import update
import requests
from app.models import Item, Issue, DeletedItem, PurchaseHistory, IssueStatus
from app import db
from flask import current_app


class OperationResult:
    # NB, OperationResult class must be kept in sync between malldepot and storefront codebases.
        
    # operation status definitions
    SUCCESS = 0
    FAILURE = 1
    NOT_PERFORMED = 2
    
    def __init__(self):
        self.http_response = 500  # HTTP response code
        self.result_code = OperationResult.NOT_PERFORMED       # 0 - success, 1 - unsuccessful, 2 - not performed
        self.result_message = "Operation not performed"
        self.deleted_count = 0
        self.updated_count = 0
        self.added_count = 0
        self.erroneous_count = 0
        self.not_found_count = 0

    def update(self, result_code, result_message="", http_response=500, **kwargs):

        self.result_code = result_code
        self.result_message = result_message or self.result_message
        self.http_response = http_response

        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self):
        return vars(self)

    # load values from a dictionary    
    def load_from_dict(self, data_dict):
        for key, value in data_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
                
    # methods to check various states of the operation.
    def operation_success(self):
        return self.result_code == OperationResult.SUCCESS

    def operation_failure(self):
        return self.result_code == OperationResult.FAILURE
    
    def operation_not_performed(self):
        return self.result_code == OperationResult.NOT_PERFORMED


# add purchases to purchase history table
def update_purchase_data(items_to_sync):
    """
    Adds purchase data from store to purchase history log at the warehouse.

    Args:
    items_to_sync: parsed JSON dataset.
    
    Returns: update status
     
    
    """
    # print(items_to_sync)

    # nothing was received.
    if not items_to_sync:
        message = "No purchase data received, nothing to update."
        current_app.logger.warning(message)
        print(message)
        return True         # There may be no purchases made in the store since the previous sync, and it is OK.

    datetime_format = current_app.config.get('DATETIME_FORMAT', '%Y-%m-%d %H:%M:%S')

    # Parse the 'purchase_time' using the format from the app's configuration

    for item in items_to_sync:
        try:
            # Create a new PurchaseHistory object
            purchase_time_str = item.get('purchase_time')
            purchase_time = datetime.strptime(purchase_time_str, datetime_format) if purchase_time_str else None

            purchase = PurchaseHistory(
                purchase_code=item.get('purchase_code'),
                item_code=item.get('code'),
                item_name=item.get('name'),
                vendor_name=item.get('vendor_name'),
                quantity=item.get('quantity'),
                price_per_unit=item.get('price_per_unit'),
                # sales_margin=item.get('sales_margin'),
                total_price=item.get('total_price'),

                purchase_time = purchase_time,
                load_time=datetime.now(timezone.utc)
            )

            # Add the new purchase to the session and commit
            db.session.add(purchase)
            db.session.commit()
            return True             # All purchases aplied. OK.

        except SQLAlchemyError as e:
            # Capture any db errors
            current_app.logger.error(f'Database error: {e}')
            db.session.rollback()
            return False            # failure due to some issue at the db (smth wrong with a constraint, or similar)


# apply purchase data to stock inventory.
# update: numner of items purchased (increase)
# update: items in stock (decrease, raise an error if zero or if item missing from stock)

def update_stock_data(data_to_apply):
    """
    Updates warehouse with purchase data received from the store.
    Increases the purchase counter according to how many items (Item model) have been purchased.
    Decreases the remaining stock quantity according to how many items have been purchased.
    If, due to the update, remaining stock quantity would reach zero or drop below, an Issue (in Issue model) shall be raised, while the stock quantity shall be set to zero.
    If there is a purchase on a deleted item (item not found in Item, but is found in DeletedItem), an issue shall be raised, but the quantity for the deleted item shall stay untouched.

    NB, purchases data are processed as FIFO, there is no optimization to prioritize either the largest purchases, or the biggest number of purchases on a single item.
    Args: purchases - purchase data received via API, 'code' uniquely determines a stock item.
    
    Returns: a success/failure flag together and a corresponding message.
    
    """

    issues_raised = 0
    success = True
    message = "Stock data updated successfully."

    for purchase in data_to_apply:
        item_code_from_purchase = purchase.get('code')
        purchased_quantity = purchase.get('quantity')

        try:
            # Find the corresponding item
            item = Item.query.filter_by(code=item_code_from_purchase).first() # look for the item in Item model
            deleted_item = DeletedItem.query.filter_by(code=item_code_from_purchase).first() # look for the item in DeletedItem model

            if not item and not deleted_item:
                # purchase was done on an item that is not found in active or deleted items.
                # this is something to investigate, hence an issue is raised.
                issue_message = f"Item with code {item_code_from_purchase} and name {purchase.get('name')} not found."
                current_app.logger.error(issue_message)
                new_issue = Issue(message=issue_message, raised_time=datetime.now(timezone.utc), status=IssueStatus.UNRESOLVED)
                issues_raised += 1
                continue

            if deleted_item:
                # Raise an issue for a purchase on a deleted item.
                # purchase statistics will not be changed for a deleted item.
                issue_message = f"Purchase on deleted item: {item_code_from_purchase} {deleted_item.name}"
                new_issue = Issue(message=issue_message, raised_time=datetime.now(timezone.utc), status=IssueStatus.UNRESOLVED)
                db.session.add(new_issue)
                issues_raised += 1
                continue

            # if the purchase refers an item that is currently active.
            if item:
                # Check if units_in_stock will drop to or below zero after this purchase
                new_stock = item.units_in_stock - purchased_quantity
                if new_stock <= 0:
                    # Log issue if stock is zero or below
                    issue_message = f"Running out of stock for: {item_code_from_purchase} {item.name}, balance is {new_stock} units."
                    new_issue = Issue(message=issue_message, raised_time=datetime.now(timezone.utc), status=IssueStatus.UNRESOLVED)
                    db.session.add(new_issue)
                    issues_raised += 1
                    item.units_in_stock = 0
                    current_app.logger.error(f"Stock underflow {new_stock} units for item {item_code_from_purchase} {item.name}. Stock set to zero.")
                else:
                    item.units_in_stock = new_stock

                # Update units_purchased
                item.units_purchased += purchased_quantity

                db.session.add(item)
    
            db.session.commit()

        except SQLAlchemyError as e:
            current_app.logger.error(f'Database error while updating item {item_code_from_purchase}: {e}')
            db.session.rollback()
            success = False
            message = "Failed to update stock data due to a database error."
            break

    return success, message, issues_raised


def prepare_updates(model, attributes, **filters):
    """
    Prepares updates for delivery.
    Arguments:
    model: Model from which the data will be taken.
    attributes: List of attribute names to extract from the model. Supports nested attributes.
    filters: Filters to be applied.

    Returns: Prepared updates.
    """
    items = model.query.filter_by(**filters).all()
    updates = []

    for item in items:
        update = {}
        for attr in attributes:
            if '.' in attr:
                # Handle nested attributes (eg., vendor.name)
                nested_value = item
                for sub_attr in attr.split('.'):
                    nested_value = getattr(nested_value, sub_attr, None)
                    if nested_value is None:
                        break
                update[attr] = nested_value
            else:
                # Handle simple attributes
                update[attr] = getattr(item, attr, None)
        updates.append(update)

    return updates


def prepare_updates_advanced(model, attributes, **filters):
    """
    Prepares updates for delivery using simple and advanced filters.
    Arguments: 
    model: model from which the data will be taken
    attributes: List of attribute names to extract from the model. Supports nested attributes.
    filters: filters to be applied (optional)
            The filters are applied either as: status=ItemStatus.FOR_SALE
            In more advanced cases, as:  units_in_stock=('>', 0)

    Returns: prepared updates
    """
    query = model.query

    if filters:
        for key, value in filters.items():
            if isinstance(value, tuple):
                # Complex filter: Unpack the tuple and apply the filter
                op, val = value
                query = query.filter(getattr(model, key).op(op)(val))
            else:
                # Simple filter: Apply as is
                query = query.filter(getattr(model, key) == value)

    items = query.all()
    updates = []

    for item in items:
        update = {}
        for attr in attributes:
            if '.' in attr:
                # Handle nested attributes (eg., vendor.name)
                nested_value = item
                for sub_attr in attr.split('.'):
                    nested_value = getattr(nested_value, sub_attr, None)
                    if nested_value is None:
                        break
                update[attr] = nested_value
            else:
                # Handle simple attributes
                update[attr] = getattr(item, attr, None)
        updates.append(update)

    return updates


def upload_data(updates, url, api_key=None, timeout=10):
    """
    Uploads data to a specified URL via a POST request.

    Args:
        updates (dict): The data to be uploaded.
        url (str): The API endpoint to which data is uploaded.
        api_key (str, optional): API key for authentication, if required.
        timeout (int, optional): timeout in seconds to wait for the connection.

    Returns:
        tuple: A tuple containing a boolean indicating success or failure, and a message.
    """

    ssl_verification_flag = current_app.config['PROD_ENV']

    update_url = url
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    error_message = "Not Set Yet."
    try:
        response = requests.post(update_url, json=updates, headers=headers, timeout=timeout, verify=ssl_verification_flag)
    
        # return OperationResult object only if the connection was successful
        if response.status_code == 200:
            error_message = "Connection to store OK."
            print(error_message)
            current_app.logger.info(error_message)
            return response.json()

        # If there is a lower-level technical error, return None
        if response.status_code >= 500:
            error_message = f"Error {response.status_code}: Server error on the destination."
            # return False, "Server error on the destination."
        elif response.status_code == 404:
            error_message = f"Error {response.status_code}: Endpoint not found."
            # return False, "Endpoint not found."
        elif response.status_code >= 400:
            error_message = f"Error {response.status_code}: Client error: {response.text}"
            # return False, f"Client error: {response.text}"
        else:
            error_message = f"Error {response.status_code}: Unknown error occurred."
        print(error_message)
        current_app.logger.error(error_message)
        return None
    
    # Return None if there is a technical error with the response.
    except requests.exceptions.ConnectionError:
        current_app.logger.error("Failed to connect to the server.")
        return None
    except requests.exceptions.Timeout:
        current_app.logger.error("Request timed out.")
        return None
    except requests.exceptions.RequestException as e:
        # Catch any other requests-related exceptions
        current_app.logger.error(f"An error occurred: {e}")
        return None


def download_data(url, api_key=None, timeout=10):
    """
    Downloads data from a specified URL via a GET request.

    Args:
        url (str): The URL from which data is to be downloaded.
        api_key (str, optional): API key for authentication, if required.
        timeout (int, optional): timeout in seconds to wait for the connection.

    Returns:
        tuple: A tuple containing a boolean indicating success or failure,
               the downloaded data or None, and an error message if any.
    """
    ssl_verification_flag = current_app.config['PROD_ENV']

    headers = {}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    try:
        response = requests.get(url, headers=headers, timeout=timeout, verify=ssl_verification_flag)

        # Check if the response is successful
        if response.status_code == 200:
            return True, response.json(), "Connection to store OK."

        # Handle unsuccessful responses
        return False, None, f"Error {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return False, None, "Failed to connect to the server."
    except requests.exceptions.Timeout:
        return False, None, "Request timed out."
    except requests.exceptions.RequestException as e:
        return False, None, f"An error occurred: {e}"


def set_single_value(model, field_to_update, new_value, **conditions):
    """
    Safely updates a single field in a given model based on provided conditions.

    Args:
        model (db.Model): The model to update.
        field_to_update (str): The name of the field to be updated.
        new_value: The new value to set for the field.
        **conditions: Field-value pairs as conditions to filter records.

    Returns:
        str: A message indicating the outcome of the operation.
    """

    # Check if the field to update exists in the model
    if not hasattr(model, field_to_update):
        return f"Error: Field '{field_to_update}' not found in model."

    # Build initial query
    query = update(model)

    # Add conditions to the query
    for field, value in conditions.items():
        if not hasattr(model, field):
            return f"Error: Condition field '{field}' not found in model."
        query = query.where(getattr(model, field) == value)

    try:
        # Apply the update
        query = query.values({field_to_update: new_value})

        # Execute the query
        result = db.session.execute(query)
        db.session.commit()

        # Return the number of rows matched
        return f"Updated {result.rowcount} records."
    except SQLAlchemyError as e:
        # Rollback in case of error
        db.session.rollback()
        return f"Error: {e}"


def set_single_value_on_list(target_model, key_col_target, items_to_update, key_col_input, target_field_to_update, new_value):
    """
    Sets the value of a specified field in the target model to a specified value specified.
    Takes a list of items as input. Searches key_col_target for the values from key_col_input, and, if a match is found,
    sets the target field to a new value.
    
    Args:
        target_model: _description_
        key_col_target: _description_
        items_to_update: _description_
        key_col_input: _description_
        target_field_to_update: _description_
        new_value: value to be used on the target field
    
    Returns:
        OperationResult object with result_code, updated_count and not_found_count values set
    
    """
 
    result = OperationResult()
    records_updated = 0
    records_not_found = 0
    erroneous_inputs = 0
        
    try:
        for item in items_to_update:
            if key_col_input not in item:
                erroneous_inputs += 1
                continue

            search_value = item[key_col_input]
            target_record = target_model.query.filter_by(**{key_col_target: search_value}).first()

            if target_record:
                setattr(target_record, target_field_to_update, new_value)
                records_updated += 1
            else:
                records_not_found += 1

        db.session.commit()
        result.update(result_code=OperationResult.SUCCESS,
                      updated_count=records_updated,
                      not_found_count=records_not_found
                      )
  
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f'Error while updating records: {e}')
        result.update(result_code=OperationResult.FAILURE)

    return result

def build_api_url(protocol: str=None, ipv4_address: str=None, 
              port: str=None, api_endpoint: str=None) -> str:
    """
    Builds a full URL for an API endpoint.

    Args:
        protocol (str, optional): protocol to be used. 
        ipv4_address (str, optional): IPv4 address of the API endpoint. 
        port (str, optional): Port used by the API endpoint
        api_endpoint (str, optional): Path to API endpoint

    All parameters above are optional, if any is omitted, default settings from app config are used.
    
    Returns:
        str: Full URL to API endpoint.
    """
    if protocol is None:
        protocol = "https" if current_app.config.get("USE_HTTPS") else "http"
        # protocol = current_app.config.get('DEFAULT_PROTOCOL', 'http')
    if ipv4_address is None:
        ipv4_address = current_app.config.get('DEFAULT_STORE_IPV4', '127.0.0.1')
    if port is None:
        port = current_app.config.get('DEFAULT_STORE_PORT', '5050')
    if api_endpoint is None:
        api_endpoint = current_app.config.get('DEFAULT_API_ENDPOINT', '')

    return f"{protocol}://{ipv4_address}:{port}/{api_endpoint}".rstrip('/')

