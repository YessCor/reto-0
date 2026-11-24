# AGENTS.md

## Proyecto
La Mesa es una aplicación web para descubrir y compartir recetas, con búsqueda por ingrediente.
Permite explorar recetas sin cuenta y registrarse para publicar recetas propias.

## Stack
- Python 3; Flask para rutas y aplicación web.
- SQLite mediante `sqlite3` para usuarios, recetas e ingredientes.
- Jinja2 para plantillas; Werkzeug para hashes de contraseñas.
- HTML y CSS adaptable para la interfaz.

## Comandos
- Instalar: `python -m pip install -r requirements.txt`
- Ejecutar: `python app.py`
- Pruebas: `python -m pytest -v`
- Estilo: `ruff check .`

## Estructura
- `app.py`: fábrica Flask, rutas, autenticación, validación y acceso a SQLite.
- `requirements.txt`: dependencias Python declaradas (Flask).
- `pytest.ini`: configuración de descubrimiento de pruebas para pytest.
- `README.md`: descripción, configuración y guía de ejecución y despliegue.
- `.gitignore`: archivos y directorios locales excluidos de Git.
- `.venv/`: entorno virtual local, excluido del control de versiones.
- `instance/`: directorio de datos creado al ejecutar; contiene la base SQLite.
- `tests/`: pruebas automatizadas de la aplicación.
- `tests/test_app.py`: pruebas de registro, inicio de sesión, publicación, búsqueda y CSRF.
- `static/`: recursos estáticos del sitio.
- `static/style.css`: estilos y diseño adaptable.
- `templates/`: plantillas HTML renderizadas con Jinja2.
- `templates/base.html`: estructura común, navegación y mensajes.
- `templates/index.html`: búsqueda y listado de recetas.
- `templates/login.html`: formulario de inicio de sesión.
- `templates/new_recipe.html`: formulario para publicar recetas.
- `templates/register.html`: formulario de registro.

## Qué no hacer
- No modificar las pruebas para que pasen.
- No escribir claves en el código.
- No instalar dependencias sin explicar para qué.
- No hacer commit ni push.

## Lecciones aprendidas
