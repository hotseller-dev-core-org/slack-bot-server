#!/bin/bash

cd "$(dirname "$0")/.."  # script → slack-bot-server 디렉토리로 이동

source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload