from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from extensions import db
from models import Conversation, DirectMessage

messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/messages")
@login_required
def inbox():
    conversations = (
        Conversation.query.filter(
            or_(Conversation.consultant_id == current_user.id, Conversation.client_id == current_user.id)
        )
        .order_by(Conversation.created_at.desc())
        .all()
    )
    # Sort by most recent message, most recent first.
    conversations.sort(
        key=lambda c: c.messages[-1].created_at if c.messages else c.created_at, reverse=True
    )
    return render_template("messages/inbox.html", conversations=conversations)


@messages_bp.route("/messages/<int:conversation_id>", methods=["GET", "POST"])
@login_required
def thread(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    if current_user.id not in (conversation.consultant_id, conversation.client_id):
        abort(403)

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if content:
            db.session.add(DirectMessage(
                conversation_id=conversation.id, sender_id=current_user.id, content=content[:4000]
            ))
            db.session.commit()
        return redirect(url_for("messages.thread", conversation_id=conversation.id))

    # Mark the other party's messages as read.
    unread = [
        m for m in conversation.messages if m.sender_id != current_user.id and m.read_at is None
    ]
    for m in unread:
        m.read_at = datetime.utcnow()
    if unread:
        db.session.commit()

    other = conversation.other_party(current_user.id)
    return render_template("messages/thread.html", conversation=conversation, other=other)
