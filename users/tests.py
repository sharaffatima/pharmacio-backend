from django.test import TestCase, Client

# Create your tests here.
class HealthEndpointTests(TestCase):
    def test_health_returns_200(self):
        client = Client()
        response = client.get('/health/')
        self.assertEqual(response.status_code, 200)