from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

from translations import TRANSLATIONS


app = Flask(__name__)

app.secret_key = "secret123"

USERNAME = "admin"
PASSWORD = "1234"

DATABASE = "complaints.db"


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

        "user_id": "INTEGER"

    }

    for column, definition in columns_to_add.items():

        try:

            cursor.execute(
                f"ALTER TABLE complaints ADD COLUMN {column} {definition}"
            )

        except sqlite3.OperationalError:

            pass


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            product_id TEXT UNIQUE NOT NULL,

            product_name TEXT NOT NULL,

            company TEXT NOT NULL,

            batch_no TEXT NOT NULL,

            status TEXT NOT NULL

        )
    """)


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


    cursor.execute("""
        UPDATE complaints

        SET status = 'Pending'

        WHERE status IS NULL
           OR status = ''
    """)


    default_products = [

        (
            'FS001',
            'Paddy Seeds',
            'ABC Seeds',
            'B101',
            'Genuine'
        ),

        (
            'FS002',
            'Groundnut Seeds',
            'Green Agro',
            'B202',
            'Genuine'
        ),

        (
            'FERT001',
            'Urea Fertilizer',
            'Agro India',
            'U301',
            'Genuine'
        )

    ]


    cursor.executemany("""
        INSERT OR IGNORE INTO products
        (
            product_id,
            product_name,
            company,
            batch_no,
            status
        )
        VALUES (?, ?, ?, ?, ?)
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

        "logged_in_user": session.get("user_name"),

        "is_user_logged_in": "user_id" in session,

        "is_admin_logged_in": "admin_user" in session

    }


@app.route("/set_language/<language>")
def set_language(language):

    if language in TRANSLATIONS:

        session["language"] = language

    return redirect(
        request.referrer or
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
            and password == PASSWORD
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


        if not name or not mobile or not password:

            return "Name, mobile number and password are required."


        if not mobile.isdigit() or len(mobile) != 10:

            return "Please enter a valid 10-digit mobile number."


        hashed_password = generate_password_hash(
            password
        )


        conn = get_db()


        try:

            conn.execute("""
                INSERT INTO users
                (
                    name,
                    mobile,
                    password,
                    village,
                    mandal,
                    district
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (

                name,

                mobile,

                hashed_password,

                village,

                mandal,

                district

            ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return "Mobile number already registered."

        conn.close()


        return redirect(
            url_for("user_login")
        )


    return render_template(
        "register.html"
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

                password,

                village,

                mandal,

                district

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

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["user_mobile"] = user["mobile"]

            return redirect(
                url_for("home")
            )


        return "Invalid mobile number or password."


    return render_template(
        "user_login.html"
    )


@app.route("/user_logout")
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

    return redirect(
        url_for("home")
    )


@app.route("/logout")
def logout():

    session.pop(
        "admin_user",
        None
    )

    return redirect(
        url_for("home")
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

        product_type = request.form.get(
            "product_type",
            ""
        ).strip()

        product = request.form.get(
            "product",
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


        ai_risk, ai_issue, ai_reason = analyze_complaint(
            description
        )


        conn = get_db()


        cursor = conn.execute("""
            INSERT INTO complaints
            (
                product_type,
                product,
                dealer,
                description,
                ai_risk,
                ai_issue,
                ai_reason,
                status,
                user_id
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        """, (

            product_type,

            product,

            dealer,

            description,

            ai_risk,

            ai_issue,

            ai_reason,

            "Pending",

            session["user_id"]

        ))


        complaint_id = cursor.lastrowid


        conn.commit()

        conn.close()


        return render_template(

            "report.html",

            complaint_submitted=True,

            complaint_id=complaint_id,

            ai_risk=ai_risk,

            ai_issue=ai_issue

        )


    return render_template(
        "report.html"
    )


@app.route("/my_complaints")
def my_complaints():

    if "user_id" not in session:

        return redirect(
            url_for("user_login")
        )


    conn = get_db()


    complaints = conn.execute("""
        SELECT

            id,

            product_type,

            product,

            dealer,

            description,

            ai_risk,

            ai_issue,

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
                    product_name,
                    company,
                    batch_no,
                    status
                )

                VALUES (?, ?, ?, ?, ?)

            """, (

                product_id,

                product_name,

                company,

                batch_no,

                status

            ))


            conn.commit()


        except sqlite3.IntegrityError:

            conn.close()

            return "Product ID already exists."


        row = conn.execute("""
            SELECT

                product_id,

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

                + ".png"

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


@app.route("/admin")
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
                COALESCE(MAX(id), 0) - 5

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

            users.name AS user_name,

            users.mobile AS user_mobile

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

                OR users.name LIKE ?

                OR users.mobile LIKE ?

            )

        """


        search_value = "%" + search + "%"


        parameters.extend([

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

        request.referrer or
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
    
    