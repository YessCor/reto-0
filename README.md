# La Mesa

Aplicación web en Python para compartir recetas y encontrar platos por ingrediente. Incluye registro, inicio y cierre de sesión; cualquier visitante puede explorar y buscar recetas, y las personas con cuenta pueden publicar las suyas.

## Requisitos

- Python 3.10 o posterior
- Flask 3.x

## Ejecutar en Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python app.py
```

Abre http://127.0.0.1:5000. La base SQLite se crea automáticamente en `instance\recipes.sqlite3`. Para usar otra ubicación, configura `DATABASE`.

Para un despliegue, define un `SECRET_KEY` persistente y único, desactiva el modo de depuración y sirve la aplicación detrás de HTTPS; establece `COOKIE_SECURE=1` cuando HTTPS esté habilitado.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```
