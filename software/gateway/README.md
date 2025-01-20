## Installation

**Set up virtual environment and install dependencies:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Perform type checks:**

```bash
bash scripts/run_mypy.sh
```

## TODOS

- execute version check on startup via thingsboard shared attributes
