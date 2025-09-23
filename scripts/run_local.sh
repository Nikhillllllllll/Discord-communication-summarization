#!/usr/bin/env bash
set -euo pipefail
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
export PYTHONPATH=src
python -m tradesbot.main

