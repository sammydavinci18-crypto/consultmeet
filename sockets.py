from flask import request
from flask_login import current_user
from flask_socketio import join_room, leave_room, emit

from extensions import socketio, db
from models import Meeting, MeetingParticipant
from datetime import datetime

# Tracks which socket id belongs to which (room_code, user) so we can
# tell everyone else in the room when someone disconnects.
CONNECTED = {}  # sid -> {"room_code": str, "user_id": int, "name": str, "is_host": bool}


@socketio.on("join")
def handle_join(data):
    room_code = data.get("room_code")
    if not current_user.is_authenticated:
        return

    meeting = Meeting.query.filter_by(room_code=room_code).first()
    if not meeting:
        return

    is_host = meeting.host_id == current_user.id
    sid = request.sid

    # Tell the new arrival who is already in the room, so THEY initiate
    # a connection to each existing peer (classic mesh join pattern).
    existing_peers = [
        {"sid": s, "name": info["name"], "is_host": info["is_host"]}
        for s, info in CONNECTED.items()
        if info["room_code"] == room_code
    ]

    CONNECTED[sid] = {
        "room_code": room_code,
        "user_id": current_user.id,
        "name": current_user.name,
        "is_host": is_host,
    }

    join_room(room_code)

    emit("existing_peers", {"peers": existing_peers})
    emit(
        "peer_joined",
        {"sid": sid, "name": current_user.name, "is_host": is_host},
        room=room_code,
        include_self=False,
    )


@socketio.on("signal")
def handle_signal(data):
    # data: { target: sid, signal: {...offer/answer/candidate} }
    target = data.get("target")
    if not target:
        return
    emit(
        "signal",
        {"sender": request.sid, "signal": data.get("signal")},
        room=target,
    )


@socketio.on("chat_message")
def handle_chat(data):
    sid = request.sid
    info = CONNECTED.get(sid)
    if not info:
        return
    emit(
        "chat_message",
        {"name": info["name"], "message": data.get("message", "")[:2000]},
        room=info["room_code"],
    )


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    info = CONNECTED.pop(sid, None)
    if not info:
        return

    room_code = info["room_code"]
    emit("peer_left", {"sid": sid}, room=room_code)

    # Mark participant as having left, if applicable
    if not info["is_host"]:
        meeting = Meeting.query.filter_by(room_code=room_code).first()
        if meeting:
            row = (
                MeetingParticipant.query.filter_by(
                    meeting_id=meeting.id, user_id=info["user_id"], left_at=None
                )
                .order_by(MeetingParticipant.joined_at.desc())
                .first()
            )
            if row:
                row.left_at = datetime.utcnow()
                db.session.commit()
