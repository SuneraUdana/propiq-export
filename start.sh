#!/bin/bash
mkdir -p data
chmod 777 data
uvicorn app:app --host 0.0.0.0 --port $PORT
