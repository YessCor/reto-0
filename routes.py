import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timezone

from flask import (
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


def register_routes(app):
    @app.context_processor
    def inject_template_values():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {
            "current_user": session.get("username"),
            "csrf_token": session["csrf_token"],
        }

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
                {
                    "recipe": recipe,
                    "ingredients": [item["name"] for item in ingredients],
                }
            )
        return render_template("index.html", recipes=recipe_cards, query=query)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            validate_csrf()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
                flash(
                    "El usuario debe tener entre 3 y 30 caracteres "
                    "(letras, números o _)."
                )
            elif len(password) < 8:
                flash("La contraseña debe tener al menos 8 caracteres.")
            elif len(password) > 128:
                flash("La contraseña no puede superar 128 caracteres.")
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
            if user is None or not check_password_hash(
                user["password_hash"], password
            ):
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
            elif any(
                has_special_characters(value)
                for value in (title, description, *ingredients)
            ):
                flash("Los campos de la receta contienen caracteres no permitidos.")
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
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),  # noqa: UP017
                    ),
                )
                g.db.executemany(
                    "INSERT INTO ingredients (recipe_id, name) VALUES (?, ?)",
                    [
                        (cursor.lastrowid, ingredient)
                        for ingredient in ingredients
                    ],
                )
                g.db.commit()
                flash("¡Receta publicada!")
                return redirect(url_for("index"))

        return render_template("new_recipe.html")

    @app.post("/recipes/<int:recipe_id>/edit")
    def edit_recipe(recipe_id):
        validate_csrf()
        user_id = session.get("user_id")
        recipe = g.db.execute(
            "SELECT id FROM recipes WHERE id = ? AND user_id = ?",
            (recipe_id, user_id),
        ).fetchone()
        if recipe is None:
            abort(404)

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title or len(title) > 100:
            flash("El título es obligatorio y no puede superar 100 caracteres.")
        elif len(description) > 2000:
            flash("La descripción no puede superar 2000 caracteres.")
        elif has_special_characters(title) or has_special_characters(description):
            flash("Los campos de la receta contienen caracteres no permitidos.")
        else:
            cursor = g.db.execute(
                """
                UPDATE recipes SET title = ?, description = ?
                WHERE id = ? AND user_id = ?
                """,
                (title, description, recipe_id, user_id),
            )
            if cursor.rowcount == 0:
                abort(404)
            g.db.commit()
            flash("¡Receta actualizada!")
        return redirect(url_for("index"))

    @app.post("/recipes/<int:recipe_id>/delete")
    def delete_recipe(recipe_id):
        validate_csrf()
        cursor = g.db.execute(
            "DELETE FROM recipes WHERE id = ? AND user_id = ?",
            (recipe_id, session.get("user_id")),
        )
        if cursor.rowcount == 0:
            abort(404)
        g.db.commit()
        flash("Receta eliminada.")
        return redirect(url_for("index"))

    @app.errorhandler(400)
    def bad_request(_error):
        return "La solicitud no es válida. Vuelve a intentarlo.", 400


def validate_csrf():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(submitted, expected):
        abort(400)


def escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def has_special_characters(value):
    return re.search(r"[^\w\s.,;:()¿¡-]", value) is not None