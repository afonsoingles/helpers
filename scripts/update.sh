#!/bin/bash

set -a
source .env
set +a

cd "$HOST_DIR" || exit 1

systemctl --user stop "$HOST_SERVICE_NAME"
git pull

source venv/bin/activate

pip install -r requirements.txt

systemctl --user start "$HOST_SERVICE_NAME"
deactivate
echo "Update completed successfully."