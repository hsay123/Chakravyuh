#!/usr/bin/env bash
# Trigger a task in the CRS via the mock competition API
# Usage: ./trigger_task.sh [task-name]
#
# This script:
# 1. Clones the example-libpng repo at the right ref
# 2. Clones the oss-fuzz-aixcc tooling at the right ref
# 3. Creates tarballs
# 4. Uploads to the mock competition API
# 5. Sends a control file to trigger the task
set -euo pipefail

MOCK_API="http://127.0.0.1:31323"
TASK_SERVER="http://127.0.0.1:8000"
CRS_KEY_ID="515cc8a0-3019-4c9f-8c1c-72d0b54ae561"
CRS_TOKEN="REDACTED_CRS_TOKEN"
SCRATCH_DIR="$(pwd)/crs_scratch"

TASK_NAME="${1:-lp_delta_01}"

echo "=== Triggering task: $TASK_NAME ==="

# Wait for mock API to be ready
echo "Waiting for mock competition API..."
for i in $(seq 1 30); do
    if curl -sf "${MOCK_API}/v1/ping/" > /dev/null 2>&1; then
        echo "Mock API ready."
        break
    fi
    sleep 2
done

# Wait for task-server to be ready
echo "Waiting for task-server..."
for i in $(seq 1 30); do
    if curl -sf -u "${CRS_KEY_ID}:${CRS_TOKEN}" "${TASK_SERVER}/status/" > /dev/null 2>&1; then
        echo "Task-server ready."
        break
    fi
    sleep 2
done

# For lp_delta_01: example-libpng with a known vulnerable commit
REPO_URL="https://${SCANTRON_GITHUB_PAT}@github.com/aixcc-finals/example-libpng.git"
BASE_REF="5bf8da2d7953974e5dfbd778429c3affd461f51a"
HEAD_REF="challenges/lp-delta-01"
FUZZ_TOOLING_URL="https://${SCANTRON_GITHUB_PAT}@github.com/aixcc-finals/oss-fuzz-aixcc.git"
FUZZ_TOOLING_REF="challenge-state/lp-delta-01"
PROJECT_NAME="libpng"
DURATION=7200

echo "Cloning challenge repo..."
rm -rf "${SCRATCH_DIR}/example-libpng"
HTTPS_URL="${REPO_URL}"
git clone --depth=1 "${HTTPS_URL}" "${SCRATCH_DIR}/example-libpng" 2>&1 || {
    echo "Trying without auth..."
    git clone --depth=1 "https://github.com/aixcc-finals/example-libpng.git" "${SCRATCH_DIR}/example-libpng" 2>&1
}
cd "${SCRATCH_DIR}/example-libpng"
git fetch --depth=100 origin "${HEAD_REF}" 2>/dev/null || git fetch --depth=100 origin "${BASE_REF}" 2>/dev/null || true
git checkout "${HEAD_REF}" 2>/dev/null || git checkout "${BASE_REF}" 2>/dev/null || true
cd ..

echo "Cloning fuzz tooling..."
rm -rf "${SCRATCH_DIR}/oss-fuzz-aixcc"
HTTPS_FUZZ_URL="${FUZZ_TOOLING_URL}"
git clone --depth=1 "${HTTPS_FUZZ_URL}" "${SCRATCH_DIR}/oss-fuzz-aixcc" 2>&1 || {
    echo "Trying without auth..."
    git clone --depth=1 "https://github.com/aixcc-finals/oss-fuzz-aixcc.git" "${SCRATCH_DIR}/oss-fuzz-aixcc" 2>&1 || true
}
cd "${SCRATCH_DIR}/oss-fuzz-aixcc"
git fetch --depth=1 origin "${FUZZ_TOOLING_REF}" 2>/dev/null || true
git checkout "${FUZZ_TOOLING_REF}" 2>/dev/null || true
cd ..

echo "Creating repo tarball..."
cd "${SCRATCH_DIR}/example-libpng"
REPO_HASH=$(sha256sum .git/HEAD 2>/dev/null | cut -d' ' -f1 || echo "$(date +%s)")
cd "${SCRATCH_DIR}"
tar czf "/tmp/repo-${REPO_HASH}.tar.gz" -C example-libpng .

echo "Creating fuzz tooling tarball..."
cd "${SCRATCH_DIR}/oss-fuzz-aixcc"
TOOLING_HASH=$(sha256sum .git/HEAD 2>/dev/null | cut -d' ' -f1 || echo "$(date +%s)")
cd "${SCRATCH_DIR}"
tar czf "/tmp/tooling-${TOOLING_HASH}.tar.gz" -C oss-fuzz-aixcc .

echo "Uploading repo tarball to mock API..."
REPO_UPLOAD=$(curl -sf -X POST "${MOCK_API}/upload-tarball/" -F "file=@/tmp/repo-${REPO_HASH}.tar.gz" 2>&1) && \
    echo "Repo uploaded: ${REPO_UPLOAD}" || echo "Repo upload response: ${REPO_UPLOAD}"

echo "Uploading tooling tarball to mock API..."
TOOLING_UPLOAD=$(curl -sf -X POST "${MOCK_API}/upload-tarball/" -F "file=@/tmp/tooling-${TOOLING_HASH}.tar.gz" 2>&1) && \
    echo "Tooling uploaded: ${TOOLING_UPLOAD}" || echo "Tooling upload response: ${TOOLING_UPLOAD}"

echo "Creating and uploading control file..."
TASK_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
MESSAGE_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
NOW_MS=$(python3 -c "import time; print(int(time.time() * 1000))")
DEADLINE_MS=$(python3 -c "import time; print(int((time.time() + ${DURATION}) * 1000))")

cat > /tmp/control_file.json << EOF
[
  {
    "id": "${TASK_ID}",
    "type": "delta",
    "deadline": "$(python3 -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) + timedelta(seconds=${DURATION})).isoformat())")",
    "source": [
      {
        "url": "${REPO_HASH}",
        "type": "repo",
        "sha256": "${REPO_HASH}"
      },
      {
        "url": "${TOOLING_HASH}",
        "type": "fuzz-tooling",
        "sha256": "${TOOLING_HASH}"
      }
    ],
    "round_id": "trapnet-demo",
    "created_at": "$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")",
    "updated_at": "$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")",
    "focus": "src/",
    "project_name": "${PROJECT_NAME}",
    "commit": "${HEAD_REF}",
    "harnesses_included": true
  }
]
EOF

echo "Sending control file to mock API..."
curl -sf -X POST "${MOCK_API}/control-file/" -F "file=@/tmp/control_file.json" && \
    echo "Control file sent successfully!" || echo "Failed to send control file"

echo ""
echo "=== Task triggered ==="
echo "Task ID: ${TASK_ID}"
echo "Monitor with: kubectl logs -f or docker compose -f compose-trapnet.yaml logs -f scheduler"
echo ""
