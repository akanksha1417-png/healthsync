import os
import uuid
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
QR_DIR = os.path.join(BASE_DIR, "static", "qrcodes")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(QR_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "healthsync.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer)
    blood_group = db.Column(db.String(20))
    allergies = db.Column(db.Text)
    emergency_contact = db.Column(db.String(120))
    important_info = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    medicines = db.relationship("Medicine", backref="user", lazy=True, cascade="all, delete-orphan")
    symptoms = db.relationship("Symptom", backref="user", lazy=True, cascade="all, delete-orphan")
    reports = db.relationship("Report", backref="user", lazy=True, cascade="all, delete-orphan")
    timeline = db.relationship("TimelineEvent", backref="user", lazy=True, cascade="all, delete-orphan")


class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    specialization = db.Column(db.String(120), nullable=False)
    hospital = db.Column(db.String(180), nullable=False)
    city = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    fee = db.Column(db.Float)
    available_days = db.Column(db.String(200))
    available_time = db.Column(db.String(100))
    appointments = db.relationship("Appointment", backref="doctor", lazy=True, cascade="all, delete-orphan")


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)
    appointment_date = db.Column(db.String(30), nullable=False)
    appointment_time = db.Column(db.String(30), nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(30), default="Booked")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    schedule = db.Column(db.String(120), nullable=False)
    dosage = db.Column(db.String(120))
    expiry_date = db.Column(db.String(30))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Symptom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    symptoms = db.Column(db.Text, nullable=False)
    duration = db.Column(db.String(120))
    severity = db.Column(db.String(30))
    result = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    report_date = db.Column(db.String(30))
    hemoglobin = db.Column(db.Float)
    glucose = db.Column(db.Float)
    cholesterol = db.Column(db.Float)
    notes = db.Column(db.Text)
    file_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TimelineEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ShareToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def current_user():
    if "user_id" not in session:
        return None
    return db.session.get(User, session["user_id"])


def symptom_advice(symptom_text, severity):
    """Educational rule-based assistant; not a diagnosis."""
    text = symptom_text.lower()
    urgent_words = ["severe chest pain", "difficulty breathing", "fainting",
                    "unconscious", "heavy bleeding", "seizure"]
    if severity == "Severe" or any(x in text for x in urgent_words):
        return ("URGENT: Severe symptoms can require immediate professional attention. "
                "Contact local emergency services or seek urgent medical care. "
                "This app does not diagnose conditions.")

    if "fever" in text and "cough" in text:
        return ("Fever with cough can occur with several illnesses. Rest, stay hydrated, "
                "monitor symptoms, and consider speaking with a healthcare professional "
                "if symptoms are persistent or worsening.")
    if "headache" in text:
        return ("Headaches have many possible causes. Consider hydration, rest, and "
                "professional advice if the headache is severe, unusual, persistent, "
                "or accompanied by concerning symptoms.")
    if "stomach" in text or "abdominal" in text:
        return ("Stomach discomfort can have many causes. Monitor symptoms and seek "
                "professional advice if pain is severe, persistent, or worsening.")

    return ("General information only: your symptoms may have multiple causes. "
            "Track them in the app and consult a qualified healthcare professional "
            "for diagnosis or treatment advice.")


