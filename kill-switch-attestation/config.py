"""
config.py — FR-14: Single source of truth for all operational parameters.

Every parameter has exactly one named environment variable with a sensible default.
"""

import os
import secrets





IAM_FAILURE_PROB: float = float(os.getenv("KS_IAM_FAILURE_PROB", "0.15"))
OP_INTERVAL: float = float(os.getenv("KS_OP_INTERVAL", "1.5"))
EXP_CYCLES: int = int(os.getenv("KS_EXP_CYCLES", "40"))

NET_DELAY_MIN: int = int(os.getenv("KS_NET_DELAY_MIN", "50"))
NET_DELAY_MAX: int = int(os.getenv("KS_NET_DELAY_MAX", "200"))
IAM_DELAY_MULT: float = float(os.getenv("KS_IAM_DELAY_MULT", "2.0"))

SCHED_FIXED: int = int(os.getenv("KS_SCHED_FIXED", "60"))
SCHED_RAND_MIN: int = int(os.getenv("KS_SCHED_RAND_MIN", "30"))
SCHED_RAND_MAX: int = int(os.getenv("KS_SCHED_RAND_MAX", "120"))

REVOKE_RETRIES: int = int(os.getenv("KS_REVOKE_RETRIES", "2"))
REVOKE_FAILURE_PROB: float = float(os.getenv("KS_REVOKE_FAILURE_PROB", "0.0"))

OP_DURATION_MIN: int = int(os.getenv("KS_OP_DURATION_MIN", "100"))
OP_DURATION_MAX: int = int(os.getenv("KS_OP_DURATION_MAX", "3000"))





DATABASE_URL: str = os.getenv(
    "KS_DATABASE_URL", "sqlite+aiosqlite:///./killswitch.db"
)
AUTH_SECRET: str = os.getenv("KS_AUTH_SECRET", secrets.token_hex(32))
KEYS_DIR: str = os.getenv("KS_KEYS_DIR", "./keys/")






ADMIN_USERNAME: str = os.getenv("KS_ADMIN_USERNAME", "admin")

ADMIN_PASSWORD_PLAINTEXT_DEFAULT: str = "admin"
ADMIN_PASSWORD_HASH_ENV: str = os.getenv("KS_ADMIN_PASSWORD_HASH", "")
