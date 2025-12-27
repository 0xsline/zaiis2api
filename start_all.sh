#!/bin/bash
python3 browser_server.py > browser.log 2>&1 &
export BROWSER_SERVICE_URL=http://localhost:5005
python3 app.py > app.log 2>&1 &
sleep 5
echo "Services are running in background."