def report_explanation(report):
    """Simple educational explanation for demo purposes."""
    parts = []
    if report.hemoglobin is not None:
        parts.append("Hemoglobin is a blood measurement related to oxygen-carrying capacity.")
    if report.glucose is not None:
        parts.append("Glucose is a measurement of blood sugar.")
    if report.cholesterol is not None:
        parts.append("Cholesterol is a type of blood lipid measured in many health checkups.")
    return " ".join(parts) or "Add selected report values to receive a simple explanation."


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("Email is already registered.", "danger")
            return redirect(url_for("register"))

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("Account created successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    medicines = Medicine.query.filter_by(user_id=user.id).order_by(Medicine.created_at.desc()).limit(5).all()
    symptoms = Symptom.query.filter_by(user_id=user.id).order_by(Symptom.created_at.desc()).limit(5).all()
    reports = Report.query.filter_by(user_id=user.id).order_by(Report.created_at.desc()).limit(5).all()
    timeline = TimelineEvent.query.filter_by(user_id=user.id).order_by(TimelineEvent.created_at.desc()).limit(8).all()
    return render_template("dashboard.html", user=user, medicines=medicines, symptoms=symptoms,
                           reports=reports, timeline=timeline)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        user.name = request.form["name"]
        user.age = request.form.get("age") or None
        user.blood_group = request.form.get("blood_group")
        user.allergies = request.form.get("allergies")
        user.emergency_contact = request.form.get("emergency_contact")
        user.important_info = request.form.get("important_info")
        db.session.commit()
        flash("Health profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


@app.route("/medicines", methods=["GET", "POST"])
@login_required
def medicines():
    user = current_user()
    if request.method == "POST":
        med = Medicine(
            user_id=user.id,
            name=request.form["name"],
            schedule=request.form["schedule"],
            dosage=request.form.get("dosage"),
            expiry_date=request.form.get("expiry_date"),
            notes=request.form.get("notes")
        )
        db.session.add(med)
        db.session.commit()
        flash("Medicine added.", "success")
        return redirect(url_for("medicines"))
    rows = Medicine.query.filter_by(user_id=user.id).order_by(Medicine.created_at.desc()).all()
    return render_template("medicines.html", medicines=rows)


@app.post("/medicines/delete/<int:medicine_id>")
@login_required
def delete_medicine(medicine_id):
    med = Medicine.query.filter_by(id=medicine_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(med)
    db.session.commit()
    flash("Medicine deleted.", "success")
    return redirect(url_for("medicines"))


@app.route("/symptoms", methods=["GET", "POST"])
@login_required
def symptoms():
    user = current_user()
    result = None
    if request.method == "POST":
        symptom_text = request.form["symptoms"]
        severity = request.form["severity"]
        result = symptom_advice(symptom_text, severity)
        row = Symptom(
            user_id=user.id,
            symptoms=symptom_text,
            duration=request.form.get("duration"),
            severity=severity,
            result=result
        )
        db.session.add(row)
        db.session.add(TimelineEvent(
            user_id=user.id,
            title="Symptom entry",
            description=symptom_text,
            event_date=datetime.utcnow().strftime("%Y-%m-%d")
        ))
        db.session.commit()

    rows = Symptom.query.filter_by(user_id=user.id).order_by(Symptom.created_at.desc()).all()
    return render_template("symptoms.html", symptoms=rows, result=result)


@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    user = current_user()
    explanation = None

    if request.method == "POST":
        file_name = None
        file = request.files.get("report_file")
        if file and file.filename:
            safe = secure_filename(file.filename)
            unique = f"{uuid.uuid4().hex}_{safe}"
            file.save(os.path.join(UPLOAD_DIR, unique))
            file_name = unique

        row = Report(
            user_id=user.id,
            title=request.form["title"],
            report_date=request.form.get("report_date"),
            hemoglobin=float(request.form["hemoglobin"]) if request.form.get("hemoglobin") else None,
            glucose=float(request.form["glucose"]) if request.form.get("glucose") else None,
            cholesterol=float(request.form["cholesterol"]) if request.form.get("cholesterol") else None,
            notes=request.form.get("notes"),
            file_name=file_name
        )
        db.session.add(row)
        db.session.flush()

        explanation = report_explanation(row)

        db.session.add(TimelineEvent(
            user_id=user.id,
            title="Medical report added",
            description=row.title,
            event_date=row.report_date or datetime.utcnow().strftime("%Y-%m-%d")
        ))
        db.session.commit()
        flash("Report saved.", "success")

    rows = Report.query.filter_by(user_id=user.id).order_by(Report.created_at.desc()).all()
    previous = rows[1] if len(rows) > 1 else None
    latest = rows[0] if rows else None
    comparison = None
    if latest and previous:
        comparison = {}
        for field in ["hemoglobin", "glucose", "cholesterol"]:
            a, b = getattr(previous, field), getattr(latest, field)
            if a is not None and b is not None:
                comparison[field] = round(b - a, 2)

    return render_template("reports.html", reports=rows, latest=latest, previous=previous,
                           comparison=comparison, explanation=explanation)


@app.route("/timeline")
@login_required
def timeline():
    rows = TimelineEvent.query.filter_by(user_id=session["user_id"]).order_by(
        TimelineEvent.event_date.desc(), TimelineEvent.created_at.desc()
    ).all()
    return render_template("timeline.html", events=rows)


@app.route("/timeline/add", methods=["POST"])
@login_required
def add_timeline():
    row = TimelineEvent(
        user_id=session["user_id"],
        title=request.form["title"],
        description=request.form.get("description"),
        event_date=request.form.get("event_date")
    )
    db.session.add(row)
    db.session.commit()
    flash("Timeline event added.", "success")
    return redirect(url_for("timeline"))


@app.route("/doctors")
@login_required
def doctors():
    rows = Doctor.query.order_by(Doctor.name).all()
    appointments = Appointment.query.filter_by(user_id=session["user_id"]).order_by(
        Appointment.appointment_date, Appointment.appointment_time
    ).all()
    return render_template("doctors.html", doctors=rows, appointments=appointments)


@app.post("/doctors/seed")
@login_required
def seed_doctors():
    if Doctor.query.count() == 0:
        sample = [
            Doctor(
                name="Dr. Ananya Sharma", specialization="General Physician",
                hospital="City Care Hospital", city="Mainpuri",
                phone="0000000000", fee=500,
                available_days="Mon, Wed, Fri", available_time="10:00 AM - 1:00 PM"
            ),
            Doctor(
                name="Dr. Rahul Verma", specialization="Cardiology",
                hospital="Health Plus Hospital", city="Mainpuri",
                phone="0000000000", fee=800,
                available_days="Tue, Thu", available_time="11:00 AM - 2:00 PM"
            ),
            Doctor(
                name="Dr. Neha Singh", specialization="Dermatology",
                hospital="Wellness Clinic", city="Mainpuri",
                phone="0000000000", fee=600,
                available_days="Mon, Thu, Sat", available_time="4:00 PM - 7:00 PM"
            ),
        ]
        db.session.add_all(sample)
        db.session.commit()
        flash("Demo doctors added.", "success")
    return redirect(url_for("doctors"))


@app.post("/appointments/book")
@login_required
def book_appointment():
    doctor_id = request.form.get("doctor_id", type=int)
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        flash("Doctor not found.", "danger")
        return redirect(url_for("doctors"))

    date = request.form.get("appointment_date")
    time = request.form.get("appointment_time")

    existing = Appointment.query.filter_by(
        doctor_id=doctor.id,
        appointment_date=date,
        appointment_time=time,
        status="Booked"
    ).first()

    if existing:
        flash("That time slot is already booked. Please choose another time.", "danger")
        return redirect(url_for("doctors"))

    appointment = Appointment(
        user_id=session["user_id"],
        doctor_id=doctor.id,
        appointment_date=date,
        appointment_time=time,
        reason=request.form.get("reason"),
        status="Booked"
    )
    db.session.add(appointment)
    db.session.add(TimelineEvent(
        user_id=session["user_id"],
        title="Doctor appointment booked",
        description=f"{doctor.name} — {doctor.specialization}",
        event_date=date
    ))
    db.session.commit()
    flash("Appointment booked successfully.", "success")
    return redirect(url_for("doctors"))


@app.post("/appointments/cancel/<int:appointment_id>")
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.filter_by(
        id=appointment_id, user_id=session["user_id"]
    ).first_or_404()
    appointment.status = "Cancelled"
    db.session.commit()
    flash("Appointment cancelled.", "success")
    return redirect(url_for("doctors"))


@app.route("/emergency")
@login_required
def emergency():
    return render_template("emergency.html", user=current_user())


@app.route("/share", methods=["GET", "POST"])
@login_required
def share():
    user = current_user()
    if request.method == "POST":
        hours = int(request.form.get("hours", 24))
        hours = max(1, min(hours, 168))
        token = secrets.token_urlsafe(32)
        share = ShareToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=hours)
        )
        db.session.add(share)
        db.session.commit()

        share_url = url_for("shared_record", token=token, _external=True)
        img = qrcode.make(share_url)
        qr_name = f"{token}.png"
        img.save(os.path.join(QR_DIR, qr_name))

        return render_template("share.html", user=user, share_url=share_url,
                               qr_url=url_for("static", filename=f"qrcodes/{qr_name}"),
                               expires_at=share.expires_at)

    return render_template("share.html", user=user, share_url=None, qr_url=None, expires_at=None)


@app.route("/shared/<token>")
def shared_record(token):
    share = ShareToken.query.filter_by(token=token).first()
    if not share or share.expires_at < datetime.utcnow():
        return render_template("expired.html"), 410

    user = db.session.get(User, share.user_id)
    reports = Report.query.filter_by(user_id=user.id).order_by(Report.created_at.desc()).all()
    medicines = Medicine.query.filter_by(user_id=user.id).order_by(Medicine.created_at.desc()).all()
    return render_template("shared_record.html", user=user, reports=reports, medicines=medicines,
                           expires_at=share.expires_at)


@app.route("/api/health-summary")
@login_required
def health_summary():
    user = current_user()
    return jsonify({
        "name": user.name,
        "medicines": Medicine.query.filter_by(user_id=user.id).count(),
        "symptoms": Symptom.query.filter_by(user_id=user.id).count(),
        "reports": Report.query.filter_by(user_id=user.id).count(),
        "timeline_events": TimelineEvent.query.filter_by(user_id=user.id).count()
    })


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
