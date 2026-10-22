from __future__ import annotations

from functools import wraps

from flask import jsonify, redirect, request, session, url_for


def student_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_username"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "Authentication required."}), 401
            return redirect(url_for("auth.login_page"))
        return view(*args, **kwargs)

    return wrapped
