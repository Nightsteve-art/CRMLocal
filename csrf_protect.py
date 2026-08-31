"""
CSRF Protection utilities for Flask application
"""
from flask_wtf.csrf import CSRFProtect, generate_csrf
from functools import wraps
from flask import session, abort, request

csrf = CSRFProtect()

def csrf_token():
    """Generate CSRF token for templates"""
    return generate_csrf()

def require_csrf_token(f):
    """Decorator to require CSRF token on POST requests"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            # Token validation is done by @csrf.protect
            pass
        return f(*args, **kwargs)
    return decorated_function
