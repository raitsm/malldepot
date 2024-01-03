from flask import redirect, url_for, render_template, request
from flask_login import current_user, login_required
from .forms import SupportForm


from app.main import bp_main

@bp_main.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    return render_template("main/dashboard.html") 
    # return redirect(url_for('main.dashboard'))  # Adjust this to your authenticated landing page

@bp_main.route('/support', methods=['GET', 'POST'])
def support():
    form = SupportForm()
    if form.validate_on_submit():
        # Redirect to previous page or a default page
        return redirect(request.args.get('next') or url_for('main.index'))
    return render_template("main/support.html", form=form)

@bp_main.route('/dashboard')
@login_required
def dashboard():
    return render_template("main/dashboard.html")
