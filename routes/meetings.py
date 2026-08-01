import os
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    abort,
    jsonify,
    current_app,
    send_file,
)
from flask_login import login_required, current_user

from extensions import db, socketio
from models import Meeting, MeetingParticipant, ConsultationNote, Recording, User

meetings_bp = Blueprint("meetings", __name__)


@meetings_bp.route("/meetings/new", methods=["GET", "POST"])
@login_required
def create_meeting():
    if request.method == "POST":
        title = request.form.get("title", "").strip() or "Consultation"
        scheduled_raw = request.form.get("scheduled_time", "").strip()
        scheduled_time = None
        if scheduled_raw:
            try:
                scheduled_time = datetime.fromisoformat(scheduled_raw)
            except ValueError:
                scheduled_time = None

        meeting = Meeting(title=title, host_id=current_user.id, scheduled_time=scheduled_time)
        db.session.add(meeting)
        db.session.commit()

        flash("Meeting created. Share the room code with your participants.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("create_meeting.html")


@meetings_bp.route("/join", methods=["GET", "POST"])
@login_required
def join_meeting():
    if request.method == "POST":
        code = request.form.get("room_code", "").strip()
        meeting = Meeting.query.filter_by(room_code=code).first()
        if not meeting:
            flash("No meeting found with that room code.", "error")
            return render_template("join_meeting.html")
        return redirect(url_for("meetings.room", room_code=meeting.room_code))

    return render_template("join_meeting.html")


@meetings_bp.route("/room/<room_code>")
@login_required
def room(room_code):
    meeting = Meeting.query.filter_by(room_code=room_code).first_or_404()

    # A meeting the host has already ended: show playback instead of a live room.
    if meeting.status == "ended":
        if meeting.recording and meeting.recording.finalized:
            return render_template("playback.html", meeting=meeting)
        return render_template("meeting_ended.html", meeting=meeting)

    # Record (or refresh) this user's participation, unless they're the host
    if meeting.host_id != current_user.id:
        existing = MeetingParticipant.query.filter_by(
            meeting_id=meeting.id, user_id=current_user.id, left_at=None
        ).first()
        if not existing:
            db.session.add(MeetingParticipant(meeting_id=meeting.id, user_id=current_user.id))
            db.session.commit()

    meeting.status = "live"
    db.session.commit()

    is_host = meeting.host_id == current_user.id
    return render_template("meeting_room.html", meeting=meeting, is_host=is_host)


@meetings_bp.route("/room/<room_code>/notes", methods=["GET", "POST"])
@login_required
def notes(room_code):
    meeting = Meeting.query.filter_by(room_code=room_code).first_or_404()

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if content:
            note = ConsultationNote(meeting_id=meeting.id, author_id=current_user.id, content=content)
            db.session.add(note)
            db.session.commit()

            # Push it to everyone else in the room right away, so people
            # don't have to close/reopen the panel to see new notes.
            socketio.emit(
                "note_added",
                {
                    "author": note.author.name,
                    "content": note.content,
                    "created_at": note.created_at.strftime("%b %d, %Y %I:%M %p"),
                },
                room=meeting.room_code,
            )
        return jsonify(
            notes=[
                {
                    "author": n.author.name,
                    "content": n.content,
                    "created_at": n.created_at.strftime("%b %d, %Y %I:%M %p"),
                }
                for n in sorted(meeting.notes, key=lambda x: x.created_at)
            ]
        )

    return jsonify(
        notes=[
            {
                "author": n.author.name,
                "content": n.content,
                "created_at": n.created_at.strftime("%b %d, %Y %I:%M %p"),
            }
            for n in sorted(meeting.notes, key=lambda x: x.created_at)
        ]
    )


def _recording_path(meeting):
    return os.path.join(current_app.config["RECORDINGS_DIR"], f"{meeting.id}.webm")


@meetings_bp.route("/room/<room_code>/recording/chunk", methods=["POST"])
@login_required
def upload_recording_chunk(room_code):
    """The host's browser POSTs the meeting recording here in ~30s chunks
    while the call is happening, so at most a few seconds are ever at risk
    if the host's browser crashes."""
    meeting = Meeting.query.filter_by(room_code=room_code).first_or_404()
    if meeting.host_id != current_user.id:
        abort(403)

    chunk = request.get_data()
    if not chunk:
        return jsonify(ok=True)

    path = _recording_path(meeting)
    with open(path, "ab") as f:
        f.write(chunk)

    recording = Recording.query.filter_by(meeting_id=meeting.id).first()
    if not recording:
        recording = Recording(meeting_id=meeting.id, filename=os.path.basename(path), finalized=False)
        db.session.add(recording)
        db.session.commit()

    return jsonify(ok=True)


@meetings_bp.route("/room/<room_code>/end", methods=["POST"])
@login_required
def end_meeting(room_code):
    """Host ends the meeting: locks it as 'ended' and finalizes the recording
    (if any) so it becomes watchable via the same room code afterward."""
    meeting = Meeting.query.filter_by(room_code=room_code).first_or_404()
    if meeting.host_id != current_user.id:
        abort(403)

    meeting.status = "ended"

    recording = Recording.query.filter_by(meeting_id=meeting.id).first()
    if recording and os.path.exists(_recording_path(meeting)):
        recording.finalized = True

    db.session.commit()
    return jsonify(ok=True, redirect=url_for("main.dashboard"))


@meetings_bp.route("/recordings/<int:meeting_id>/file")
@login_required
def stream_recording(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    recording = meeting.recording

    if not recording or not recording.finalized:
        abort(404)

    # Only the host or someone who actually attended can watch it back.
    is_host = meeting.host_id == current_user.id
    was_participant = MeetingParticipant.query.filter_by(
        meeting_id=meeting.id, user_id=current_user.id
    ).first() is not None
    if not (is_host or was_participant):
        abort(403)

    path = _recording_path(meeting)
    if not os.path.exists(path):
        abort(404)

    return send_file(path, mimetype="video/webm", conditional=True)
