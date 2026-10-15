import os
from functools import wraps
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, request, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["FLASK_SECRET_KEY"],
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "rolliepods_db"),
    )

def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Please log in first."}), 401
        return route_function(*args, **kwargs)
    return wrapper


def admin_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Please log in first."}), 401

        if session.get("role") != "admin":
            return jsonify({"error": "Administrator access required."}), 403

        return route_function(*args, **kwargs)
    return wrapper


def read_json():
    return request.get_json(silent=True) or {}

@app.get("/api")
def api_status():
    return jsonify({
        "message": "Rolliepods API is running."
    })

@app.post("/api/register")
@limiter.limit("3 per hour")
def register():
    data = read_json()

    name = data.get("full_name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not isinstance(password, str):
        return jsonify({"error": "Name, email, and password are required."}), 400

    if len(name) > 100 or len(email) > 150:
        return jsonify({"error": "Name or email is too long."}), 400

    if "@" not in email:
        return jsonify({"error": "Enter a valid email address."}), 400

    if len(password) < 8 or len(password) > 128:
        return jsonify({"error": "Password must be 8–128 characters."}), 400

    password_hash = generate_password_hash(password)

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users (full_name, email, password_hash, role)
            VALUES (%s, %s, %s, 'tenant')
            """,
            (name, email, password_hash),
        )
        db.commit()

        return jsonify({
            "message": "Registration successful.",
            "user_id": cursor.lastrowid,
        }), 201

    except mysql.connector.IntegrityError:
        db.rollback()
        return jsonify({"error": "That email is already registered."}), 409

    finally:
        cursor.close()
        db.close()
        
@app.post("/api/login")
@limiter.limit("5 per minute")
def login():
    data = read_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not isinstance(password, str) or not password:
        return jsonify({"error": "Email and password are required."}), 400

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id, full_name, email, password_hash, role
            FROM users
            WHERE email = %s
            """,
            (email,),
        )
        user = cursor.fetchone()

        if not user or not check_password_hash(
            user["password_hash"], password
        ):
            return jsonify({"error": "Invalid email or password."}), 401

        session.clear()
        session["user_id"] = user["user_id"]
        session["role"] = user["role"]

        return jsonify({
            "message": "Login successful.",
            "user": {
                "user_id": user["user_id"],
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"],
            },
        })

    finally:
        cursor.close()
        db.close()
        
@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        "error": "Too many attempts. Please try again later."
    }), 429

@app.get("/api/me")
@login_required
def current_user():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id, full_name, email, role
            FROM users WHERE user_id = %s
            """,
            (session["user_id"],),
        )
        user = cursor.fetchone()

        if not user:
            session.clear()
            return jsonify({"error": "Account not found."}), 404

        return jsonify({"user": user})

    finally:
        cursor.close()
        db.close()


@app.post("/api/logout")
@login_required
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."})

@app.get("/api/announcements")
@login_required
def get_announcements():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT a.announcement_id, a.title, a.content,
                a.created_at, a.updated_at,
                u.full_name AS author
            FROM announcements a
            LEFT JOIN users u ON a.author_id = u.user_id
            WHERE a.is_published = TRUE
            ORDER BY a.created_at DESC
            """
        )
        return jsonify({"announcements": cursor.fetchall()})

    finally:
        cursor.close()
        db.close()


@app.post("/api/announcements")
@admin_required
def create_announcement():
    data = read_json()
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()

    if not title or not content:
        return jsonify({"error": "Title and content are required."}), 400

    if len(title) > 200:
        return jsonify({"error": "Title must be at most 200 characters."}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO announcements (title, content, author_id)
            VALUES (%s, %s, %s)
            """,
            (title, content, session["user_id"]),
        )
        db.commit()

        return jsonify({
            "message": "Announcement created.",
            "announcement_id": cursor.lastrowid,
        }), 201

    finally:
        cursor.close()
        db.close()


@app.put("/api/announcements/<int:announcement_id>")
@admin_required
def update_announcement(announcement_id):
    data = read_json()
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()

    if not title or not content:
        return jsonify({"error": "Title and content are required."}), 400

    if len(title) > 200:
        return jsonify({"error": "Title must be at most 200 characters."}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            UPDATE announcements
            SET title = %s, content = %s
            WHERE announcement_id = %s
            """,
            (title, content, announcement_id),
        )
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Announcement not found."}), 404

        return jsonify({"message": "Announcement updated."})

    finally:
        cursor.close()
        db.close()


