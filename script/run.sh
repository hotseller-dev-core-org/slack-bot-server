#!/bin/bash

# package_abs_path=$(dirname $0)  # 현재 'run' 파일의 절대 경로

# pushd $package_abs_path  # 파일이 존재하는 경로로 push

# export PYTHONPATH=$PYTHONPATH:`pwd`/moneycoon  # 파이썬 환경변수 등록

# . env/bin/activate  # 파이썬 env 세팅

# uvicorn web_app.main:app --reload --port 8000 --host 127.0.0.1
# #uvicorn web_app.main:app --reload --port 8000 --host 0.0.0.0

# deactivate

# popd

source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload