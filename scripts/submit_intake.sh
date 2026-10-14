#!/usr/bin/env bash
# Submit a Transcript file as a new Intake and print the API response.
#
# Usage: scripts/submit_intake.sh "<client name>" <transcript-file>
#
# Environment:
#   INTAKE_API_KEY  required, sent as the X-API-Key header
#   API_URL         optional, defaults to http://127.0.0.1:8000
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 \"<client name>\" <transcript-file>" >&2
  exit 2
fi

client_name=$1
transcript_file=$2
api_url=${API_URL:-http://127.0.0.1:8000}

if [[ -z "${INTAKE_API_KEY:-}" ]]; then
  echo "error: INTAKE_API_KEY is not set" >&2
  exit 2
fi
if [[ ! -r "$transcript_file" ]]; then
  echo "error: cannot read transcript file: $transcript_file" >&2
  exit 2
fi

# Build the JSON body with python3 so quotes and newlines in the Transcript are escaped.
body=$(python3 -c '
import json, sys
print(json.dumps({"client_name": sys.argv[1], "transcript": open(sys.argv[2]).read()}))
' "$client_name" "$transcript_file")

# The key goes through a curl config (process substitution), so it never shows up
# in `ps`; the body is read from stdin.
response=$(curl --silent --show-error \
  --config <(printf 'header = "X-API-Key: %s"\n' "$INTAKE_API_KEY") \
  --write-out '\n%{http_code}' \
  --header 'Content-Type: application/json' \
  --data @- \
  "$api_url/intakes" <<<"$body")

http_code=${response##*$'\n'}
payload=${response%$'\n'*}

echo "HTTP $http_code" >&2
echo "$payload" | python3 -m json.tool 2>/dev/null || echo "$payload"

[[ $http_code == 200 || $http_code == 202 ]]
