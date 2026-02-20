import csv
import os
import sqlite3

from flask import Flask, g, render_template, request

app = Flask(__name__)
DATABASE = os.path.join(app.root_path, "popular_names.db")
CSV_FILE = os.path.join(app.root_path, "nebraska_popular_names.csv")


def get_db():
    """Get a database connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the table and import CSV data if the database doesn't exist."""
    if os.path.exists(DATABASE):
        return

    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS statutes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            statute_number TEXT NOT NULL,
            section_title TEXT,
            popular_name TEXT NOT NULL,
            start_section TEXT,
            end_section TEXT,
            full_text TEXT,
            url TEXT
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_popular_name ON statutes (popular_name)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_statute_number ON statutes (statute_number)"
    )

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db.execute(
                """
                INSERT INTO statutes
                    (statute_number, section_title, popular_name,
                     start_section, end_section, full_text, url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["statute_number"],
                    row["section_title"],
                    row["popular_name"],
                    row["start_section"],
                    row["end_section"],
                    row["full_text_of_naming_clause"],
                    row["url"],
                ),
            )

    db.commit()
    db.close()


@app.route("/")
def home():
    """Home page with search bar."""
    query = request.args.get("q", "").strip()
    results = None

    if query:
        db = get_db()
        results = db.execute(
            """
            SELECT * FROM statutes
            WHERE popular_name LIKE ? OR statute_number LIKE ?
            ORDER BY popular_name
            """,
            (f"%{query}%", f"%{query}%"),
        ).fetchall()

    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM statutes").fetchone()[0]

    # All popular names for the quick-jump dropdown
    all_names = db.execute(
        "SELECT popular_name, url FROM statutes ORDER BY popular_name"
    ).fetchall()

    return render_template(
        "home.html", query=query, results=results, total=total, all_names=all_names
    )


@app.route("/browse")
def browse():
    """Browse all popular names alphabetically."""
    db = get_db()
    statutes = db.execute(
        "SELECT * FROM statutes ORDER BY popular_name, statute_number"
    ).fetchall()

    # Group by first letter for alphabetical navigation
    letters = sorted(set(s["popular_name"][0].upper() for s in statutes if s["popular_name"]))

    # Group by chapter number for chapter view
    by_chapter = db.execute(
        "SELECT * FROM statutes ORDER BY statute_number"
    ).fetchall()

    chapters = {}
    for s in by_chapter:
        chap = s["statute_number"].split("-")[0] if "-" in s["statute_number"] else "Other"
        chapters.setdefault(chap, []).append(s)

    # Sort chapter keys numerically
    sorted_chapters = sorted(chapters.keys(), key=lambda c: (int(c) if c.isdigit() else 9999))

    return render_template(
        "browse.html",
        statutes=statutes,
        letters=letters,
        chapters=chapters,
        sorted_chapters=sorted_chapters,
    )


@app.route("/about")
def about():
    """About page."""
    return render_template("about.html")


# Initialise the database before serving any requests
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
