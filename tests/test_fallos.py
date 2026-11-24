import secrets

from app import create_app


def test_csrf_invalido_devuelve_error_claro_sin_traza(tmp_path):
    suffix = secrets.randbelow(1_000_000)
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / f"datos_ficticios_{suffix}.sqlite3"),
        }
    )
    client = app.test_client()

    response = client.post(
        "/register",
        data={
            "csrf_token": f"token_invalido_{suffix}",
            "username": f"usuario_ficticio_{suffix}",
            "password": "ClaveFicticia123",
        },
    )

    body = response.get_data(as_text=True)
    assert "Traceback" not in body
    assert response.status_code == 400
