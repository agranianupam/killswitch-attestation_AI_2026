"""
tests/test_auth.py
"""

import pytest
from api.auth import get_password_hash, verify_password

def test_bcrypt_hashing():
    pwd = "my_secure_password"
    hashed = get_password_hash(pwd)
    
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False

def test_unauthenticated_shutdown_rejected(client):
    res = client.post("/api/shutdown?strategy=A")
    assert res.status_code == 401
