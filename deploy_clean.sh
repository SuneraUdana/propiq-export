#!/bin/bash
set -e
echo "╔══════════════════════════════════════╗"
echo "║   PropIQ — Clean Deploy to Railway   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Step 1: Apply all file fixes LOCALLY
echo "[1/5] Applying local fixes..."
cp output/app.py ./app.py
echo "      app.py replaced"

# Copy reporter to wherever it exists
if [ -f "propiq/propiq/reporter.py" ]; then
  cp output/propiq_reporter_v3.py propiq/propiq/reporter.py
  echo "      reporter.py -> propiq/propiq/reporter.py"
elif [ -f "propiq/reporter.py" ]; then
  cp output/propiq_reporter_v3.py propiq/reporter.py
  echo "      reporter.py -> propiq/reporter.py"
fi

# Step 2: Copy seed data
echo "[2/5] Adding seed_data.json..."
cp output/seed_data.json ./seed_data.json
echo "      200 records ready"

# Step 3: Write correct Procfile and Dockerfile
echo "[3/5] Writing Procfile + Dockerfile..."
echo 'web: uvicorn app:app --host 0.0.0.0 --port $PORT' > Procfile
cat > Dockerfile << 'DOCKEREOF'
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/propiq/data /app/static
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
DOCKEREOF
echo "      Procfile: web: uvicorn app:app --host 0.0.0.0 --port $PORT"
echo "      Dockerfile: CMD uvicorn app:app port 8000"

# Step 4: Remove fix_files.py from repo so Railway never runs it
echo "[4/5] Removing fix_files.py from repo (should only run locally)..."
rm -f fix_files.py
echo "      Done"

# Step 5: Commit and push
echo "[5/5] Git commit + push..."
git add app.py Procfile Dockerfile seed_data.json
git add propiq/reporter.py 2>/dev/null || git add propiq/propiq/reporter.py 2>/dev/null || true
git rm --cached fix_files.py 2>/dev/null || true
git commit -m "fix: clean deploy — correct uvicorn module, Procfile, no fix_files on Railway"
git push origin main

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║ IMPORTANT: Also check Railway Dashboard!                 ║"
echo "║ Go to: Service → Settings → Start Command               ║"
echo "║ Make sure it is EMPTY or set to:                        ║"
echo "║   uvicorn app:app --host 0.0.0.0 --port $PORT          ║"
echo "╚══════════════════════════════════════════════════════════╝"
