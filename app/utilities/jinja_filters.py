# Custom Jinja2 filter functions defined below

# converts margin multipliers into easier-to-comprehend percentages.
def format_sales_margin(margin):
    if margin < 1:
        # Convert to negative percentage for discounts
        percentage = (1 - margin) * 100
        return f"-{percentage:.0f}%"
    elif margin > 1:
        # Convert to positive percentage for extra margin
        percentage = (margin - 1) * 100
        return f"+{percentage:.0f}%"
    else:
        # Zero margin
        return "0%"
