from app import app

cliente = app.test_client()


def test_pagina_principal_responde():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200