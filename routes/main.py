from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from models import Meeting, MeetingParticipant

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    hosted = (
        Meeting.query.filter_by(host_id=current_user.id)
        .order_by(Meeting.created_at.desc())
        .all()
    )

    joined_rows = (
        MeetingParticipant.query.filter_by(user_id=current_user.id).all()
    )
    joined = [
        row.meeting for row in joined_rows if row.meeting.host_id != current_user.id
    ]

    return render_template("dashboard.html", hosted=hosted, joined=joined)