@app.delete("/api/announcements/<int:announcement_id>")
@admin_required
def delete_announcement(announcement_id):
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            "DELETE FROM announcements WHERE announcement_id = %s",
            (announcement_id,),
        )
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Announcement not found."}), 404

        return jsonify({"message": "Announcement deleted."})

    finally:
        cursor.close()
        db.close()

@app.post("/api/inquiries")
@login_required
def create_inquiry():
    data = read_json()
    subject = data.get("subject", "").strip()
    message = data.get("message", "").strip()
    inquiry_type = data.get("inquiry_type", "general")

    if not subject or not message:
        return jsonify({"error": "Subject and message are required."}), 400

    if len(subject) > 200:
        return jsonify({"error": "Subject must be at most 200 characters."}), 400

    if inquiry_type not in ("general", "maintenance"):
        return jsonify({"error": "Invalid inquiry type."}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO inquiries
                (tenant_id, subject, message, inquiry_type)
            VALUES (%s, %s, %s, %s)
            """,
            (session["user_id"], subject, message, inquiry_type),
        )
        db.commit()

        return jsonify({
            "message": "Inquiry submitted successfully.",
            "inquiry_id": cursor.lastrowid,
            "status": "pending",
        }), 201

    finally:
        cursor.close()
        db.close()

@app.get("/api/inquiries")
@login_required
def get_my_inquiries():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT inquiry_id, subject, message, inquiry_type,
                status, admin_response, created_at, updated_at,
                resolved_at
            FROM inquiries
            WHERE tenant_id = %s
            ORDER BY created_at DESC
            """,
            (session["user_id"],),
        )
        return jsonify({"inquiries": cursor.fetchall()})

    finally:
        cursor.close()
        db.close()
        
@app.get("/api/admin/inquiries")
@admin_required
def admin_get_inquiries():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT i.inquiry_id, i.tenant_id,
                u.full_name AS tenant_name,
                u.email AS tenant_email,
                i.subject, i.message, i.inquiry_type,
                i.status, i.admin_response,
                i.created_at, i.updated_at, i.resolved_at
            FROM inquiries i
            JOIN users u ON i.tenant_id = u.user_id
            ORDER BY i.created_at DESC
            """
        )
        return jsonify({"inquiries": cursor.fetchall()})

    finally:
        cursor.close()
        db.close()


@app.patch("/api/admin/inquiries/<int:inquiry_id>")
@admin_required
def update_inquiry_status(inquiry_id):
    data = read_json()
    status = data.get("status")
    response = data.get("admin_response")

    allowed_statuses = {
        "pending", "in_progress", "resolved", "closed"
    }

    if status not in allowed_statuses:
        return jsonify({"error": "Invalid inquiry status."}), 400

    if response is not None and not isinstance(response, str):
        return jsonify({"error": "Admin response must be text."}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            UPDATE inquiries
            SET status = %s,
                admin_response = COALESCE(%s, admin_response),
                resolved_at = CASE
                    WHEN %s = 'resolved'
                        THEN COALESCE(resolved_at, NOW())
                    ELSE NULL
                END
            WHERE inquiry_id = %s
            """,
            (status, response, status, inquiry_id),
        )
        db.commit()

        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT inquiry_id FROM inquiries WHERE inquiry_id = %s",
                (inquiry_id,),
            )
            if not cursor.fetchone():
                return jsonify({"error": "Inquiry not found."}), 404

        return jsonify({"message": "Inquiry updated successfully."})

    finally:
        cursor.close()
        db.close()

if __name__ == "__main__":
    app.run(debug=True)
