import unittest
from app import app
import json

class TestURLAnalysis(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_legitimate_job_url(self):
        # Test avec une URL légitime
        test_data = {
            'job_url': 'https://careers.google.com/jobs/results/123456789',
            'notes': 'Test for legitimate job posting'
        }
        response = self.app.post('/analyze-url', data=test_data)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue('success' in data)
        self.assertFalse(data.get('is_fraudulent'))

    def test_fraudulent_job_url(self):
        # Test avec une URL suspecte
        test_data = {
            'job_url': 'http://fake-jobs-scam.com/job123',
            'notes': 'Test for fraudulent job posting'
        }
        response = self.app.post('/analyze-url', data=test_data)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue('success' in data)
        self.assertTrue(data.get('is_fraudulent'))

    def test_invalid_url(self):
        # Test avec une URL invalide
        test_data = {
            'job_url': 'not-a-valid-url',
            'notes': 'Test with invalid URL'
        }
        response = self.app.post('/analyze-url', data=test_data)
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main()
