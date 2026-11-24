import os
import secrets
from pathlib import Path

from flask import Flask

from database import setup_database
from routes import register_routes


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    secret_key_path = instance_path / "secret_key"
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        try:
            secret_key = secret_key_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            secret_key = secrets.token_hex(32)
            try:
                with secret_key_path.open("x", encoding="utf-8") as secret_file:
                    secret_file.write(secret_key)
            except FileExistsError:
                secret_key = secret_key_path.read_text(encoding="utf-8")

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        DATABASE=os.environ.get(
            "DATABASE", str(Path(app.instance_path) / "recipes.sqlite3")
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    )
    if test_config:
        app.config.update(test_config)

    setup_database(app)
    register_routes(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
