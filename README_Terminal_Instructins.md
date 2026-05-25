# DPI Terminal Instructions (WSL)

This guide provides terminal commands for all four services:
1) Forgery Detection
2) Privacy Filter
3) Insurance Policy (pdf2nhcx)
4) Clinical Document (pdf2abdm)

Notes:
- Run these in WSL (Ubuntu) or any bash-compatible shell.
- Windows file paths must be converted to WSL paths using /mnt/c/...
- Each service has its own token. Tokens are not interchangeable.
- Demo tokens are valid for 1 day.

Common setup (required):

```bash
NAME="YOUR_NAME"
EMAIL="you@example.com"
BASE="https://dpi-dev.tanuh.ai"
```

------------------------------------------------------------
## 1) Forgery Detection API (forgensic)

Endpoints used:
- POST /forgensic/api/token
- POST /forgensic/jobs
- GET  /forgensic/jobs/{job_id}
- GET  /forgensic/jobs/{job_id}/results
- GET  /forgensic/jobs/{job_id}/files/{file_name}

Set your input file:
```bash
FILE="/path/to/document.pdf"  # or .jpg/.png/.tiff
OCR="false"
```

Commands:
```bash
# Health check (optional)
curl -s "$BASE/forgensic/health" | python3 -m json.tool

# Get token
TOKEN=$(curl -s -X POST "$BASE/forgensic/api/token" \
	-H "Content-Type: application/json" \
	-d "{\"name\":\"$NAME\",\"email\":\"$EMAIL\"}" \
	| python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
echo "TOKEN_LEN=${#TOKEN}"

# Upload file (creates job)
JOB_ID=$(curl -s -X POST "$BASE/forgensic/jobs" \
	-H "Authorization: Bearer $TOKEN" \
	-F "file=@$FILE" \
	-F "ocr_enabled=$OCR" \
	| python3 -c 'import sys, json; print(json.load(sys.stdin)["job_id"])')
echo "JOB_ID=$JOB_ID"

# Poll status
for i in {1..30}; do
	STATUS_JSON=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/forgensic/jobs/$JOB_ID")
	STATUS=$(python3 -c 'import sys, json; print(json.load(sys.stdin).get("status",""))' <<<"$STATUS_JSON")
	PROGRESS=$(python3 -c 'import sys, json; print(json.load(sys.stdin).get("progress",""))' <<<"$STATUS_JSON")
	echo "status=$STATUS progress=$PROGRESS"
	if [ "$STATUS" = "complete" ] || [ "$STATUS" = "error" ]; then
		break
	fi
	sleep 2
done

# Fetch results
RESULTS_JSON=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/forgensic/jobs/$JOB_ID/results")
echo "$RESULTS_JSON" | python3 -m json.tool

# Download first preview image (optional)
PREVIEW_URL=$(python3 -c 'import sys, json; d=json.load(sys.stdin); pages=d.get("pages",[]); print(pages[0].get("preview_url",""))' <<<"$RESULTS_JSON")
if [ -n "$PREVIEW_URL" ]; then
	curl -s -L -H "Authorization: Bearer $TOKEN" "$BASE$PREVIEW_URL" -o forgensic_preview.png
	echo "Saved forgensic_preview.png"
fi
```

------------------------------------------------------------
## 2) Privacy Filter API

Endpoints used:
- POST /privacy-filter/api/demo-token
- POST /privacy-filter/api/redact
- GET  /privacy-filter/api/files/{kind}/{key}

Set your input file:
```bash
FILE="/path/to/document.pdf"
```

Commands:
```bash
# Health + supported types (optional)
curl -s "$BASE/privacy-filter/api/health" | python3 -m json.tool
curl -s "$BASE/privacy-filter/api/supported-types" | python3 -m json.tool

# Get token
TOKEN=$(curl -s -X POST "$BASE/privacy-filter/api/demo-token" \
	-H "Content-Type: application/json" \
	-d "{\"name\":\"$NAME\",\"email\":\"$EMAIL\"}" \
	| python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
echo "TOKEN_LEN=${#TOKEN}"

# Redact document
RESP=$(curl -s -X POST "$BASE/privacy-filter/api/redact" \
	-H "Authorization: Bearer $TOKEN" \
	-F "file=@$FILE")
echo "$RESP" | python3 -m json.tool

# Download original + redacted files (optional)
ORIG_URL=$(python3 -c 'import sys,json; print(json.load(sys.stdin).get("original_url",""))' <<<"$RESP")
RED_URL=$(python3 -c 'import sys,json; print(json.load(sys.stdin).get("redacted_url",""))' <<<"$RESP")
FILENAME=$(python3 -c 'import sys,json; print(json.load(sys.stdin).get("filename","document"))' <<<"$RESP")
RED_NAME=$(python3 -c 'import os,sys; fn=sys.argv[1]; root,ext=os.path.splitext(fn); print(root+"__redacted"+ext if ext else fn+"__redacted")' "$FILENAME")

if [ -n "$ORIG_URL" ]; then
	curl -s -L -H "Authorization: Bearer $TOKEN" "$BASE$ORIG_URL" -o "$FILENAME"
	echo "Saved $FILENAME"
fi
if [ -n "$RED_URL" ]; then
	curl -s -L -H "Authorization: Bearer $TOKEN" "$BASE$RED_URL" -o "$RED_NAME"
	echo "Saved $RED_NAME"
fi
```

