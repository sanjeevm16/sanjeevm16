#!/bin/bash
# Production runner for the AI Companion App
source ./set_env.sh
./.venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
