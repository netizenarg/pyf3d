#/bin/bash

if [ ! -d "venv" ]; then
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
else
. venv/bin/activate
fi

cd src

python main.py
