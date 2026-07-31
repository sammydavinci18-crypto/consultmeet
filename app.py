from flask import Flask
from flask_login import LoginManager

from config import Config
from extensions import db, login_manager, socketio
from models import User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.meetings import meetings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(meetings_bp)

    # Register Socket.IO events
    import sockets  # noqa: F401

    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    @app.cli.command("init-db")
    def init_db():
        """Create all database tables manually."""
        with app.app_context():
            db.create_all()
        print("Database tables created.")

    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
