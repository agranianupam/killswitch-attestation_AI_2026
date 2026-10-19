import pytest
from api.auth import get_password_hash, verify_password
import config

def test_bcrypt_hashing():
    pwd = "my_secure_password"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False

def test_unauthenticated_requests_rejected(client):
    assert client.post("/api/shutdown?strategy=A").status_code == 401
    assert client.post("/api/scheduler/toggle", json={"enabled": False}).status_code == 401

def test_wrong_password_rejected(client):
    res = client.post("/api/auth/login", data={"username": config.ADMIN_USERNAME, "password": "wrong_password"})
    assert res.status_code == 401

def test_correct_login_works(client):
    res = client.post("/api/auth/login", data={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD_PLAINTEXT_DEFAULT})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    token = data["access_token"]

    protected_res = client.post("/api/shutdown/settings", json={"in_flight_leak_prob": 0.25}, headers={"Authorization": f"Bearer {token}"})
    assert protected_res.status_code == 200

    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    after_logout_res = client.post("/api/shutdown/settings", json={"in_flight_leak_prob": 0.25}, headers={"Authorization": f"Bearer {token}"})
    assert after_logout_res.status_code == 401

def test_demo_admin_token_rejected(client):
    res = client.post("/api/shutdown?strategy=A", headers={"Authorization": "Bearer demo-admin-token"})
    assert res.status_code == 401
