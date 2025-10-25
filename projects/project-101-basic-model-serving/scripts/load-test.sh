#!/bin/bash

# Load testing script
# This script performs load testing on the API using curl and parallel requests

echo "=========================================="
echo "Model Serving System - Load Test"
echo "=========================================="
echo ""

# Configuration
API_URL=${API_URL:-"http://localhost:8000"}
NUM_REQUESTS=${NUM_REQUESTS:-100}
CONCURRENCY=${CONCURRENCY:-10}
TEST_IMAGE_URL="https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg"

echo "Configuration:"
echo "  API URL: $API_URL"
echo "  Total Requests: $NUM_REQUESTS"
echo "  Concurrency: $CONCURRENCY"
echo ""

# Create test payload
PAYLOAD='{"url": "'$TEST_IMAGE_URL'", "top_k": 5}'

# Function to make a single request
make_request() {
    local start_time=$(date +%s%3N)
    local response=$(curl -s -o /dev/null -w "%{http_code},%{time_total}" -X POST "$API_URL/predict/url" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD")
    local end_time=$(date +%s%3N)

    echo "$response"
}

export -f make_request
export API_URL
export PAYLOAD

echo "Starting load test..."
echo ""

# Run load test
start_time=$(date +%s)

# Use GNU parallel if available, otherwise use xargs
if command -v parallel &> /dev/null; then
    results=$(seq 1 $NUM_REQUESTS | parallel -j $CONCURRENCY make_request)
else
    results=$(seq 1 $NUM_REQUESTS | xargs -P $CONCURRENCY -I {} bash -c 'make_request')
fi

end_time=$(date +%s)
total_time=$((end_time - start_time))

# Parse results
successful=0
failed=0
total_response_time=0

while IFS= read -r line; do
    http_code=$(echo $line | cut -d',' -f1)
    response_time=$(echo $line | cut -d',' -f2)

    if [ "$http_code" = "200" ]; then
        ((successful++))
        total_response_time=$(echo "$total_response_time + $response_time" | bc)
    else
        ((failed++))
    fi
done <<< "$results"

# Calculate statistics
avg_response_time=$(echo "scale=3; $total_response_time / $successful" | bc)
requests_per_sec=$(echo "scale=2; $NUM_REQUESTS / $total_time" | bc)

# Print results
echo "=========================================="
echo "Load Test Results"
echo "=========================================="
echo ""
echo "Total requests: $NUM_REQUESTS"
echo "Successful: $successful"
echo "Failed: $failed"
echo "Total time: ${total_time}s"
echo "Requests/sec: $requests_per_sec"
echo "Avg response time: ${avg_response_time}s"
echo ""

if [ $failed -eq 0 ]; then
    echo "✓ All requests successful!"
else
    echo "✗ Some requests failed"
    exit 1
fi
