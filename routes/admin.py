import os
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, current_app, send_from_directory
from flask_login import login_required, current_user

from extensions import db
from models import ConsultantProfile, VerificationDocument
from permissions import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/consultants")
@login_required
@admin_required
def queue():
    pending = (
        ConsultantProfile.query.filter_by(status="pending")
        .order_by(ConsultantProfile.submitted_at.asc()).all()
    )
    reviewed = (
        ConsultantProfile.query.filter(ConsultantProfile.status.in_(["approved", "rejected"]))
        .order_by(ConsultantProfile.reviewed_at.desc()).limit(30).all()
    )
    return render_template("admin/queue.html", pending=pending, reviewed=reviewed)


@admin_bp.route("/admin/consultants/<int:profile_id>")
@login_required
@admin_required
def review(profile_id):
    profile = ConsultantProfile.query.get_or_404(profile_id)
    return render_template("admin/review.html", profile=profile)


@admin_bp.route("/admin/consultants/<int:profile_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve(profile_id):
    profile = ConsultantProfile.query.get_or_404(profile_id)
    profile.status = "approved"
    profile.review_note = None
    profile.reviewed_at = datetime.utcnow()
    profile.reviewed_by_id = current_user.id
    db.session.commit()
    flash(f"{profile.user.name} is now a verified consultant.", "success")
    return redirect(url_for("admin.queue"))


@admin_bp.route("/admin/consultants/<int:profile_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject(profile_id):
    profile = ConsultantProfile.query.get_or_404(profile_id)
    profile.status = "rejected"
    profile.review_note = request.form.get("review_note", "").strip()
    profile.reviewed_at = datetime.utcnow()
    profile.reviewed_by_id = current_user.id
    db.session.commit()
    flash(f"{profile.user.name}'s application was rejected.", "info")
    return redirect(url_for("admin.queue"))


@admin_bp.route("/admin/documents/<int:document_id>")
@login_required
def view_document(document_id):
    # Deliberately not @admin_required alone — the consultant who uploaded
    # a document also needs to be able to see their own file. Access is
    # otherwise fully locked down: nobody else, no public /static path.
    doc = VerificationDocument.query.get_or_404(document_id)
    profile = doc.profile
    if not (current_user.is_admin or profile.user_id == current_user.id):
        abort(403)
    docs_dir = current_app.config["VERIFICATION_DOCS_DIR"]
    return send_from_directory(docs_dir, doc.stored_filename, as_attachment=False)
