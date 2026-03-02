import os
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db


ENERGY_MULTIPLIERS = {
    "High": 1.0,
    "Medium": 0.6,
    "Low": 0.3,
    "Burnout": 0.05,
}
VALID_ENERGIES = set(ENERGY_MULTIPLIERS.keys())


def scaled_goal(base_goal: int, energy: str) -> int:
    mult = ENERGY_MULTIPLIERS.get(energy, 0.6)
    return max(1, round(base_goal * mult))


def normalize_energy(raw_energy: str | None) -> str:
    energy = (raw_energy or "").strip()
    return energy if energy in VALID_ENERGIES else "Medium"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")

    @app.teardown_appcontext
    def _close_db(exception):
        close_db(exception)

    # ROUTE 1/5: Login (kept at "/")
    @app.route("/", methods=["GET", "POST"])
    def login():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            db = get_db()
            user = db.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if not user or not check_password_hash(user["password_hash"], password):
                return render_template("login.html", error="Invalid username or password.")

            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    # ROUTE 2/5: Signup
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            if len(username) < 3:
                return render_template("signup.html", error="Username must be at least 3 characters.")
            if len(password) < 6:
                return render_template("signup.html", error="Password must be at least 6 characters.")

            db = get_db()
            existing = db.execute(
                "SELECT 1 FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if existing:
                return render_template("signup.html", error="That username is already taken.")

            db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            db.commit()
            return redirect(url_for("login"))

        return render_template("signup.html")

    # ROUTE 3/5: Logout
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    def require_login():
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return None

    # ROUTE 4/5: Dashboard (protected) + submit habit + submit daily entry
    @app.route("/dashboard", methods=["GET", "POST"])
    def dashboard():
        gate = require_login()
        if gate:
            return gate

        user_id = session["user_id"]
        db = get_db()

        if request.method == "POST":
            form_type = request.form.get("type")
            selected_energy = normalize_energy(request.form.get("energy"))

            # Submit habit
            if form_type == "habit":
                title = (request.form.get("title") or "").strip()
                base_goal_raw = request.form.get("base_goal") or "0"
                unit = (request.form.get("unit") or "units").strip() or "units"
                unit = unit[:16]

                try:
                    base_goal = int(base_goal_raw)
                except ValueError:
                    base_goal = 0

                if not title:
                    return render_template("dashboard.html", error="Habit title is required.")
                if base_goal < 1:
                    return render_template("dashboard.html", error="Base goal must be at least 1.")

                db.execute(
                    "INSERT INTO habits (user_id, title, base_goal, unit) VALUES (?, ?, ?, ?)",
                    (user_id, title, base_goal, unit),
                )
                db.commit()
                return redirect(url_for("dashboard", energy=selected_energy))

            # Submit daily entry
            if form_type == "entry":
                habit_id_raw = request.form.get("habit_id") or ""
                energy = selected_energy
                completed_raw = request.form.get("completed") or "0"

                try:
                    habit_id = int(habit_id_raw)
                except ValueError:
                    habit_id = -1

                try:
                    completed = int(completed_raw)
                except ValueError:
                    completed = 0

                habit = db.execute(
                    "SELECT id, base_goal FROM habits WHERE id = ? AND user_id = ? AND is_active = 1",
                    (habit_id, user_id),
                ).fetchone()
                if not habit:
                    return render_template("dashboard.html", error="Pick a valid habit first.")

                s_goal = scaled_goal(int(habit["base_goal"]), energy)
                if completed < 0:
                    completed = 0

                effort_ratio = completed / s_goal if s_goal else 0.0
                score_delta = float(effort_ratio)
                today = date.today().isoformat()

                try:
                    db.execute(
                        """
                        INSERT INTO entries (user_id, habit_id, entry_date, energy, scaled_goal, completed, score_delta)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id, habit_id, entry_date) DO UPDATE SET
                            energy=excluded.energy,
                            scaled_goal=excluded.scaled_goal,
                            completed=excluded.completed,
                            score_delta=excluded.score_delta
                        """,
                        (user_id, habit_id, today, energy, s_goal, completed, score_delta),
                    )
                    db.commit()
                except Exception:
                    return render_template("dashboard.html", error="Could not save entry. Try again.")

                return redirect(url_for("dashboard", energy=energy))

        selected_energy = normalize_energy(request.args.get("energy"))

        habits = db.execute(
            """
            SELECT id, title, base_goal, unit
            FROM habits
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

        latest_entry = db.execute(
            """
            SELECT e.entry_date, e.energy, e.scaled_goal, e.completed, e.score_delta, h.title, h.unit
            FROM entries e
            JOIN habits h ON h.id = e.habit_id
            WHERE e.user_id = ?
            ORDER BY e.entry_date DESC, e.created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        latest_entry_display_date = None
        if latest_entry is not None:
            try:
                d = datetime.fromisoformat(latest_entry["entry_date"]).date()
                latest_entry_display_date = d.strftime("%d/%m/%Y")
            except ValueError:
                latest_entry_display_date = latest_entry["entry_date"]

        return render_template(
            "dashboard.html",
            username=session.get("username"),
            habits=habits,
            latest_entry=latest_entry,
            latest_entry_display_date=latest_entry_display_date,
            selected_energy=selected_energy,
        )

    # ROUTE 5/5: Stats for 7-day chart (protected)
    @app.route("/api/stats")
    def api_stats():
        gate = require_login()
        if gate:
            return gate

        user_id = session["user_id"]
        db = get_db()

        today = date.today()
        start = (today - timedelta(days=6)).isoformat()

        rows = db.execute(
            """
            SELECT entry_date,
                   SUM(score_delta) AS score,
                   AVG(completed * 1.0 / scaled_goal) AS avg_effort_ratio
            FROM entries
            WHERE user_id = ? AND entry_date >= ?
            GROUP BY entry_date
            ORDER BY entry_date ASC
            """,
            (user_id, start),
        ).fetchall()

        by_day = {r["entry_date"]: r for r in rows}
        labels = []
        scores = []
        avg_ratios = []

        for i in range(6, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            try:
                pretty = datetime.fromisoformat(d).strftime("%d/%m/%Y")
            except ValueError:
                pretty = d
            labels.append(pretty)
            r = by_day.get(d)
            scores.append(float(r["score"]) if r and r["score"] is not None else 0.0)
            avg_ratios.append(float(r["avg_effort_ratio"]) if r and r["avg_effort_ratio"] is not None else 0.0)

        total_score = db.execute(
            "SELECT COALESCE(SUM(score_delta), 0) AS total FROM entries WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]

        # Monthly trend: last 30 days, grouped by energy
        month_start = (today - timedelta(days=29)).isoformat()
        month_rows = db.execute(
            """
            SELECT energy, SUM(score_delta) AS score
            FROM entries
            WHERE user_id = ? AND entry_date >= ?
            GROUP BY energy
            """,
            (user_id, month_start),
        ).fetchall()

        month_by_energy = {r["energy"]: r for r in month_rows}
        energy_order = ["High", "Medium", "Low", "Burnout"]
        month_labels = energy_order
        month_scores = [
            float(month_by_energy[e]["score"]) if e in month_by_energy and month_by_energy[e]["score"] is not None else 0.0
            for e in energy_order
        ]

        month_start_pretty = datetime.fromisoformat(month_start).strftime("%d/%m/%Y")
        month_end_pretty = today.strftime("%d/%m/%Y")

        return jsonify(
            {
                "labels": labels,
                "scores": scores,
                "avg_effort_ratio": avg_ratios,
                "total_score": float(total_score),
                "monthly": {
                    "labels": month_labels,
                    "scores": month_scores,
                    "start_date": month_start_pretty,
                    "end_date": month_end_pretty,
                },
            }
        )

    return app


app = create_app()
init_db(app)


if __name__ == "__main__":
    app.run(debug=True)
