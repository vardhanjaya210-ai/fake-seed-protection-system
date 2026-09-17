from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from translations import TRANSLATIONS
from ai_researcher import research_product, save_research_result

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "secret123"
)

USERNAME = "admin"
PASSWORD = "1234"

DATABASE = "complaints.db"

OTP_EXPIRY_MINUTES = 5
MAX_OTP_ATTEMPTS = 5

EMAIL_SENDER = os.environ.get(
    "EMAIL_SENDER",
    ""
)

EMAIL_APP_PASSWORD = os.environ.get(
    "EMAIL_APP_PASSWORD",
    ""
)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_type TEXT,
            product TEXT NOT NULL,
            dealer TEXT NOT NULL,
            description TEXT NOT NULL,
            ai_risk TEXT,
            ai_issue TEXT,
            ai_reason TEXT,
            status TEXT DEFAULT 'Pending',
            user_id INTEGER
        )
    """)

    columns_to_add = {
        "product_type": "TEXT",
        "ai_risk": "TEXT",
        "ai_issue": "TEXT",
        "ai_reason": "TEXT",
        "status": "TEXT DEFAULT 'Pending'",
        "user_id": "INTEGER",
        "product_id": "TEXT",
        "company": "TEXT",
        "batch_no": "TEXT",
        "validation_status": "TEXT",
        "validation_reason": "TEXT",
        "validation_method": "TEXT",
        "validation_notes": "TEXT",
        "validated_by": "TEXT",
        "validated_at": "TEXT"
    }

    for column, definition in columns_to_add.items():
        try:
            cursor.execute(
                f"""
                ALTER TABLE complaints
                ADD COLUMN {column} {definition}
                """
            )
        except sqlite3.OperationalError:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE NOT NULL,
            product_type TEXT,
            product_name TEXT NOT NULL,
            company TEXT NOT NULL,
            batch_no TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    product_columns = {
        "product_type": "TEXT"
    }

    for column, definition in product_columns.items():
        try:
            cursor.execute(
                f"""
                ALTER TABLE products
                ADD COLUMN {column} {definition}
                """
            )
        except sqlite3.OperationalError:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            village TEXT,
            mandal TEXT,
            district TEXT
        )
    """)

    user_columns = {
        "email": "TEXT",
        "email_verified": "INTEGER DEFAULT 0",
        "mobile_verified": "INTEGER DEFAULT 0",
        "otp_hash": "TEXT",
        "otp_expires_at": "TEXT",
        "otp_attempts": "INTEGER DEFAULT 0",
        "email_otp_hash": "TEXT",
        "email_otp_expires_at": "TEXT",
        "email_otp_attempts": "INTEGER DEFAULT 0"
    }

    for column, definition in user_columns.items():
        try:
            cursor.execute(
                f"""
                ALTER TABLE users
                ADD COLUMN {column} {definition}
                """
            )
        except sqlite3.OperationalError:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_research_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER,
            product_id TEXT,
            product_type TEXT,
            product_name TEXT,
            company TEXT,
            batch_no TEXT,
            assessment TEXT,
            confidence REAL,
            reason TEXT,
            evidence TEXT,
            sources TEXT,
            analyzed_at TEXT
        )
    """)

    cursor.execute("""
        UPDATE complaints
        SET status = 'Pending'
        WHERE status IS NULL
        OR status = ''
    """)

    default_products = [
        (
            "FS001",
            "Seed",
            "Paddy Seeds",
            "ABC Seeds",
            "B101",
            "Genuine"
        ),
        (
            "FS002",
            "Seed",
            "Groundnut Seeds",
            "Green Agro",
            "B202",
            "Genuine"
        ),
        (
            "FERT001",
            "Fertilizer",
            "Urea Fertilizer",
            "Agro India",
            "U301",
            "Genuine"
        )
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO products
        (
            product_id,
            product_type,
            product_name,
            company,
            batch_no,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, default_products)

    conn.commit()
    conn.close()


@app.context_processor
def inject_translations():
    language = session.get(
        "language",
        "English"
    )

    translations = TRANSLATIONS.get(
        language,
        TRANSLATIONS["English"]
    )

    return {
        "t": translations,
        "current_language": language,
        "languages": TRANSLATIONS.keys(),
        "logged_in_user": session.get(
            "user_name"
        ),
        "is_user_logged_in": (
            "user_id" in session
        ),
        "is_admin_logged_in": (
            "admin_user" in session
        )
    }


@app.route(
    "/set_language/<language>"
)
def set_language(language):
    if language in TRANSLATIONS:
        session["language"] = language

    return redirect(
        request.referrer
        or
        url_for("home")
    )


def analyze_complaint(description):
    text = description.lower()

    high_risk_words = [
        "fake",
        "counterfeit",
        "duplicate",
        "fraud",
        "forged",
        "fake product",
        "fake seed",
        "fake fertilizer"
    ]

    for word in high_risk_words:
        if word in text:
            return (
                "High Risk",
                "Possible Counterfeit",
                "The complaint contains terms associated with a possible counterfeit or fraudulent product."
            )

    germination_words = [
        "not germinating",
        "did not germinate",
        "didn't germinate",
        "not grow",
        "did not grow",
        "didn't grow",
        "seeds not growing",
        "poor germination",
        "low germination",
        "no germination"
    ]

    for word in germination_words:
        if word in text:
            return (
                "Possible Risk",
                "Germination Problem",
                "The complaint indicates poor or unsuccessful seed germination."
            )

    packaging_words = [
        "wrong label",
        "missing label",
        "label missing",
        "suspicious label",
        "package",
        "packaging",
        "batch number missing",
        "no batch number",
        "expiry missing",
        "expiry date missing",
        "seal broken",
        "broken seal"
    ]

    for word in packaging_words:
        if word in text:
            return (
                "Possible Risk",
                "Packaging / Label Problem",
                "The complaint indicates a possible issue with product packaging, labeling, batch information, or sealing."
            )

    fertilizer_words = [
        "fertilizer quality",
        "poor fertilizer",
        "bad fertilizer",
        "fertilizer not working",
        "fertilizer ineffective",
        "fertilizer quality is bad",
        "low quality fertilizer"
    ]

    for word in fertilizer_words:
        if word in text:
            return (
                "Possible Risk",
                "Fertilizer Quality Problem",
                "The complaint indicates a possible fertilizer quality or effectiveness issue."
            )

    quality_words = [
        "bad quality",
        "poor quality",
        "low quality",
        "quality problem",
        "quality issue",
        "damaged",
        "defective",
        "different seeds",
        "wrong product"
    ]

    for word in quality_words:
        if word in text:
            return (
                "Possible Risk",
                "Product Quality Problem",
                "The complaint indicates a possible product quality or product-related issue."
            )

    dealer_words = [
        "dealer cheated",
        "dealer fraud",
        "dealer gave",
        "dealer sold",
        "shopkeeper",
        "seller cheated",
        "seller fraud",
        "wrong product from dealer"
    ]

    for word in dealer_words:
        if word in text:
            return (
                "Possible Risk",
                "Dealer / Seller Issue",
                "The complaint indicates a possible issue involving the dealer or seller."
            )

    return (
        "Low Risk",
        "General Complaint",
        "No major risk-related issue was detected from the complaint description."
    )


def validate_product(
    product_id,
    product_type,
    product_name,
    company,
    batch_no
):
    conn = get_db()

    registered = conn.execute("""
        SELECT
            product_id,
            product_type,
            product_name,
            company,
            batch_no,
            status
        FROM products
        WHERE UPPER(product_id) = UPPER(?)
    """, (
        product_id,
    )).fetchone()

    conn.close()

    if not registered:
        return (
            "Product Not Found",
            "No registered product record was found for the submitted Product ID.",
            "Product Database"
        )

    mismatches = []

    if (
        product_type
        and
        registered["product_type"]
        and
        product_type.lower()
        !=
        registered["product_type"].lower()
    ):
        mismatches.append(
            "Product Type"
        )

    if (
        product_name
        and
        product_name.lower()
        !=
        registered["product_name"].lower()
    ):
        mismatches.append(
            "Product Name"
        )

    if (
        company
        and
        company.lower()
        !=
        registered["company"].lower()
    ):
        mismatches.append(
            "Company"
        )

    if (
        batch_no
        and
        batch_no.lower()
        !=
        registered["batch_no"].lower()
    ):
        mismatches.append(
            "Batch Number"
        )

    if mismatches:
        return (
            "Information Mismatch",
            "The following submitted details do not match the registered product record: "
            +
            ", ".join(mismatches)
            +
            ".",
            "Product Database"
        )

    if (
        registered["status"]
        and
        registered["status"].lower()
        !=
        "genuine"
    ):
        return (
            "Registered Record Requires Review",
            "The registered product record is not marked as Genuine.",
            "Product Database"
        )

    return (
        "Database Match",
        "The submitted Product ID, product type, product name, company and batch number match the registered product record.",
        "Product Database"
    )


def generate_otp():
    return str(
        secrets.randbelow(900000)
        + 100000
    )


def create_demo_otp_for_user(user_id):
    otp = generate_otp()

    otp_hash = generate_password_hash(
        otp
    )

    expires_at = (
        datetime.utcnow()
        +
        timedelta(
            minutes=OTP_EXPIRY_MINUTES
        )
    ).isoformat()

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET
            otp_hash = ?,
            otp_expires_at = ?,
            otp_attempts = 0
        WHERE id = ?
    """, (
        otp_hash,
        expires_at,
        user_id
    ))

    conn.commit()
    conn.close()

    return otp


