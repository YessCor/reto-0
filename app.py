import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE
);
"""


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get(
            "DATABASE", str(Path(app.instance_path) / "recipes.sqlite3")
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    initialize_database(app)

    @app.before_request
    def open_database():
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    @app.teardown_appcontext
    def close_database(_error=None):
        database = g.pop("db", None)
        if database is not None:
            database.close()

    @app.context_processor
    def inject_template_values():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"current_user": session.get("username"), "csrf_token": session["csrf_token"]}

    @app.route("/")
    def index():
        query = request.args.get("q", "").strip()[:100]
        if query:
            pattern = f"%{escape_like(query)}%"
            recipes = g.db.execute(
                """
                SELECT DISTINCT recipes.id, recipes.title, recipes.description,
                       recipes.created_at, users.username
                FROM recipes
                JOIN users ON users.id = recipes.user_id
                JOIN ingredients ON ingredients.recipe_id = recipes.id
                WHERE ingredients.name LIKE ? ESCAPE '\\'
                ORDER BY recipes.created_at DESC
                """,
                (pattern,),
            ).fetchall()
        else:
            recipes = g.db.execute(
                """
                SELECT recipes.id, recipes.title, recipes.description,
                       recipes.created_at, users.username
                FROM recipes
                JOIN users ON users.id = recipes.user_id
                ORDER BY recipes.created_at DESC
                """
            ).fetchall()

        recipe_cards = []
        for recipe in recipes:
            ingredients = g.db.execute(
                "SELECT name FROM ingredients WHERE recipe_id = ? ORDER BY id",
                (recipe["id"],),
            ).fetchall()
            recipe_cards.append(
                {"recipe": recipe, "ingredients": [item["name"] for item in ingredients]}
            )
        return render_template("index.html", recipes=recipe_cards, query=query)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            validate_csrf()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
                flash("El usuario debe tener entre 3 y 30 caracteres (letras, números o _).")
            elif len(password) < 8:
                flash("La contraseña debe tener al menos 8 caracteres.")
            else:
                try:
                    cursor = g.db.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash(password)),
                    )
                    g.db.commit()
                except sqlite3.IntegrityError:
                    flash("Ese nombre de usuario ya está registrado.")
                else:
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    session["username"] = username
                    flash("¡Tu cuenta está lista! Ya puedes publicar recetas.")
                    return redirect(url_for("index"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            validate_csrf()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = g.db.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Usuario o contraseña incorrectos.")
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                flash(f"¡Qué bueno verte, {user['username']}!")
                return redirect(url_for("index"))
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        validate_csrf()
        session.clear()
        flash("Has cerrado sesión.")
        return redirect(url_for("index"))

    @app.route("/recipes/new", methods=["GET", "POST"])
    def new_recipe():
        if "user_id" not in session:
            flash("Inicia sesión para publicar una receta.")
            return redirect(url_for("login"))

        if request.method == "POST":
            validate_csrf()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            raw_ingredients = request.form.get("ingredients", "")
            ingredients = [
                ingredient.strip()
                for ingredient in re.split(r"[\n,]+", raw_ingredients)
                if ingredient.strip()
            ]

            if not title or len(title) > 100:
                flash("El título es obligatorio y no puede superar 100 caracteres.")
            elif len(description) > 2000:
                flash("La descripción no puede superar 2000 caracteres.")
            elif not ingredients or len(ingredients) > 50:
                flash("Añade entre 1 y 50 ingredientes.")
            elif any(len(ingredient) > 100 for ingredient in ingredients):
                flash("Cada ingrediente debe tener como máximo 100 caracteres.")
            else:
                cursor = g.db.execute(
                    """
                    INSERT INTO recipes (user_id, title, description, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        session["user_id"],
                        title,
                        description,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )
                g.db.executemany(
                    "INSERT INTO ingredients (recipe_id, name) VALUES (?, ?)",
                    [(cursor.lastrowid, ingredient) for ingredient in ingredients],
                )
                g.db.commit()
                flash("¡Receta publicada!")
                return redirect(url_for("index"))

        return render_template("new_recipe.html")

    @app.errorhandler(400)
    def bad_request(_error):
        flash("La solicitud no es válida. Vuelve a intentarlo.")
        return redirect(request.referrer or url_for("index"))

    def validate_csrf():
        submitted = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(submitted, expected):
            abort(400)

    return app


def escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def initialize_database(app):
    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as database:
        database.execute("PRAGMA foreign_keys = ON")
        database.executescript(SCHEMA)


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
