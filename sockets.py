from flask import request
from flask_login import current_user
from flask_socketio import join_room, leave_room, emit
from datetime import datetime

from extensions import socketio, db
from models import Meeting, MeetingParticipant

# Tracks which socket id belongs to which (room_code, user) so we can
# tell everyone else in the room when someone disconnects.
CONNECTED = {}  # sid -> {"room_code": str, "user_id": int, "name": str, "is_host": bool}

# Participants who have requested to join but haven't been admitted yet.
# room_code -> { sid: name }
WAITING = {}


def _host_sid_for_room(room_code):
    return next(
        (s for s, info in CONNECTED.items() if info["room_code"] == room_code and info["is_host"]),
        None,
    )


# ---------------------------------------------------------------------------
# Waiting room / lobby
# ---------------------------------------------------------------------------

@socketio.on("request_to_join")
def handle_request_to_join(data):
    """First thing a client does on page load. Host is auto-admitted.
    Everyone else waits for the host to approve them, unless no host is
    currently in the room (then we let them straight in rather than stall)."""
    room_code = data.get("room_code")
    if not current_user.is_authenticated:
        return

    meeting = Meeting.query.filter_by(room_code=room_code).first()
    if not meeting:
        return

    sid = request.sid
    is_host = meeting.host_id == current_user.id

    if is_host:
        emit("join_approved", {})
        return

    host_sid = _host_sid_for_room(room_code)
    if not host_sid:
        emit("join_approved", {})
        return

    WAITING.setdefault(room_code, {})[sid] = current_user.name
    emit("join_request", {"sid": sid, "name": current_user.name}, room=host_sid)
    emit("waiting_for_host", {})


@socketio.on("admit_participant")
def handle_admit_participant(data):
    room_code = data.get("room_code")
    target_sid = data.get("sid")
    if not current_user.is_authenticated or not target_sid:
        return

    meeting = Meeting.query.filter_by(room_code=room_code).first()
    if not meeting or meeting.host_id != current_user.id:
        return

    WAITING.get(room_code, {}).pop(target_sid, None)
    emit("join_approved", {}, room=target_sid)


@socketio.on("deny_participant")
def handle_deny_participant(data):
    room_code = data.get("room_code")
    target_sid = data.get("sid")
    if not current_user.is_authenticated or not target_sid:
        return

    meeting = Meeting.query.filter_by(room_code=room_code).first()
    if not meeting or meeting.host_id != current_user.id:
        return

    WAITING.get(room_code, {}).pop(target_sid, None)
    emit("join_denied", {}, room=target_sid)


# ---------------------------------------------------------------------------
# Mesh call join / signaling (unchanged flow, just gated behind admission now)
# ---------------------------------------------------------------------------

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
    target = data.get("target")
    if not target:
        return
    emit(
        "signal",
        {"sender": request.sid, "signal": data.get("signal")},
        room=target,
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Reactions / hand raise
# ---------------------------------------------------------------------------

@socketio.on("reaction")
def handle_reaction(data):
    sid = request.sid
    info = CONNECTED.get(sid)
    if not info:
        return
    emoji = (data.get("emoji") or "")[:8]
    if not emoji:
        return
    emit(
        "reaction",
        {"sid": sid, "name": info["name"], "emoji": emoji},
        room=info["room_code"],
    )


@socketio.on("hand_raise")
def handle_hand_raise(data):
    sid = request.sid
    info = CONNECTED.get(sid)
    if not info:
        return
    raised = bool(data.get("raised"))
    emit(
        "hand_raise",
        {"sid": sid, "name": info["name"], "raised": raised},
        room=info["room_code"],
    )


# ---------------------------------------------------------------------------
# Screen share presence (actual media swap happens over the existing
# WebRTC peer connections — this just lets the UI show a "presenting" badge)
# ---------------------------------------------------------------------------

@socketio.on("screen_share")
def handle_screen_share(data):
    sid = request.sid
    info = CONNECTED.get(sid)
    if not info:
        return
    sharing = bool(data.get("sharing"))
    emit(
        "screen_share",
        {"sid": sid, "name": info["name"], "sharing": sharing},
        room=info["room_code"],
        include_self=False,
    )


# ---------------------------------------------------------------------------
# Host controls
# ---------------------------------------------------------------------------

@socketio.on("host_mute_all")
def handle_host_mute_all(data):
    room_code = data.get("room_code")
    if not current_user.is_authenticated:
        return
    meeting = Meeting.query.filter_by(room_code=room_code).first()
    if not meeting or meeting.host_id != current_user.id:
        return
    emit("force_mute", {}, room=room_code, include_self=False)


@socketio.on("host_remove_participant")
def handle_host_remove_participant(data):
    room_code = data.get("room_code")
    target_sid = data.get("sid")
    if not current_user.is_authenticated or not target_sid:
        return
    meeting = Meeting.query.filter_by(room_code=room_code).first()
    if not meeting or meeting.host_id != current_user.id:
        return
    emit("removed_by_host", {}, room=target_sid)


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid

    # Clear from any waiting-room lists regardless of admission state.
    for pending in WAITING.values():
        pending.pop(sid, None)

    info = CONNECTED.pop(sid, None)
    if not info:
        return

    room_code = info["room_code"]
    emit("peer_left", {"sid": sid}, room=room_code)

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
