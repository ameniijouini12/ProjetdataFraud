import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page(client):
    rv = client.get('/')
    assert rv.status_code == 200

def test_job_prediction(client):
    test_data = {
        'title': 'Software Engineer',
        'location': 'New York',
        'department': 'Engineering',
        'profile': 'Senior',
        'req': 'Python, ML',
        'ben': 'Health Insurance',
        'emptype': 'Full-time',
        'exp': '5 years',
        'edu': 'Bachelor',
        'indu': 'Technology',
        'func': 'Development',
        'des': 'Join our team'
    }
    rv = client.post('/submit', data=test_data)
    assert rv.status_code == 200