------------------------------------------------------------
## 3) Insurance Policy API (pdf2nhcx)

Endpoints used:
- POST /pdf2nhcx/api/token
- POST /pdf2nhcx/submit
- GET  /pdf2nhcx/task-status/{task_id}
- GET  /pdf2nhcx/task-result/{task_id}

Set your input file:
```bash
FILE="/path/to/insurance_policy.pdf"
```

Commands:
```bash
# Health check (optional)
curl -s "$BASE/pdf2nhcx/health" | python3 -m json.tool

# Get token
TOKEN=$(curl -s -X POST "$BASE/pdf2nhcx/api/token" \
	-H "Content-Type: application/json" \
	-d "{\"name\":\"$NAME\",\"email\":\"$EMAIL\"}" \
	| python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
echo "TOKEN_LEN=${#TOKEN}"

# Submit PDF (async)
TASK_ID=$(curl -s -X POST "$BASE/pdf2nhcx/submit" \
	-H "Authorization: Bearer $TOKEN" \
	-F "file=@$FILE" \
	| python3 -c 'import sys, json; print(json.load(sys.stdin)["task_id"])')
echo "TASK_ID=$TASK_ID"

# Poll status
for i in {1..60}; do
	STATUS_JSON=$(curl -s "$BASE/pdf2nhcx/task-status/$TASK_ID")
	STATUS=$(python3 -c 'import sys, json; print(json.load(sys.stdin).get("status",""))' <<<"$STATUS_JSON")
	echo "status=$STATUS"
	if [ "$STATUS" = "completed" ] || [ "$STATUS" = "error" ]; then
		break
	fi
	sleep 5
done

# Fetch result
RESULT=$(curl -s "$BASE/pdf2nhcx/task-result/$TASK_ID")
echo "$RESULT" | python3 -m json.tool
```

------------------------------------------------------------
## 4) Clinical Document API (pdf2abdm)

Endpoints used:
- POST /pdf2abdm/api/token
- POST /pdf2abdm/submit
- GET  /pdf2abdm/task-status/{task_id}
- GET  /pdf2abdm/task-result/{task_id}

Set your input file:
```bash
FILE="/path/to/clinical_document.pdf"
```

Commands:
```bash
# Health check (optional)
curl -s "$BASE/pdf2abdm/health" | python3 -m json.tool

# Get token
TOKEN=$(curl -s -X POST "$BASE/pdf2abdm/api/token" \
	-H "Content-Type: application/json" \
	-d "{\"name\":\"$NAME\",\"email\":\"$EMAIL\"}" \
	| python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
echo "TOKEN_LEN=${#TOKEN}"

# Submit PDF (async)
TASK_ID=$(curl -s -X POST "$BASE/pdf2abdm/submit" \
	-H "Authorization: Bearer $TOKEN" \
	-F "file=@$FILE" \
	| python3 -c 'import sys, json; print(json.load(sys.stdin)["task_id"])')
echo "TASK_ID=$TASK_ID"

# Poll status
for i in {1..60}; do
	STATUS_JSON=$(curl -s "$BASE/pdf2abdm/task-status/$TASK_ID")
	STATUS=$(python3 -c 'import sys, json; print(json.load(sys.stdin).get("status",""))' <<<"$STATUS_JSON")
	echo "status=$STATUS"
	if [ "$STATUS" = "completed" ] || [ "$STATUS" = "error" ]; then
		break
	fi
	sleep 5
done

# Fetch result
RESULT=$(curl -s "$BASE/pdf2abdm/task-result/$TASK_ID")
echo "$RESULT" | python3 -m json.tool
```
