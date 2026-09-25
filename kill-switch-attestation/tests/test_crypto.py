"""
tests/test_crypto.py
"""

import pytest
from services.crypto_service import ensure_keys_exist, load_public_key, load_private_key, sign_test_result, verify_signature
from schemas.contracts import TestResult
from datetime import datetime

def test_crypto_signature_verification():
    ensure_keys_exist()
    
    tr = TestResult(
        timestamp=datetime.utcnow(),
        revocation_latency_ms=100.5,
        leaked_channels=[],
        in_flight_failures=0
    )
    
    payload_json = tr.model_dump_json(indent=None)
    sig = sign_test_result(tr)
    
    pub_key = load_public_key()
    
    assert verify_signature(payload_json, sig, pub_key) is True
    
    
    tampered_payload = payload_json.replace("100.5", "100.6")
    assert verify_signature(tampered_payload, sig, pub_key) is False

def test_verify_with_private_key_raises():
    ensure_keys_exist()
    priv_key = load_private_key()
    
    with pytest.raises(TypeError):
        verify_signature("{}", b"dummy", priv_key)
