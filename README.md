# HealthSync — Smart Health Companion

A BTech mini-project starter built with Flask + SQLite.

## Features included

- User registration/login
- Digital health profile
- Symptom journal + rule-based educational assistant
- Medical report storage
- Simple report explanation
- Previous/latest report comparison
- Medicine manager
- Health timeline
- Emergency health card
- Temporary health sharing link
- Temporary QR code
- Doctor directory with demo doctors
- Appointment booking and slot-conflict checking
- Appointment cancellation
- Appointment events added to the health timeline
- Basic JSON health summary API

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this project folder.
3. Create a virtual environment:

   Windows:
   `python -m venv venv`
   `venv\Scripts\activate`

   macOS/Linux:
   `python3 -m venv venv`
   `source venv/bin/activate`

4. Install dependencies:

   `pip install -r requirements.txt`

5. Start:

   `python app.py`

6. Open:

   `http://127.0.0.1:5000`

## Important

This is a student-project MVP. Do not use it as a real medical system without professional review, proper security, encryption, privacy controls, secure deployment, audit logs, validated medical datasets, and clinical oversight.

The symptom assistant is deliberately rule-based and educational; it does not diagnose disease.
