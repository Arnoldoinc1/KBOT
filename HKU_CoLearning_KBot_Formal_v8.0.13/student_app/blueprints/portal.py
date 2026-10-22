from flask import Blueprint, redirect, render_template, session, url_for

from common.auth import student_login_required


bp = Blueprint("portal", __name__)


@bp.get("/")
def home():
    return redirect(url_for("portal.dashboard")) if session.get("student_username") else redirect(url_for("auth.login_page"))


@bp.get("/dashboard")
@student_login_required
def dashboard():
    return render_template("dashboard.html", enabled=current_enabled())


def current_enabled() -> set[str]:
    from flask import current_app
    return current_app.config["ENABLED_STUDENT_MODULES"]

