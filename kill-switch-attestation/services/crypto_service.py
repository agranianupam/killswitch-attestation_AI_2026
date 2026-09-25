"""
services/crypto_service.py — FR-8: Ed25519, hash-chain
"""

import os
import uuid
import hashlib
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import config
from schemas.contracts import TestResult
from models.attestation import AttestationEntry

def ensure_keys_exist():
    os.makedirs(config.KEYS_DIR, exist_ok=True)
    priv_path = os.path.join(config.KEYS_DIR, "private_key.pem")
    pub_path = os.path.join(config.KEYS_DIR, "public_key.pem")

    if not os.path.exists(priv_path) or not os.path.exists(pub_path):
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        with open(priv_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(pub_path, "wb") as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))

def load_private_key() -> ed25519.Ed25519PrivateKey:
    ensure_keys_exist()
    with open(os.path.join(config.KEYS_DIR, "private_key.pem"), "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def load_public_key() -> ed25519.Ed25519PublicKey:
    ensure_keys_exist()
    with open(os.path.join(config.KEYS_DIR, "public_key.pem"), "rb") as f:
        return serialization.load_pem_public_key(f.read())

def sign_test_result(result: TestResult) -> bytes:
    private_key = load_private_key()
    payload = result.model_dump_json(indent=None).encode('utf-8')
    return private_key.sign(payload)

def verify_signature(payload_json: str, signature: bytes, public_key) -> bool:
    if isinstance(public_key, ed25519.Ed25519PrivateKey):
        raise TypeError("Cannot verify with a private key")
    
    try:
        public_key.verify(signature, payload_json.encode('utf-8'))
        return True
    except Exception:
        return False

async def append_to_chain(db: AsyncSession, shutdown_event_id: str, payload_json: str, signature_hex: str) -> AttestationEntry:
    
    result = await db.execute(select(AttestationEntry).order_by(desc(AttestationEntry.created_at)).limit(1))
    last_entry = result.scalar_one_or_none()
    
    prev_hash = last_entry.entry_hash if last_entry else "GENESIS"
    
    hasher = hashlib.sha256()
    hasher.update((payload_json + signature_hex + prev_hash).encode('utf-8'))
    entry_hash = hasher.hexdigest()
    
    entry = AttestationEntry(
        id=uuid.uuid4().hex,
        shutdown_event_id=shutdown_event_id,
        payload_json=payload_json,
        signature=signature_hex,
        prev_hash=prev_hash,
        entry_hash=entry_hash
    )
    
    db.add(entry)
    await db.commit()
    return entry

async def verify_chain(db: AsyncSession, public_key) -> dict:
    result = await db.execute(select(AttestationEntry).order_by(AttestationEntry.created_at))
    entries = result.scalars().all()
    
    if not entries:
        return {"valid": True, "entries_checked": 0, "first_failure_index": None}
        
    expected_prev = "GENESIS"
    for i, entry in enumerate(entries):
        
        if entry.prev_hash != expected_prev:
            return {"valid": False, "entries_checked": i, "first_failure_index": i}
            
        
        hasher = hashlib.sha256()
        hasher.update((entry.payload_json + entry.signature + entry.prev_hash).encode('utf-8'))
        computed_hash = hasher.hexdigest()
        if entry.entry_hash != computed_hash:
             return {"valid": False, "entries_checked": i, "first_failure_index": i}
             
        
        if not verify_signature(entry.payload_json, bytes.fromhex(entry.signature), public_key):
             return {"valid": False, "entries_checked": i, "first_failure_index": i}
             
        expected_prev = entry.entry_hash
        
    return {"valid": True, "entries_checked": len(entries), "first_failure_index": None}
