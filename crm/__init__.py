import os
from flask import Flask
from config import Config
from .extensions import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs("instance", exist_ok=True)
    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    @app.errorhandler(ValueError)
    def handle_validation_error(error):
        db.session.rollback()
        return {"error": str(error)}, 400

    @app.errorhandler(400)
    def handle_bad_request(error):
        db.session.rollback()
        return {"error": getattr(error, "description", "Некорректный запрос")}, 400

    with app.app_context():
        db.create_all()
        seed_database()
    return app


def seed_database():
    from .models import User
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@local.crm", full_name="Администратор", role="admin")
        admin.set_password(os.getenv("ADMIN_PASSWORD", "admin123"))
        db.session.add(admin)
        db.session.commit()
