import tempfile
import unittest
from pathlib import Path

from app import create_app


class RecipeAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": str(Path(self.temp_dir.name) / "test.sqlite3"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf_token(self):
        response = self.client.get("/register")
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def register(self, username="cocinera"):
        token = self.csrf_token()
        return self.client.post(
            "/register",
            data={"csrf_token": token, "username": username, "password": "unaclave123"},
            follow_redirects=True,
        )

    def test_registration_login_and_recipe_publication(self):
        response = self.register()
        self.assertIn("Tu cuenta está lista".encode(), response.data)

        token = self.csrf_token()
        response = self.client.post(
            "/recipes/new",
            data={
                "csrf_token": token,
                "title": "Ensalada fresca",
                "description": "Ideal para el verano",
                "ingredients": "Tomate\nPepino, Aceite de oliva",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Ensalada fresca", response.data)
        self.assertIn(b"Pepino", response.data)

        self.client.post("/logout", data={"csrf_token": self.csrf_token()})
        token = self.csrf_token()
        response = self.client.post(
            "/login",
            data={"csrf_token": token, "username": "cocinera", "password": "unaclave123"},
            follow_redirects=True,
        )
        self.assertIn(b"Ensalada fresca", response.data)

    def test_search_matches_ingredient_case_insensitively(self):
        self.register()
        self.client.post(
            "/recipes/new",
            data={
                "csrf_token": self.csrf_token(),
                "title": "Tarta de chocolate",
                "ingredients": "Chocolate\nHarina",
            },
        )

        response = self.client.get("/?q=choco")
        self.assertIn(b"Tarta de chocolate", response.data)
        self.assertNotIn(b"No hay recetas", response.data)

        response = self.client.get("/?q=limón")
        self.assertNotIn(b"Tarta de chocolate", response.data)

    def test_invalid_csrf_and_weak_password_are_rejected(self):
        response = self.client.post(
            "/register",
            data={"csrf_token": "invalid", "username": "cocinera", "password": "unaclave123"},
        )
        self.assertEqual(response.status_code, 302)

        token = self.csrf_token()
        response = self.client.post(
            "/register",
            data={"csrf_token": token, "username": "cocinera", "password": "short"},
        )
        self.assertIn(b"al menos 8", response.data)


if __name__ == "__main__":
    unittest.main()
