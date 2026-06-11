#!/usr/bin/env bash

if [ "$1" = "--clear-old-logs" ]; then
  rm -rf *.log
fi

if [ ! -d "venv" ]; then
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
else
. venv/bin/activate
fi

cd src

python3 main.py
