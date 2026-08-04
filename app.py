import sys

from flask import Flask
from flask_login import LoginManager
from datetime import datetime, timezone

from config import Config
from extensions import db, login_manager, socketio
from models import User, Meeting, MeetingParticipant, ConsultationNote, Recording  # noqa: F401
# ^ every model is imported explicitly (not just User) so db.create_all()
#   below actually knows about every table, not just whichever one
#   happened to be imported elsewhere already.


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_current_year():
        return {"current_year": datetime.now(timezone.utc).year}

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.meetings import meetings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(meetings_bp)

    # Registers the Socket.IO event handlers defined in sockets.py
    import sockets  # noqa: F401

    # Safety net: make sure tables exist on every boot, regardless of
    # whether this was deployed via the render.yaml Blueprint (which runs
    # `flask --app app init-db` as a preDeployCommand already) or a manually
    # created Render service (which won't run that). db.create_all() only
    # creates tables that don't exist yet, so this is a no-op most of the
    # time and safe to run on every startup.
    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:  # e.g. DB briefly unreachable during a cold start
            print(f"[startup] Skipped db.create_all() — could not reach the database: {exc}", file=sys.stderr)

    @app.cli.command("init-db")
    def init_db():
        """Create all database tables. Run with: flask --app app init-db"""
        with app.app_context():
            db.create_all()
        print("Database tables created.")

    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
