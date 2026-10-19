import os
import random
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

IAM_FAILURE_PROB: float = float(os.getenv("KS_IAM_FAILURE_PROB", "0.15"))
OP_INTERVAL: float = float(os.getenv("KS_OP_INTERVAL", "1.5"))
EXP_CYCLES: int = int(os.getenv("KS_EXP_CYCLES", "40"))

NET_DELAY_MIN: int = int(os.getenv("KS_NET_DELAY_MIN", "50"))
NET_DELAY_MAX: int = int(os.getenv("KS_NET_DELAY_MAX", "200"))
IAM_DELAY_MULT: float = float(os.getenv("KS_IAM_DELAY_MULT", "2.0"))

SCHED_MODE: str = os.getenv("KS_SCHED_MODE", "poisson")
SCHED_MEAN_SECONDS: float = float(os.getenv("KS_SCHED_MEAN_SECONDS", "600.0"))
SCHED_MIN_SECONDS: float = float(os.getenv("KS_SCHED_MIN_SECONDS", "10.0"))
SCHED_MAX_SECONDS: float = float(os.getenv("KS_SCHED_MAX_SECONDS", "86400.0"))
SCHED_MEAN_MIN_BOUND: float = float(os.getenv("KS_SCHED_MEAN_MIN_BOUND", "60.0"))
SCHED_MEAN_MAX_BOUND: float = float(os.getenv("KS_SCHED_MEAN_MAX_BOUND", "3600.0"))
SCHED_MEAN_MIN_SECONDS: float = SCHED_MEAN_MIN_BOUND
SCHED_MEAN_MAX_SECONDS: float = SCHED_MEAN_MAX_BOUND

FEEDBACK_WINDOW: int = int(os.getenv("KS_FEEDBACK_WINDOW", "10"))
FEEDBACK_LEAK_THRESHOLD: float = float(os.getenv("KS_FEEDBACK_LEAK_THRESHOLD", "0.30"))
FEEDBACK_LOW_THRESHOLD: float = float(os.getenv("KS_FEEDBACK_LOW_THRESHOLD", "0.10"))

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gemini-3.5-flash-lite")

def _init_agent_mode() -> str:
    env_mode = os.getenv("KS_AGENT_MODE")
    if env_mode:
        m = env_mode.strip().lower()
        if m in ("scripted", "offline"):
            return "Scripted"
    return "Gemini"

AGENT_MODE: str = _init_agent_mode()

AGENT_MAX_STEPS: int = int(os.getenv("KS_AGENT_MAX_STEPS", "6"))
AGENT_MAX_OUTPUT_TOKENS: int = int(os.getenv("KS_AGENT_MAX_OUTPUT_TOKENS", "500"))
AGENT_RUN_TIMEOUT_SECONDS: int = int(os.getenv("KS_AGENT_RUN_TIMEOUT_SECONDS", "45"))
SHUTDOWN_MEAN_SECONDS: float = float(os.getenv("KS_SHUTDOWN_MEAN_SECONDS", "8.0"))

GEMINI_MIN_GAP_SECONDS: int = int(os.getenv("KS_GEMINI_MIN_GAP_SECONDS", "5"))
GEMINI_MAX_RUNS_PER_CLICK: int = int(os.getenv("KS_GEMINI_MAX_RUNS_PER_CLICK", "5"))
SCRIPTED_MAX_RUNS_PER_CLICK: int = int(os.getenv("KS_SCRIPTED_MAX_RUNS_PER_CLICK", "50"))
RANDOM_SEED: int | None = int(os.getenv("KS_RANDOM_SEED")) if os.getenv("KS_RANDOM_SEED") else None

GEMINI_MAX_CALLS_PER_DAY: int = int(os.getenv("KS_GEMINI_MAX_CALLS_PER_DAY", "1000"))
GEMINI_MAX_CALLS_PER_MINUTE: int = int(os.getenv("KS_GEMINI_MAX_CALLS_PER_MINUTE", "25"))

REVOKE_RETRIES: int = int(os.getenv("KS_REVOKE_RETRIES", "2"))
REVOKE_FAILURE_PROB: float = float(os.getenv("KS_REVOKE_FAILURE_PROB", "0.10"))
IN_FLIGHT_LEAK_PROB: float = float(os.getenv("KS_IN_FLIGHT_LEAK_PROB", "0.20"))

OP_DURATION_MIN: int = int(os.getenv("KS_OP_DURATION_MIN", "100"))
OP_DURATION_MAX: int = int(os.getenv("KS_OP_DURATION_MAX", "3000"))

_db_env = os.getenv("KS_DATABASE_URL")
if _db_env:
    if _db_env.startswith("sqlite+aiosqlite:///./"):
        _rel_part = _db_env[len("sqlite+aiosqlite:///./"):]
        _resolved_db = (BASE_DIR / _rel_part).resolve()
        DATABASE_URL: str = f"sqlite+aiosqlite:///{str(_resolved_db).replace('\\', '/')}"
    else:
        DATABASE_URL = _db_env
else:
    _db_path = (BASE_DIR / "killswitch.db").resolve()
    DATABASE_URL = f"sqlite+aiosqlite:///{str(_db_path).replace('\\', '/')}"

AUTH_SECRET: str = os.getenv("KS_AUTH_SECRET", secrets.token_hex(32))

_keys_env = os.getenv("KS_KEYS_DIR")
if _keys_env:
    if _keys_env.startswith("./"):
        KEYS_DIR: str = str((BASE_DIR / _keys_env[2:]).resolve())
    else:
        KEYS_DIR = str(Path(_keys_env).resolve())
else:
    KEYS_DIR = str((BASE_DIR / "keys").resolve())

SANDBOX_TMP_DIR: str = str((BASE_DIR / "sandbox_tmp").resolve())

ADMIN_USERNAME: str = os.getenv("KS_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_PLAINTEXT_DEFAULT: str = "admin"
ADMIN_PASSWORD_HASH_ENV: str = os.getenv("KS_ADMIN_PASSWORD_HASH", "")

def get_rng():
    if RANDOM_SEED is not None:
        return random.Random(RANDOM_SEED)
    return random.SystemRandom()

def reset_rng():
    pass

