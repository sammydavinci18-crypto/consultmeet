import secrets
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


def generate_room_code():
    return secrets.token_urlsafe(6).replace("_", "").replace("-", "")[:8]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    meetings_hosted = db.relationship(
        "Meeting", backref="host", lazy=True, foreign_keys="Meeting.host_id"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Meeting(db.Model):
    __tablename__ = "meetings"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    room_code = db.Column(db.String(16), unique=True, nullable=False, default=generate_room_code, index=True)
    host_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="scheduled")  # scheduled, live, ended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    participants = db.relationship("MeetingParticipant", backref="meeting", lazy=True, cascade="all, delete-orphan")
    notes = db.relationship("ConsultationNote", backref="meeting", lazy=True, cascade="all, delete-orphan")


class MeetingParticipant(db.Model):
    __tablename__ = "meeting_participants"

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    left_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")


class ConsultationNote(db.Model):
    __tablename__ = "consultation_notes"

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User")


class Recording(db.Model):
    __tablename__ = "recordings"

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"), unique=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)  # relative path under the recordings folder
    finalized = db.Column(db.Boolean, default=False)  # True once the host has ended the meeting
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    meeting = db.relationship("Meeting", backref=db.backref("recording", uselist=False, cascade="all, delete-orphan"))
