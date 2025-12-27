#!/bin/bash
echo "Updating Database..."
sqlite3 instance/zai2api.db "UPDATE token SET is_active=1, error_count=0 WHERE id=11;"
echo "Triggering API Test..."
curl -s -X POST http://localhost:5002/api/tokens/11/test -H "Authorization: Bearer sk-default-key"
echo "Waiting for browser..."
sleep 10
echo "Fetching Header..."
curl -v -X GET http://localhost:5005/header --max-time 120
