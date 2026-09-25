# Verifiable Kill-Switch Attestation System

A self-contained research demo that continuously, independently, and cryptographically proves whether an AI agent's kill switch works across every access channel it holds, including actions already in flight at shutdown.

## Setup

1. Install dependencies:
   ```
   python -m pip install -r requirements.txt
   ```

2. Run tests:
   ```
   python -m pytest tests/ -v --tb=short
   ```

3. Start server:
   ```
   uvicorn main:app --reload
   ```

Open http://localhost:8000 to view the dashboard.
