from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_register():
    response = client.post(
        "/auth/register",
        json={
            "email": "test2@example.com",
            "password": "test123"
        }
    )
    assert response.status_code in [200, 201, 400]


def test_login_invalid():
    response = client.post(
        "/auth/login",
        json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code in [401, 422]


def test_get_products():
    response = client.get("/products")
    assert response.status_code == 200


def test_get_product_not_found():
    response = client.get("/products/999999")
    assert response.status_code == 404


def test_cart_requires_login():
    response = client.get("/cart")
    assert response.status_code in [401, 403]


def test_orders_requires_login():
    response = client.get("/orders")
    assert response.status_code in [401, 403]


def test_register_invalid_email():
    response = client.post(
        "/auth/register",
        json={
            "email": "invalid-email",
            "password": "test123"
        }
    )
    assert response.status_code == 422


def test_products_pagination():
    response = client.get("/products?page=1&limit=10")
    assert response.status_code == 200