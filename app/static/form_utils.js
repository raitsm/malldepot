// form-utils.js
window.onload = function() {
    // Store initial values
    window.initialData = {};
    document.querySelectorAll('.form-control').forEach(function(field) {
        window.initialData[field.name] = field.value;
    });
};

function confirmSubmitChanges() {
    var isChanged = checkFormChanges();
    if (isChanged) {
        return confirm('Submit the changes?');
    }
    return true;  // No changes detected, submit the form without confirmation
}

function confirmCancel(url) {
    var isChanged = checkFormChanges();
    if (isChanged && !confirm('Discard changes?')) {
        return;  // User chose not to cancel, do nothing
    }
    window.location.href = url;  // Redirect to the provided URL
}


function checkFormChanges() {
    var isChanged = false;
    document.querySelectorAll('.form-control').forEach(function(field) {
        if (window.initialData[field.name] !== field.value) {
            isChanged = true;
        }
    });
    return isChanged;
}