def send_email_otp(email, otp):
    if (
        not EMAIL_SENDER
        or
        not EMAIL_APP_PASSWORD
    ):
        return (
            False,
            "Email OTP is not configured. Demo OTP is available."
        )

    try:
        message = EmailMessage()

        message["Subject"] = (
            "Fake Seed & Fertilizer Protection System - Email OTP"
        )

        message["From"] = EMAIL_SENDER
        message["To"] = email

        message.set_content(
            f"""
Your Email Verification OTP is: {otp}

This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.

Do not share this OTP with anyone.

Fake Seed & Fertilizer Protection System
"""
        )

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465
        ) as server:

            server.login(
                EMAIL_SENDER,
                EMAIL_APP_PASSWORD
            )

            server.send_message(
                message
            )

        return (
            True,
            "OTP sent successfully to your email."
        )

    except Exception as error:
        print(
            "Email OTP error:",
            error
        )

        return (
            False,
            "Unable to send Email OTP. Demo OTP is available."
        )


def create_email_otp_for_user(
    user_id,
    email
):
    otp = generate_otp()

    otp_hash = generate_password_hash(
        otp
    )

    expires_at = (
        datetime.utcnow()
        +
        timedelta(
            minutes=OTP_EXPIRY_MINUTES
        )
    ).isoformat()

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET
            email_otp_hash = ?,
            email_otp_expires_at = ?,
            email_otp_attempts = 0
        WHERE id = ?
    """, (
        otp_hash,
        expires_at,
        user_id
    ))

    conn.commit()
    conn.close()

    sent, message = send_email_otp(
        email,
        otp
    )

    return (
        sent,
        message
    )


def verify_demo_otp(
    user_id,
    entered_otp
):
    conn = get_db()

    user = conn.execute("""
        SELECT
            otp_hash,
            otp_expires_at,
            otp_attempts
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if not user:
        conn.close()

        return (
            False,
            "User account not found."
        )

    if not user["otp_hash"]:
        conn.close()

        return (
            False,
            "Demo OTP is not available."
        )

    if (
        user["otp_attempts"]
        >=
        MAX_OTP_ATTEMPTS
    ):
        conn.close()

        return (
            False,
            "Maximum OTP attempts reached. Please request a new OTP."
        )

    try:
        expires_at = datetime.fromisoformat(
            user["otp_expires_at"]
        )

    except Exception:
        conn.close()

        return (
            False,
            "OTP information is invalid."
        )

    if datetime.utcnow() > expires_at:
        conn.close()

        return (
            False,
            "OTP has expired. Please request a new OTP."
        )

    if not check_password_hash(
        user["otp_hash"],
        entered_otp
    ):
        conn.execute("""
            UPDATE users
            SET otp_attempts =
                otp_attempts + 1
            WHERE id = ?
        """, (
            user_id,
        ))

        conn.commit()
        conn.close()

        return (
            False,
            "Invalid OTP."
        )

    conn.execute("""
        UPDATE users
        SET
            mobile_verified = 1,
            otp_hash = NULL,
            otp_expires_at = NULL,
            otp_attempts = 0
        WHERE id = ?
    """, (
        user_id,
    ))

    conn.commit()
    conn.close()

    return (
        True,
        "Demo OTP verified successfully."
    )


