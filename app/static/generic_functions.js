function confirmCancelNoForm(redirectUrl) {
    if (confirm('Are you sure you want to cancel?')) {
        window.location.href = redirectUrl;
    }
}

/* universal confirm action function with redirect */
function confirmAction(event, redirectUrl) {
    var message = event.target.getAttribute('data-confirm-message');
    if (confirm(message)) {
        window.location.href = redirectUrl;
    } else {
        event.preventDefault();
    }
}



/* universal confirm cancellation message */
function cancelAction(event, redirectUrl) {
    event.preventDefault();  // Prevent form submission
    if (redirectUrl) {
        window.location.href = redirectUrl;  // Redirect to the specified URL
    } else {
        var form = event.target.closest('form');
        if (form) {
            form.reset();  // Reset the form
        }
    }
}

/* 
generic message with OK button
to be used to inform the user that the action is completed.
*/
function messageAndRedirect(message, redirectUrl) {
    if (confirm(message)) {
        window.location.href = redirectUrl;
    }
}

/* logout confirmation */
function confirmLogout() {
    if (confirm('Do you want to log out?')) {
        window.location.href = '/auth/logout';  // if user confirms logout, do logout
    }
}

