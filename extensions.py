from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"

# threading async mode keeps this dependency-light (no eventlet/gevent required)
socketio = SocketIO(async_mode="threading", cors_allowed_origins="*")
