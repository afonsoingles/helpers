#!/bin/bash

set -a
source .env
set +a

cd "$HOST_DIR" || exit 1

git pull

source venv/bin/activate

pip install -r requirements.txt

systemctl --user restart "$HOST_SERVICE_NAME"

