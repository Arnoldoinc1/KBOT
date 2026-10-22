from __future__ import annotations

import re
import uuid

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from common.models import User, db


bp = Blueprint("auth", __name__)


def _start(user: User) -> None:
    session.clear()
    session["student_username"] = user.username
    session["display_name"] = user.name or user.username
    session["quiz_session_id"] = uuid.uuid4().hex


def _success(redirect_endpoint: str, status: int = 200):
    location = url_for(redirect_endpoint)
    if request.is_json:
        return jsonify({"ok": True, "redirect": location}), status
    return redirect(location)


def _failure(message: str, template: str, status: int):
    if request.is_json:
        return jsonify({"ok": False, "error": message}), status
    return render_template(template, error=message), status


@bp.get("/login")
def login_page():
    if session.get("student_username"):
        return redirect(url_for("portal.dashboard"))
    return render_template("login.html")


@bp.post("/login")
def login_action():
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    user = User.query.filter_by(username=username).first() if username else None
    if user is not None:
        role = str(user.role or "").casefold()
        if role not in {"student", "learner"}:
            return _failure(
                "This account belongs to the teacher portal. Please use a student account.",
                "login.html",
                403,
            )
        if user.check_password(password):
            _start(user)
            return _success("portal.dashboard")
        return _failure("Invalid student username or password.", "login.html", 401)

    # v6.2 kept a local demo account that could work before the shared users
    # table existed. Preserve that account while still preferring DB accounts.
    demo_user = str(current_app.config.get("DEMO_USER") or "")
    demo_pass = str(current_app.config.get("DEMO_PASS") or "")
    if username == demo_user and password == demo_pass:
        transient = User(username=username, name=username, role="student", password_hash="")
        _start(transient)
        return _success("portal.dashboard")

    return _failure("Invalid student username or password.", "login.html", 401)


@bp.get("/register")
def register_page():
    if session.get("student_username"):
        return redirect(url_for("portal.dashboard"))
    return render_template("register.html")


@bp.post("/register")
def register_action():
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}
    username = str(data.get("username") or "").strip()
    name = str(data.get("name") or "").strip()
    password = str(data.get("password") or "")
    confirmation = str(data.get("confirm_password") or "")

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", username):
        return _failure(
            "Username must be 3–40 characters using letters, numbers, dot, underscore, or hyphen.",
            "register.html",
            400,
        )
    if len(name) > 80 or not (6 <= len(password) <= 128) or password != confirmation:
        return _failure(
            "Check the display name, password length, and password confirmation.",
            "register.html",
            400,
        )

    user = User(username=username, name=name or username, role="student", password_hash="")
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _failure("This username is already registered.", "register.html", 409)

    _start(user)
    return _success("portal.dashboard", 201)


@bp.post("/logout")
def logout_action():
    session.clear()
    location = url_for("auth.login_page")
    if request.is_json:
        return jsonify({"ok": True, "redirect": location})
    return redirect(location)