def verify_email_otp(
    user_id,
    entered_otp
):
    conn = get_db()

    user = conn.execute("""
        SELECT
            email_otp_hash,
            email_otp_expires_at,
            email_otp_attempts
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if not user:
        conn.close()

        return (
            False,
            "User account not found."
        )

    if not user["email_otp_hash"]:
        conn.close()

        return (
            False,
            "Email OTP is not available."
        )

    if (
        user["email_otp_attempts"]
        >=
        MAX_OTP_ATTEMPTS
    ):
        conn.close()

        return (
            False,
            "Maximum OTP attempts reached. Please request a new OTP."
        )

    try:
        expires_at = datetime.fromisoformat(
            user["email_otp_expires_at"]
        )

    except Exception:
        conn.close()

        return (
            False,
            "Email OTP information is invalid."
        )

    if datetime.utcnow() > expires_at:
        conn.close()

        return (
            False,
            "Email OTP has expired. Please request a new OTP."
        )

    if not check_password_hash(
        user["email_otp_hash"],
        entered_otp
    ):
        conn.execute("""
            UPDATE users
            SET email_otp_attempts =
                email_otp_attempts + 1
            WHERE id = ?
        """, (
            user_id,
        ))

        conn.commit()
        conn.close()

        return (
            False,
            "Invalid Email OTP."
        )

    conn.execute("""
        UPDATE users
        SET
            email_verified = 1,
            email_otp_hash = NULL,
            email_otp_expires_at = NULL,
            email_otp_attempts = 0
        WHERE id = ?
    """, (
        user_id,
    ))

    conn.commit()
    conn.close()

    return (
        True,
        "Email OTP verified successfully."
    )


@app.route("/")
def home():
    return render_template(
        "index.html"
    )


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():
    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == USERNAME
            and
            password == PASSWORD
        ):
            session["admin_user"] = username

            return redirect(
                url_for("admin")
            )

        return "Invalid Login"

    return render_template(
        "login.html"
    )


@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():
    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        mobile = request.form.get(
            "mobile",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        ).strip()

        village = request.form.get(
            "village",
            ""
        ).strip()

        mandal = request.form.get(
            "mandal",
            ""
        ).strip()

        district = request.form.get(
            "district",
            ""
        ).strip()

        if (
            not name
            or
            not mobile
            or
            not email
            or
            not password
        ):
            return (
                "Name, mobile number, email and password are required."
            )

        if (
            not mobile.isdigit()
            or
            len(mobile) != 10
        ):
            return (
                "Please enter a valid 10-digit mobile number."
            )

        if (
            "@"
            not in email
            or
            "."
            not in email.split("@")[-1]
        ):
            return (
                "Please enter a valid email address."
            )

        if len(password) < 6:
            return (
                "Password must contain at least 6 characters."
            )

        hashed_password = generate_password_hash(
            password
        )

        conn = get_db()

        existing_mobile = conn.execute("""
            SELECT *
            FROM users
            WHERE mobile = ?
        """, (
            mobile,
        )).fetchone()

        existing_email = conn.execute("""
            SELECT *
            FROM users
            WHERE LOWER(email) = ?
        """, (
            email,
        )).fetchone()

        if (
            existing_email
            and
            (
                not existing_mobile
                or
                existing_email["id"]
                !=
                existing_mobile["id"]
            )
        ):
            conn.close()

            return (
                "Email address is already registered."
            )

        if existing_mobile:

            if (
                existing_mobile["email_verified"]
                == 1
                or
                existing_mobile["mobile_verified"]
                == 1
            ):
                conn.close()

                return (
                    "Mobile number is already registered. Please use User Login."
                )

            user_id = existing_mobile["id"]

            conn.execute("""
                UPDATE users
                SET
                    name = ?,
                    email = ?,
                    password = ?,
                    village = ?,
                    mandal = ?,
                    district = ?,
                    email_verified = 0,
                    mobile_verified = 0,
                    otp_hash = NULL,
                    otp_expires_at = NULL,
                    otp_attempts = 0,
                    email_otp_hash = NULL,
                    email_otp_expires_at = NULL,
                    email_otp_attempts = 0
                WHERE id = ?
            """, (
                name,
                email,
                hashed_password,
                village,
                mandal,
                district,
                user_id
            ))

        else:

            try:
                cursor = conn.execute("""
                    INSERT INTO users
                    (
                        name,
                        mobile,
                        email,
                        password,
                        village,
                        mandal,
                        district,
                        email_verified,
                        mobile_verified
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                """, (
                    name,
                    mobile,
                    email,
                    hashed_password,
                    village,
                    mandal,
                    district
                ))

                user_id = cursor.lastrowid

            except sqlite3.IntegrityError:
                conn.close()

                return (
                    "Unable to create the account."
                )

        conn.commit()
        conn.close()

        demo_otp = create_demo_otp_for_user(
            user_id
        )

        email_sent, email_message = (
            create_email_otp_for_user(
                user_id,
                email
            )
        )

        session[
            "pending_verification_user_id"
        ] = user_id

        session["demo_otp"] = demo_otp

        session[
            "verification_email"
        ] = email

        session[
            "email_otp_sent"
        ] = email_sent

        session[
            "email_otp_message"
        ] = email_message

        return redirect(
            url_for("verify_otp")
        )

    return render_template(
        "register.html"
    )


@app.route(
    "/verify_otp",
    methods=["GET", "POST"]
)
def verify_otp():

    user_id = session.get(
        "pending_verification_user_id"
    )

    if not user_id:
        return redirect(
            url_for("register")
        )

    message = None

    if request.method == "POST":

        entered_otp = request.form.get(
            "otp",
            ""
        ).strip()

        if (
            not entered_otp.isdigit()
            or
            len(entered_otp) != 6
        ):
            message = (
                "Please enter a valid 6-digit OTP."
            )

        else:

            demo_success, demo_message = (
                verify_demo_otp(
                    user_id,
                    entered_otp
                )
            )

            email_success, email_message = (
                verify_email_otp(
                    user_id,
                    entered_otp
                )
            )

            if (
                demo_success
                or
                email_success
            ):

                conn = get_db()

                user = conn.execute("""
                    SELECT
                        id,
                        name,
                        mobile,
                        email,
                        email_verified,
                        mobile_verified
                    FROM users
                    WHERE id = ?
                """, (
                    user_id,
                )).fetchone()

                conn.close()

                if user:

                    session["user_id"] = (
                        user["id"]
                    )

                    session["user_name"] = (
                        user["name"]
                    )

                    session["user_mobile"] = (
                        user["mobile"]
                    )

                    session["user_email"] = (
                        user["email"]
                    )

                    session.pop(
                        "pending_verification_user_id",
                        None
                    )

                    session.pop(
                        "demo_otp",
                        None
                    )

                    session.pop(
                        "verification_email",
                        None
                    )

                    session.pop(
                        "email_otp_sent",
                        None
                    )

                    session.pop(
                        "email_otp_message",
                        None
                    )

                    return redirect(
                        url_for("home")
                    )

            message = (
                "Invalid or expired OTP."
            )

    return render_template(
        "verify_otp.html",
        demo_otp=session.get(
            "demo_otp"
        ),
        verification_email=session.get(
            "verification_email"
        ),
        email_otp_sent=session.get(
            "email_otp_sent",
            False
        ),
        email_otp_message=session.get(
            "email_otp_message"
        ),
        message=message
    )


@app.route(
    "/resend_otp"
)
def resend_otp():

    user_id = session.get(
        "pending_verification_user_id"
    )

    if not user_id:
        return redirect(
            url_for("register")
        )

    conn = get_db()

    user = conn.execute("""
        SELECT
            email
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    conn.close()

    if not user:
        return redirect(
            url_for("register")
        )

    demo_otp = create_demo_otp_for_user(
        user_id
    )

    email_sent, email_message = (
        create_email_otp_for_user(
            user_id,
            user["email"]
        )
    )

    session["demo_otp"] = demo_otp

    session["verification_email"] = (
        user["email"]
    )

    session["email_otp_sent"] = (
        email_sent
    )

    session["email_otp_message"] = (
        email_message
    )

    return redirect(
        url_for("verify_otp")
    )


@app.route(
    "/user_login",
    methods=["GET", "POST"]
)
def user_login():

    if request.method == "POST":

        mobile = request.form.get(
            "mobile",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        conn = get_db()

        user = conn.execute("""
            SELECT
                id,
                name,
                mobile,
                email,
                password,
                email_verified,
                mobile_verified
            FROM users
            WHERE mobile = ?
        """, (
            mobile,
        )).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            if (
                user["email_verified"] != 1
                and
                user["mobile_verified"] != 1
            ):

                demo_otp = (
                    create_demo_otp_for_user(
                        user["id"]
                    )
                )

                email_sent, email_message = (
                    create_email_otp_for_user(
                        user["id"],
                        user["email"]
                    )
                )

                session[
                    "pending_verification_user_id"
                ] = user["id"]

                session["demo_otp"] = (
                    demo_otp
                )

                session[
                    "verification_email"
                ] = user["email"]

                session[
                    "email_otp_sent"
                ] = email_sent

                session[
                    "email_otp_message"
                ] = email_message

                return redirect(
                    url_for("verify_otp")
                )

            session["user_id"] = (
                user["id"]
            )

            session["user_name"] = (
                user["name"]
            )

            session["user_mobile"] = (
                user["mobile"]
            )

            session["user_email"] = (
                user["email"]
            )

            return redirect(
                url_for("home")
            )

        return (
            "Invalid mobile number or password."
        )

    return render_template(
        "user_login.html"
    )


@app.route(
    "/user_logout"
)
def user_logout():

    session.pop(
        "user_id",
        None
    )

    session.pop(
        "user_name",
        None
    )

    session.pop(
        "user_mobile",
        None
    )

    session.pop(
        "user_email",
        None
    )

    return redirect(
        url_for("home")
    )


@app.route(
    "/logout"
)
def logout():

    session.pop(
        "admin_user",
        None
    )

    return redirect(
        url_for("home")
    )


@app.route(
    "/voice_complaint"
)
def voice_complaint():

    if "user_id" not in session:
        return redirect(
            url_for("user_login")
        )

    return render_template(
        "voice_complaint.html",
        complaint_submitted=False
    )


@app.route(
    "/report",
    methods=["GET", "POST"]
)
def report():

    if "user_id" not in session:
        return redirect(
            url_for("user_login")
        )

    if request.method == "POST":

        product_id = request.form.get(
            "product_id",
            ""
        ).strip()

        product_type = request.form.get(
            "product_type",
            ""
        ).strip()

        product = request.form.get(
            "product",
            ""
        ).strip()

        company = request.form.get(
            "company",
            ""
        ).strip()

        batch_no = request.form.get(
            "batch_no",
            ""
        ).strip()

        dealer = request.form.get(
            "dealer",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        ai_risk, ai_issue, ai_reason = (
            analyze_complaint(
                description
            )
        )

        validation_status, validation_reason, validation_method = (
            validate_product(
                product_id,
                product_type,
                product,
                company,
                batch_no
            )
        )

        conn = get_db()

        cursor = conn.execute("""
            INSERT INTO complaints
            (
                product_id,
                product_type,
                product,
                company,
                batch_no,
                dealer,
                description,
                ai_risk,
                ai_issue,
                ai_reason,
                status,
                user_id,
                validation_status,
                validation_reason,
                validation_method
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            product_type,
            product,
            company,
            batch_no,
            dealer,
            description,
            ai_risk,
            ai_issue,
            ai_reason,
            "Pending",
            session["user_id"],
            validation_status,
            validation_reason,
            validation_method
        ))

        complaint_id = cursor.lastrowid

        conn.commit()
        conn.close()

        research_result = None

        try:
            research_result = research_product(
                product_id,
                product_type,
                product,
                company,
                batch_no
            )

            research_result["complaint_id"] = (
                complaint_id
            )

            save_research_result(
                research_result
            )

        except Exception as error:
            print(
                "AI research error:",
                error
            )

        return render_template(
            "report.html",
            complaint_submitted=True,
            complaint_id=complaint_id,
            ai_risk=ai_risk,
            ai_issue=ai_issue,
            ai_reason=ai_reason,
            validation_status=validation_status,
            validation_reason=validation_reason,
            validation_method=validation_method,
            research_result=research_result
        )

    return render_template(
        "report.html"
    )


@app.route(
    "/my_complaints"
)
def my_complaints():

    if "user_id" not in session:
        return redirect(
            url_for("user_login")
        )

    conn = get_db()

    complaints = conn.execute("""
        SELECT
            id,
            product_id,
            product_type,
            product,
            company,
            batch_no,
            dealer,
            description,
            ai_risk,
            ai_issue,
            ai_reason,
            validation_status,
            validation_reason,
            validation_method,
            status
        FROM complaints
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "my_complaints.html",
        complaints=complaints
    )


@app.route(
    "/verify",
    methods=["GET", "POST"]
)
def verify():

    product = None
    searched = False

    if request.method == "POST":

        product_id = request.form.get(
            "product_id",
            ""
        ).strip()

        searched = True

        conn = get_db()

        product = conn.execute("""
            SELECT
                product_id,
                product_type,
                product_name,
                company,
                batch_no,
                status
            FROM products
            WHERE product_id = ?
        """, (
            product_id,
        )).fetchone()

        conn.close()

    return render_template(
        "verify.html",
        product=product,
        searched=searched
    )


@app.route(
    "/add_product",
    methods=["GET", "POST"]
)
def add_product():

    if "admin_user" not in session:
        return redirect(
            url_for("login")
        )

    registered_product = None
    qr_filename = None
    verification_url = None

    if request.method == "POST":

        product_id = request.form.get(
            "product_id",
            ""
        ).strip()

        product_type = request.form.get(
            "product_type",
            ""
        ).strip()

        product_name = request.form.get(
            "product_name",
            ""
        ).strip()

        company = request.form.get(
            "company",
            ""
        ).strip()

        batch_no = request.form.get(
            "batch_no",
            ""
        ).strip()

        status = request.form.get(
            "status",
            ""
        ).strip()

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO products
                (
                    product_id,
                    product_type,
                    product_name,
                    company,
                    batch_no,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                product_id,
                product_type,
                product_name,
                company,
                batch_no,
                status
            ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return (
                "Product ID already exists."
            )

        row = conn.execute("""
            SELECT
                product_id,
                product_type,
                product_name,
                company,
                batch_no,
                status
            FROM products
            WHERE product_id = ?
        """, (
            product_id,
        )).fetchone()

        conn.close()

        if row:

            registered_product = {
                "product_id": row["product_id"],
                "product_type": row["product_type"],
                "product_name": row["product_name"],
                "company": row["company"],
                "batch_no": row["batch_no"],
                "status": row["status"]
            }

        try:

            import qrcode

            verification_url = url_for(
                "verify_product",
                product_id=product_id,
                _external=True
            )

            qr_directory = os.path.join(
                "static",
                "qr_codes"
            )

            os.makedirs(
                qr_directory,
                exist_ok=True
            )

            qr_filename = (
                product_id.replace(
                    " ",
                    "_"
                )
                +
                ".png"
            )

            qr_path = os.path.join(
                qr_directory,
                qr_filename
            )

            qr = qrcode.make(
                verification_url
            )

            qr.save(
                qr_path
            )

        except Exception as error:

            print(
                "QR generation error:",
                error
            )

            qr_filename = None

    return render_template(
        "add_product.html",
        registered_product=registered_product,
        qr_filename=qr_filename,
        verification_url=verification_url
    )


@app.route(
    "/verify_product/<product_id>"
)
def verify_product(product_id):

    conn = get_db()

    product = conn.execute("""
        SELECT
            product_id,
            product_type,
            product_name,
            company,
            batch_no,
            status
        FROM products
        WHERE product_id = ?
    """, (
        product_id,
    )).fetchone()

    conn.close()

    return render_template(
        "verify.html",
        product=product,
        searched=True
    )


@app.route(
    "/admin"
)
def admin():

    if "admin_user" not in session:
        return redirect(
            url_for("login")
        )

    search = request.args.get(
        "search",
        ""
    ).strip()

    status_filter = request.args.get(
        "status",
        ""
    ).strip()

    conn = get_db()

    total = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
    """).fetchone()[0]

    pending = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Pending'
    """).fetchone()[0]

    under_review = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Under Review'
    """).fetchone()[0]

    verified = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Verified'
    """).fetchone()[0]

    rejected = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Rejected'
    """).fetchone()[0]

    recent = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE id > (
            SELECT
                COALESCE(
                    MAX(id),
                    0
                ) - 5
            FROM complaints
        )
    """).fetchone()[0]

    query = """
        SELECT
            complaints.id,
            complaints.product_type,
            complaints.product,
            complaints.dealer,
            complaints.description,
            complaints.ai_risk,
            complaints.ai_issue,
            complaints.ai_reason,
            complaints.status,
            complaints.user_id,
            complaints.product_id,
            complaints.company,
            complaints.batch_no,
            complaints.validation_status,
            complaints.validation_reason,
            complaints.validation_method,
            complaints.validation_notes,
            complaints.validated_by,
            complaints.validated_at,
            users.name AS user_name,
            users.mobile AS user_mobile,
            users.email AS user_email
        FROM complaints
        LEFT JOIN users
        ON complaints.user_id = users.id
        WHERE 1 = 1
    """

    parameters = []

    if search:

        query += """
            AND (
                complaints.product LIKE ?
                OR complaints.dealer LIKE ?
                OR complaints.product_type LIKE ?
                OR complaints.description LIKE ?
                OR complaints.product_id LIKE ?
                OR complaints.company LIKE ?
                OR complaints.batch_no LIKE ?
                OR users.name LIKE ?
                OR users.mobile LIKE ?
                OR users.email LIKE ?
            )
        """

        search_value = (
            "%"
            +
            search
            +
            "%"
        )

        parameters.extend([
            search_value,
            search_value,
            search_value,
            search_value,
            search_value,
            search_value,
            search_value,
            search_value,
            search_value,
            search_value
        ])

    if status_filter:

        query += """
            AND complaints.status = ?
        """

        parameters.append(
            status_filter
        )

    query += """
        ORDER BY complaints.id DESC
    """

    complaints = conn.execute(
        query,
        parameters
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        complaints=complaints,
        total=total,
        recent=recent,
        pending=pending,
        under_review=under_review,
        verified=verified,
        rejected=rejected,
        search=search,
        status_filter=status_filter
    )


@app.route(
    "/update_status/<int:id>",
    methods=["POST"]
)
def update_status(id):

    if "admin_user" not in session:
        return redirect(
            url_for("login")
        )

    new_status = request.form.get(
        "status",
        "Pending"
    ).strip()

    allowed_statuses = [
        "Pending",
        "Under Review",
        "Verified",
        "Rejected"
    ]

    if new_status not in allowed_statuses:
        new_status = "Pending"

    conn = get_db()

    conn.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
    """, (
        new_status,
        id
    ))

    conn.commit()
    conn.close()

    return redirect(
        request.referrer
        or
        url_for("admin")
    )


@app.route(
    "/delete/<int:id>"
)
def delete(id):

    if "admin_user" not in session:
        return redirect(
            url_for("login")
        )

    conn = get_db()

    conn.execute("""
        DELETE FROM complaints
        WHERE id = ?
    """, (
        id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )