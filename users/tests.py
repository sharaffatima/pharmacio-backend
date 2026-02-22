from django.test import TestCase, Client


class HealthEndpointTests(TestCase):
    def test_health_returns_200(self):
        client = Client()
        response = client.get('/health/')
        self.assertEqual(response.status_code, 200)

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status



class AuthApiTests(APITestCase):
    API_PREFIX = "/api"

    def setUp(self):
        User = get_user_model()
        self.user_password = "pass1234"

        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password=self.user_password,
        )

    def test_login_returns_token(self):
        """
        POST /auth/login/ should return an access token for valid credentials.
        """
        url = f"{self.API_PREFIX}/auth/login/"
        payload = {"username": "testuser", "password": self.user_password}

        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertIn("token", res.data)
        self.assertIn("access", res.data["token"])
        self.assertIn("refresh", res.data["token"])

    def test_protected_endpoint_requires_auth_401(self):
        """
        GET /auth/profile/ without token should return 401.
        """
        url = f"{self.API_PREFIX}/auth/profile/"
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoint_with_token_returns_200(self):
        """
        GET /auth/profile/ with token should return 200.
        """
        login_url = f"{self.API_PREFIX}/auth/login/"
        login_payload = {"username": "testuser", "password": self.user_password}

        login_res = self.client.post(login_url, login_payload, format="json")
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

        token = login_res.data["token"]["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        profile_url = f"{self.API_PREFIX}/auth/profile/"
        profile_res = self.client.get(profile_url)

        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)
        self.assertIn("email", profile_res.data)