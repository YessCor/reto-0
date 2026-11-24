import ast
import secrets
import sqlite3
from pathlib import Path

import pytest

from app import create_app


def csrf_token(client):
    response = client.get("/register")
    assert response.status_code == 200
    with client.session_transaction() as session:
        return session["csrf_token"]


def register(client, username):
    response = client.post(
        "/register",
        data={
            "csrf_token": csrf_token(client),
            "username": username,
            "password": "unaclave123",
        },
    )
    assert response.status_code == 302


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_receta_ajena_no_se_altera_y_su_dueno_puede_administrarla(
    tmp_path, action
):
    suffix = secrets.randbelow(1_000_000)
    owner_name = f"usuarioA_{suffix}"
    other_name = f"usuarioB_{suffix}"
    original_title = f"Receta_{suffix}"
    database = tmp_path / "test.sqlite3"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(database),
        }
    )
    owner = app.test_client()
    other_user = app.test_client()
    register(owner, owner_name)
    owner.post(
        "/recipes/new",
        data={
            "csrf_token": csrf_token(owner),
            "title": original_title,
            "description": "Descripcion original",
            "ingredients": "Ingrediente ficticio",
        },
    )

    with sqlite3.connect(database) as connection:
        recipe_id = connection.execute(
            "SELECT id FROM recipes WHERE title = ?", (original_title,)
        ).fetchone()[0]

    register(other_user, other_name)
    attack_data = {
        "csrf_token": csrf_token(other_user),
        "title": "Titulo alterado",
        "description": "Descripcion alterada",
    }
    response = other_user.post(
        f"/recipes/{recipe_id}/{action}", data=attack_data
    )
    assert response.status_code == 404

    with sqlite3.connect(database) as connection:
        current_recipe = connection.execute(
            "SELECT title FROM recipes WHERE id = ?", (recipe_id,)
        ).fetchone()
    assert current_recipe == (original_title,)

    owner_data = {
        "csrf_token": csrf_token(owner),
        "title": "Titulo autorizado",
        "description": "Descripcion autorizada",
    }
    response = owner.post(
        f"/recipes/{recipe_id}/{action}", data=owner_data
    )
    assert response.status_code == 302

    with sqlite3.connect(database) as connection:
        current_recipe = connection.execute(
            "SELECT title FROM recipes WHERE id = ?", (recipe_id,)
        ).fetchone()
    if action == "edit":
        assert current_recipe == ("Titulo autorizado",)
    else:
        assert current_recipe is None


def test_responsabilidades_de_aplicacion_estan_separadas(tmp_path):
    suffix = secrets.randbelow(1_000_000)
    database = tmp_path / f"datos_ficticios_{suffix}.sqlite3"
    create_app({"TESTING": True, "DATABASE": str(database)})
    username = f"usuario_ficticio_{suffix}"
    recipe_title = f"receta_ficticia_{suffix}"

    with sqlite3.connect(database) as connection:
        user_id = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, "hash_ficticio"),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO recipes (user_id, title, description, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, recipe_title, "Descripcion ficticia", "2026-01-01T00:00:00+00:00"),
        )
        assert connection.execute(
            "SELECT title FROM recipes WHERE title = ?", (recipe_title,)
        ).fetchone() == (recipe_title,)

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app_module = ast.parse(app_path.read_text(encoding="utf-8"))
    responsibilities = []

    for node in ast.walk(app_module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "route"
                for decorator in node.decorator_list
            ):
                responsibilities.append(f"ruta Flask: {node.name}")
            if node.name in {
                "validate_csrf",
                "has_special_characters",
                "initialize_database",
            }:
                responsibilities.append(f"lógica auxiliar: {node.name}")

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"execute", "executemany", "executescript"}
        ):
            responsibilities.append(f"consulta SQLite: línea {node.lineno}")

    assert not responsibilities, (
        "app.py todavía concentra responsabilidades que deben estar separadas: "
        + ", ".join(responsibilities)
    )