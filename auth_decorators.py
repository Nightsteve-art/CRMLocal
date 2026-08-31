"""
Authentication and authorization decorators
"""
from functools import wraps
from flask import session, redirect, url_for, abort, flash
from app import User, ROLES

def login_required(f):
    """Decorator to require user to be logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Требуется вход в систему', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Требуется вход в систему', 'danger')
                return redirect(url_for('login'))
            
            user = User.query.get(session['user_id'])
            if not user or user.role not in allowed_roles:
                flash('Недостаточно прав доступа', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permission_required(*permissions):
    """Decorator to check specific permissions based on user role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Требуется вход в систему', 'danger')
                return redirect(url_for('login'))
            
            user = User.query.get(session['user_id'])
            if not user:
                abort(401)
            
            user_perms = ROLES.get(user.role, {}).get('permissions', [])
            
            # Check if user has wildcard permission or specific permission
            has_permission = False
            for perm in permissions:
                if '*' in user_perms or perm in user_perms or f"{perm}:*" in user_perms:
                    has_permission = True
                    break
            
            if not has_permission:
                flash('Недостаточно прав доступа', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_user_permission(required_role=None):
    """Check if user is logged in and has required role"""
    if 'user_id' not in session:
        return False
    
    if required_role:
        user = User.query.get(session['user_id'])
        return user and user.role == required_role
    
    return True
