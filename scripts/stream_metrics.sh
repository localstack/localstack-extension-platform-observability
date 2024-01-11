#!/bin/bash

LOCALSTACK_URL=${1:-'http://localhost:4566'}
OUTPUT_FILE=${2:-'output.log'}

while sleep 1; do
   { curl -s "${LOCALSTACK_URL}/_extension/observability/metrics"; echo; } | tee -a $OUTPUT_FILE
done
