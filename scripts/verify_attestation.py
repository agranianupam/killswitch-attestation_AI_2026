import argparse
import hashlib
import json
import os
import re
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

def parse_markdown_report(report_text: str) -> dict:
    sig_match = re.search(r'-\s*\*\*Attestation Signature \(Hex\)\*\*:\s*```(?:\w+)?\s*([a-fA-F0-9]+)\s*```', report_text)
    hash_match = re.search(r'-\s*\*\*Entry Hash \(SHA-256\)\*\*:\s*```(?:\w+)?\s*([a-fA-F0-9]+)\s*```', report_text)
    prev_match = re.search(r'-\s*\*\*Previous Block Hash\*\*:\s*```(?:\w+)?\s*([^\r\n`]+)\s*```', report_text)

    payload_match = re.search(r'## 5\. Canonical Attestation Payload [^\r\n]*\s*```(?:json)?\s*([\s\S]*?)\s*```', report_text)
    if not payload_match:
        payload_match = re.search(r'## 5\. Canonical Attestation Payload\s*```(?:json)?\s*([\s\S]*?)\s*```', report_text)

    if not sig_match or not hash_match or not prev_match or not payload_match:
        raise ValueError("Could not parse all required cryptographic attestation fields from markdown report.")

    return {
        "signature": sig_match.group(1).strip(),
        "entry_hash": hash_match.group(1).strip().lower(),
        "prev_hash": prev_match.group(1).strip(),
        "payload_json": payload_match.group(1).strip()
    }

def verify_single_attestation(payload_json: str, signature_hex: str, prev_hash: str, expected_entry_hash: str, public_key) -> dict:
    results = {
        "hash_valid": False,
        "signature_valid": False,
        "calculated_hash": None,
        "error": None
    }

    try:
        hasher = hashlib.sha256()
        hasher.update((payload_json + signature_hex + prev_hash).encode('utf-8'))
        calculated_hash = hasher.hexdigest().lower()
        results["calculated_hash"] = calculated_hash
        results["hash_valid"] = (calculated_hash == expected_entry_hash.lower())
    except Exception as e:
        results["error"] = f"Hash calculation error: {e}"
        return results

    try:
        sig_bytes = bytes.fromhex(signature_hex)
        public_key.verify(sig_bytes, payload_json.encode('utf-8'))
        results["signature_valid"] = True
    except Exception as e:
        results["signature_valid"] = False
        if not results["error"]:
            results["error"] = f"Signature verification failed: {e}"

    return results

def verify_sqlite_chain(db_path: str, public_key) -> dict:
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, shutdown_event_id, payload_json, signature, prev_hash, entry_hash, created_at FROM attestation_entries ORDER BY created_at ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()

    expected_prev = "GENESIS"
    for i, row in enumerate(rows):
        entry_id, sh_id, payload_json, sig_hex, prev_hash, entry_hash, created_at = row
        if prev_hash != expected_prev:
            return {"valid": False, "entries_checked": i, "first_failure_index": i, "reason": f"Entry {i} ({entry_id}) prev_hash '{prev_hash}' != expected '{expected_prev}'"}

        hasher = hashlib.sha256()
        hasher.update((payload_json + sig_hex + prev_hash).encode('utf-8'))
        computed_hash = hasher.hexdigest()
        if entry_hash.lower() != computed_hash.lower():
            return {"valid": False, "entries_checked": i, "first_failure_index": i, "reason": f"Entry {i} ({entry_id}) entry_hash mismatch. Computed: {computed_hash}, Found: {entry_hash}"}

        try:
            sig_bytes = bytes.fromhex(sig_hex)
            public_key.verify(sig_bytes, payload_json.encode('utf-8'))
        except Exception as e:
            return {"valid": False, "entries_checked": i, "first_failure_index": i, "reason": f"Entry {i} ({entry_id}) signature verification failed: {e}"}

        expected_prev = entry_hash
    return {"valid": True, "entries_checked": len(rows), "first_failure_index": None, "reason": None}

def main():
    parser = argparse.ArgumentParser(description="Independent Ed25519 & SHA-256 Attestation Verifier")
    parser.add_argument("--report", help="Path to exported markdown report (.md)")
    parser.add_argument("--db", help="Path to SQLite database (e.g. killswitch.db) to verify complete chain")
    parser.add_argument("--public-key", default="keys/public_key.pem", help="Path to Ed25519 public key (.pem)")
    parser.add_argument("--payload", help="Raw canonical payload string")
    parser.add_argument("--signature", help="Signature in hex")
    parser.add_argument("--prev-hash", help="Previous entry hash")
    parser.add_argument("--entry-hash", help="Expected entry hash")

    args = parser.parse_args()

    if not os.path.exists(args.public_key):
        print(f"[FAIL] Public key file not found: {args.public_key}", file=sys.stderr)
        sys.exit(2)

    with open(args.public_key, "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())

    if args.db:
        if not os.path.exists(args.db):
            print(f"[FAIL] Database file not found: {args.db}", file=sys.stderr)
            sys.exit(2)
        res = verify_sqlite_chain(args.db, public_key)
        print("=== Complete Attestation Chain Verification ===")
        print(f"Database            : {args.db}")
        print(f"Entries Evaluated   : {res['entries_checked']}")
        print(f"Genesis Root Valid  : {'PASS [OK]' if res['entries_checked'] > 0 else 'N/A (empty)'}")
        print(f"Chain Integrity     : {'PASS [OK]' if res['valid'] else 'FAIL [X]'}")
        if res["valid"]:
            print(f"\nOVERALL STATUS: CHAIN VERIFIED ({res['entries_checked']} sequential blocks cryptographically intact)")
            sys.exit(0)
        else:
            print(f"\nOVERALL STATUS: CHAIN COMPROMISED (Failed at block #{res['first_failure_index']}: {res['reason']})")
            sys.exit(1)

    if args.report:
        with open(args.report, "r", encoding="utf-8") as f:
            content = f.read()
        parsed = parse_markdown_report(content)
        payload = parsed["payload_json"]
        sig = parsed["signature"]
        prev = parsed["prev_hash"]
        entry_hash = parsed["entry_hash"]
    elif args.payload and args.signature and args.prev_hash and args.entry_hash:
        payload = args.payload
        sig = args.signature
        prev = args.prev_hash
        entry_hash = args.entry_hash
    else:
        print("[FAIL] Specify --report <path>, --db <path>, or all four components (--payload, --signature, --prev-hash, --entry-hash).", file=sys.stderr)
        sys.exit(2)

    res = verify_single_attestation(payload, sig, prev, entry_hash, public_key)

    print("=== Cryptographic Attestation Verification Report ===")
    print(f"Previous Block Hash : {prev}")
    print(f"Recorded Entry Hash : {entry_hash}")
    print(f"Calculated Hash     : {res['calculated_hash']}")
    print(f"Hash Match          : {'PASS [OK]' if res['hash_valid'] else 'FAIL [X]'}")
    print(f"Ed25519 Signature   : {'PASS [OK]' if res['signature_valid'] else 'FAIL [X]'}")

    if res["hash_valid"] and res["signature_valid"]:
        print("\nOVERALL STATUS: VERIFIED (Cryptographically sound, tamper-evident proof confirmed)")
        sys.exit(0)
    else:
        print(f"\nOVERALL STATUS: TAMPER DETECTED / VERIFICATION FAILED ({res.get('error')})")
        sys.exit(1)

if __name__ == "__main__":
    main()
