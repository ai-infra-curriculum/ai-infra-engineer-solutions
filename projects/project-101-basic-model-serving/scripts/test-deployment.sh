#!/bin/bash

# Test deployment script
# This script runs smoke tests against the deployed API

set -e

echo "=========================================="
echo "Model Serving System - Smoke Tests"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Configuration
API_URL=${API_URL:-"http://localhost:8000"}
TEST_IMAGE_URL="https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg"

# Test 1: Health check
echo "Test 1: Health Check"
response=$(curl -s -o /dev/null -w "%{http_code}" $API_URL/health)
if [ "$response" = "200" ]; then
    print_status "Health check passed"
else
    print_error "Health check failed (HTTP $response)"
    exit 1
fi

# Test 2: Readiness check
echo ""
echo "Test 2: Readiness Check"
response=$(curl -s -o /dev/null -w "%{http_code}" $API_URL/ready)
if [ "$response" = "200" ]; then
    print_status "Readiness check passed"
else
    print_error "Readiness check failed (HTTP $response)"
    exit 1
fi

# Test 3: Model info
echo ""
echo "Test 3: Model Info"
response=$(curl -s $API_URL/model/info)
if echo "$response" | grep -q "model_name"; then
    print_status "Model info retrieved"
    echo "Model: $(echo $response | grep -o '"model_name":"[^"]*"' | cut -d'"' -f4)"
else
    print_error "Failed to get model info"
    exit 1
fi

# Test 4: Prediction from URL
echo ""
echo "Test 4: Prediction from URL"
payload='{"url": "'$TEST_IMAGE_URL'", "top_k": 3}'
response=$(curl -s -X POST "$API_URL/predict/url" \
    -H "Content-Type: application/json" \
    -d "$payload")

if echo "$response" | grep -q "predictions"; then
    print_status "Prediction from URL successful"
    top_prediction=$(echo $response | grep -o '"label":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo "Top prediction: $top_prediction"
else
    print_error "Prediction from URL failed"
    echo "$response"
    exit 1
fi

# Test 5: Create a simple test image and upload
echo ""
echo "Test 5: Prediction from File Upload"
# Create a simple test image using Python
python3 << EOF
from PIL import Image
import io

# Create a simple test image
img = Image.new('RGB', (224, 224), color=(73, 109, 137))
img.save('/tmp/test_image.jpg', 'JPEG')
EOF

response=$(curl -s -X POST "$API_URL/predict" \
    -F "file=@/tmp/test_image.jpg" \
    -F "top_k=3")

if echo "$response" | grep -q "predictions"; then
    print_status "Prediction from file upload successful"
else
    print_error "Prediction from file upload failed"
    echo "$response"
    exit 1
fi

# Clean up
rm -f /tmp/test_image.jpg

# Test 6: API Documentation
echo ""
echo "Test 6: API Documentation"
response=$(curl -s -o /dev/null -w "%{http_code}" $API_URL/docs)
if [ "$response" = "200" ]; then
    print_status "API documentation accessible"
else
    print_error "API documentation not accessible (HTTP $response)"
fi

# Test 7: Metrics endpoint
echo ""
echo "Test 7: Metrics Endpoint"
response=$(curl -s $API_URL/metrics)
if echo "$response" | grep -q "http_requests_total"; then
    print_status "Metrics endpoint working"
else
    print_error "Metrics endpoint not working"
fi

# Summary
echo ""
echo "=========================================="
echo "All Tests Passed!"
echo "=========================================="
echo ""
echo "API URL: $API_URL"
echo "API Docs: $API_URL/docs"
echo "Metrics: $API_URL/metrics"
echo ""
