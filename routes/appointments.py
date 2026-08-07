from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from extensions import db
from models import Appointment, Meeting

appointments_bp = Blueprint("appointments", __name__)


@appointments_bp.route("/appointments")
@login_required
def my_appointments():
    as_client = (
        Appointment.query.filter_by(client_id=current_user.id)
        .order_by(Appointment.created_at.desc()).all()
    )
    as_consultant = (
        Appointment.query.filter_by(consultant_id=current_user.id)
        .order_by(Appointment.created_at.desc()).all()
    )
    return render_template("appointments/list.html", as_client=as_client, as_consultant=as_consultant)


@appointments_bp.route("/appointments/<int:appointment_id>/confirm", methods=["POST"])
@login_required
def confirm(appointment_id):
    appt = Appointment.query.get_or_404(appointment_id)
    if appt.consultant_id != current_user.id:
        abort(403)
    if appt.status != "pending":
        flash("This request has already been handled.", "error")
        return redirect(url_for("appointments.my_appointments"))

    # Optional: consultant can adjust the agreed price before confirming
    # (e.g. after negotiating over messages).
    price_raw = request.form.get("price_amount", "").strip()
    if price_raw:
        try:
            appt.price_amount = float(price_raw)
        except ValueError:
            pass

    meeting = Meeting(
        title=f"Consultation with {appt.client.name}",
        host_id=appt.consultant_id,
        scheduled_time=appt.requested_time,
    )
    db.session.add(meeting)
    db.session.flush()

    appt.meeting_id = meeting.id
    appt.status = "confirmed"
    appt.responded_at = datetime.utcnow()
    db.session.commit()

    flash("Appointment confirmed. A video room has been created for it.", "success")
    return redirect(url_for("appointments.my_appointments"))


@appointments_bp.route("/appointments/<int:appointment_id>/decline", methods=["POST"])
@login_required
def decline(appointment_id):
    appt = Appointment.query.get_or_404(appointment_id)
    if appt.consultant_id != current_user.id:
        abort(403)
    if appt.status != "pending":
        flash("This request has already been handled.", "error")
        return redirect(url_for("appointments.my_appointments"))

    if appt.slot:
        appt.slot.is_booked = False
    appt.status = "declined"
    appt.responded_at = datetime.utcnow()
    db.session.commit()
    flash("Request declined.", "info")
    return redirect(url_for("appointments.my_appointments"))


@appointments_bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@login_required
def cancel(appointment_id):
    appt = Appointment.query.get_or_404(appointment_id)
    if current_user.id not in (appt.client_id, appt.consultant_id):
        abort(403)
    if appt.status not in ("pending", "confirmed"):
        flash("This appointment can't be cancelled.", "error")
        return redirect(url_for("appointments.my_appointments"))

    if appt.slot:
        appt.slot.is_booked = False
    appt.status = "cancelled"
    db.session.commit()
    flash("Appointment cancelled.", "info")
    return redirect(url_for("appointments.my_appointments"))
