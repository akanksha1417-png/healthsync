import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'healthsync-super-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///healthsync.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    blood_group = db.Column(db.String(20), nullable=True)

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)

class Symptom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)

class TimelineEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROUTES ====================

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        age = request.form.get("age")
        blood_group = request.form.get("blood_group")

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash("Email already registered.")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(
            name=name, 
            email=email, 
            password_hash=hashed_pw,
            age=int(age) if age else None,
            blood_group=blood_group
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for("dashboard"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.")
            return redirect(url_for("login"))

    return render_template("auth.html")

@app.route("/dashboard")
@login_required
def dashboard():
    medicines_count = Medicine.query.filter_by(user_id=current_user.id).count()
    symptoms_count = Symptom.query.filter_by(user_id=current_user.id).count()
    reports_count = Report.query.filter_by(user_id=current_user.id).count()
    timeline_count = TimelineEvent.query.filter_by(user_id=current_user.id).count()

    return render_template("dashboard.html", 
                           user=current_user,
                           medicines_count=medicines_count,
                           symptoms_count=symptoms_count,
                           reports_count=reports_count,
                           timeline_count=timeline_count)

@app.route("/api/health-summary")
@login_required
def health_summary():
    return jsonify({
        "name": current_user.name,
        "medicines": Medicine.query.filter_by(user_id=current_user.id).count(),
        "symptoms": Symptom.query.filter_by(user_id=current_user.id).count(),
        "reports": Report.query.filter_by(user_id=current_user.id).count(),
        "timeline_events": TimelineEvent.query.filter_by(user_id=current_user.id).count()
    })

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# ==================== INITIALIZATION ====================

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
    
