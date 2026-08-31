from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

# ============================================================
# TRANSLATIONS
# ============================================================

from translations import TRANSLATIONS


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = "secret123"

USERNAME = "admin"
PASSWORD = "1234"

DATABASE = "complaints.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()


    # ========================================================
    # COMPLAINTS TABLE
    # ========================================================

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

            status TEXT DEFAULT 'Pending'

        )
    """)


    # ========================================================
    # ADD MISSING COLUMNS TO OLD DATABASE
    # ========================================================

    columns_to_add = {

        "product_type": "TEXT",

        "ai_risk": "TEXT",

        "ai_issue": "TEXT",

        "ai_reason": "TEXT",

        "status": "TEXT DEFAULT 'Pending'"

    }


    for column, definition in columns_to_add.items():

        try:

            cursor.execute(
                f"ALTER TABLE complaints ADD COLUMN {column} {definition}"
            )

        except sqlite3.OperationalError:

            pass


    # ========================================================
    # PRODUCTS TABLE
    # ========================================================

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


    # ========================================================
    # FIX OLD NULL STATUS VALUES
    # ========================================================

    cursor.execute("""
        UPDATE complaints

        SET status = 'Pending'

        WHERE status IS NULL
           OR status = ''
    """)


    conn.commit()

    conn.close()


# ============================================================
# LANGUAGE SUPPORT
# ============================================================

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

        "languages": TRANSLATIONS.keys()

    }


# ============================================================
# CHANGE LANGUAGE
# ============================================================

@app.route("/set_language/<language>")
def set_language(language):

    if language in TRANSLATIONS:

        session["language"] = language


    return redirect(
        request.referrer or
        url_for("home")
    )


# ============================================================
# AI COMPLAINT ANALYSIS
# ============================================================

def analyze_complaint(description):

    text = description.lower()


    # ========================================================
    # HIGH RISK
    # ========================================================

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


    # ========================================================
    # GERMINATION
    # ========================================================

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


    # ========================================================
    # PACKAGING / LABEL
    # ========================================================

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


    # ========================================================
    # FERTILIZER QUALITY
    # ========================================================

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


    # ========================================================
    # GENERAL PRODUCT QUALITY
    # ========================================================

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


    # ========================================================
    # DEALER / SELLER
    # ========================================================

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


    # ========================================================
    # LOW RISK
    # ========================================================

    return (

        "Low Risk",

        "General Complaint",

        "No major risk-related issue was detected from the complaint description."

    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# LOGIN
# ============================================================

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

            session["user"] = username

            return redirect(
                url_for("admin")
            )


        return "Invalid Login"


    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.pop(
        "user",
        None
    )


    return redirect(
        url_for("home")
    )


# ============================================================
# REPORT PRODUCT / COMPLAINT
# ============================================================

@app.route(
    "/report",
    methods=["GET", "POST"]
)
def report():

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


        # ====================================================
        # AI ANALYSIS
        # ====================================================

        ai_risk, ai_issue, ai_reason = analyze_complaint(
            description
        )


        # ====================================================
        # SAVE COMPLAINT
        # ====================================================

        conn = get_db()


        conn.execute("""
            INSERT INTO complaints
            (
                product_type,
                product,
                dealer,
                description,
                ai_risk,
                ai_issue,
                ai_reason,
                status
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            product_type,

            product,

            dealer,

            description,

            ai_risk,

            ai_issue,

            ai_reason,

            "Pending"

        ))


        conn.commit()

        conn.close()


        return redirect(
            url_for("home")
        )


    return render_template(
        "report.html"
    )


# ============================================================
# VERIFY PRODUCT
# ============================================================

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


# ============================================================
# ADD REGISTERED PRODUCT + QR
# ============================================================

@app.route(
    "/add_product",
    methods=["GET", "POST"]
)
def add_product():

    # ========================================================
    # LOGIN REQUIRED
    # ========================================================

    if "user" not in session:

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


        # ====================================================
        # SAVE PRODUCT
        # ====================================================

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


        # ====================================================
        # GET REGISTERED PRODUCT
        # ====================================================

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


        # ====================================================
        # QR CODE
        # ====================================================

        try:

            import qrcode


            # ------------------------------------------------
            # Verification URL
            # ------------------------------------------------

            verification_url = url_for(

                "verify_product",

                product_id=product_id,

                _external=True

            )


            # ------------------------------------------------
            # QR DIRECTORY
            # ------------------------------------------------

            qr_directory = os.path.join(

                "static",

                "qr_codes"

            )


            os.makedirs(

                qr_directory,

                exist_ok=True

            )


            # ------------------------------------------------
            # QR FILE
            # ------------------------------------------------

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


            # ------------------------------------------------
            # CREATE QR
            # ------------------------------------------------

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


# ============================================================
# QR VERIFICATION PAGE
# ============================================================

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


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
def admin():

    # ========================================================
    # LOGIN CHECK
    # ========================================================

    if "user" not in session:

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


    # ========================================================
    # TOTAL COMPLAINTS
    # ========================================================

    total = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
    """).fetchone()[0]


    # ========================================================
    # PENDING COMPLAINTS
    # ========================================================

    pending = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Pending'
    """).fetchone()[0]


    # ========================================================
    # UNDER REVIEW
    # ========================================================

    under_review = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Under Review'
    """).fetchone()[0]


    # ========================================================
    # VERIFIED
    # ========================================================

    verified = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Verified'
    """).fetchone()[0]


    # ========================================================
    # REJECTED
    # ========================================================

    rejected = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Rejected'
    """).fetchone()[0]


    # ========================================================
    # RECENT
    # ========================================================

    recent = conn.execute("""
        SELECT COUNT(*)

        FROM complaints

        WHERE id > (

            SELECT
                COALESCE(MAX(id), 0) - 5

            FROM complaints

        )
    """).fetchone()[0]


    # ========================================================
    # SEARCH + STATUS FILTER
    # ========================================================

    query = """
        SELECT

            id,

            product_type,

            product,

            dealer,

            description,

            ai_risk,

            ai_issue,

            ai_reason,

            status

        FROM complaints

        WHERE 1 = 1
    """


    parameters = []


    # ========================================================
    # SEARCH
    # ========================================================

    if search:

        query += """

            AND (

                product LIKE ?

                OR dealer LIKE ?

                OR product_type LIKE ?

                OR description LIKE ?

            )

        """


        search_value = "%" + search + "%"


        parameters.extend([

            search_value,

            search_value,

            search_value,

            search_value

        ])


    # ========================================================
    # STATUS FILTER
    # ========================================================

    if status_filter:

        query += """

            AND status = ?

        """


        parameters.append(
            status_filter
        )


    # ========================================================
    # ORDER
    # ========================================================

    query += """

        ORDER BY id DESC

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


# ============================================================
# UPDATE COMPLAINT STATUS
# ============================================================

@app.route(
    "/update_status/<int:id>",
    methods=["POST"]
)
def update_status(id):

    # ========================================================
    # LOGIN REQUIRED
    # ========================================================

    if "user" not in session:

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


    # ========================================================
    # UPDATE DATABASE
    # ========================================================

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


# ============================================================
# DELETE COMPLAINT
# ============================================================

@app.route(
    "/delete/<int:id>"
)
def delete(id):

    # ========================================================
    # LOGIN REQUIRED
    # ========================================================

    if "user" not in session:

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


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    init_db()


    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )