# API Documentation

## Overview

The Model Serving API provides REST endpoints for image classification using a pretrained ResNet50 model. The API is built with FastAPI and includes automatic OpenAPI documentation.

**Base URL:** `http://localhost:8000` (local) or your deployed URL

**OpenAPI Docs:** `/docs` (Swagger UI) or `/redoc` (ReDoc)

## Authentication

Currently, the API does not require authentication. For production deployments, consider adding API key authentication or OAuth2.

## Endpoints

### General Endpoints

#### GET /

Root endpoint providing API information.

**Response:**
```json
{
  "name": "model-serving-api",
  "version": "1.0.0",
  "description": "Image classification API using ResNet50",
  "docs": "/docs",
  "health": "/health"
}
```

**Status Codes:**
- `200 OK`: Success

---

### Monitoring Endpoints

#### GET /health

Health check endpoint for Kubernetes probes.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "timestamp": 1234567890.123,
  "version": "1.0.0"
}
```

**Status Codes:**
- `200 OK`: Service is healthy
- `503 Service Unavailable`: Service is unhealthy (model not loaded)

---

#### GET /ready

Readiness check endpoint for Kubernetes.

**Response:**
```json
{
  "status": "ready",
  "timestamp": 1234567890.123
}
```

**Status Codes:**
- `200 OK`: Service is ready to receive traffic
- `503 Service Unavailable`: Service is not ready

---

#### GET /metrics

Prometheus metrics endpoint for monitoring.

**Response:** Prometheus text format

**Example metrics:**
```
http_requests_total{method="POST",handler="/predict"} 1523
http_request_duration_seconds_bucket{le="0.1"} 1234
```

---

### Model Endpoints

#### GET /model/info

Get information about the loaded model.

**Response:**
```json
{
  "model_name": "resnet50",
  "device": "cpu",
  "is_loaded": true,
  "num_classes": 1000
}
```

**Status Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: Failed to get model info

---

### Prediction Endpoints

#### POST /predict

Perform image classification on an uploaded file.

**Request:**

- Content-Type: `multipart/form-data`
- Body Parameters:
  - `file` (required): Image file (JPEG, PNG, etc.)
  - `top_k` (optional): Number of top predictions to return (1-100, default: 5)

**Example (curl):**
```bash
curl -X POST "http://localhost:8000/predict" \
  -F "file=@dog.jpg" \
  -F "top_k=5"
```

**Example (Python):**
```python
import requests

url = "http://localhost:8000/predict"
files = {"file": open("dog.jpg", "rb")}
params = {"top_k": 5}

response = requests.post(url, files=files, params=params)
print(response.json())
```

**Response:**
```json
{
  "predictions": [
    {
      "class_id": 258,
      "label": "Samoyed",
      "confidence": 0.8932
    },
    {
      "class_id": 259,
      "label": "Pomeranian",
      "confidence": 0.0541
    },
    {
      "class_id": 261,
      "label": "keeshond",
      "confidence": 0.0234
    }
  ],
  "inference_time_ms": 45.23,
  "preprocessing_time_ms": 12.45
}
```

**Status Codes:**
- `200 OK`: Prediction successful
- `400 Bad Request`: Invalid image or parameters
- `413 Payload Too Large`: File size exceeds limit (10MB)
- `500 Internal Server Error`: Prediction failed

---

#### POST /predict/url

Perform image classification on an image from URL.

**Request:**

- Content-Type: `application/json`
- Body:
```json
{
  "url": "https://example.com/image.jpg",
  "top_k": 5
}
```

**Example (curl):**
```bash
curl -X POST "http://localhost:8000/predict/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/dog.jpg", "top_k": 5}'
```

**Example (Python):**
```python
import requests

url = "http://localhost:8000/predict/url"
payload = {
    "url": "https://example.com/dog.jpg",
    "top_k": 5
}

response = requests.post(url, json=payload)
print(response.json())
```

**Response:**
```json
{
  "predictions": [
    {
      "class_id": 258,
      "label": "Samoyed",
      "confidence": 0.8932
    },
    {
      "class_id": 259,
      "label": "Pomeranian",
      "confidence": 0.0541
    }
  ],
  "inference_time_ms": 45.23,
  "preprocessing_time_ms": 156.78
}
```

**Status Codes:**
- `200 OK`: Prediction successful
- `400 Bad Request`: Invalid URL or image
- `422 Unprocessable Entity`: Invalid request format
- `500 Internal Server Error`: Prediction failed

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error type",
  "detail": "Detailed error message"
}
```

### Common Errors

**Invalid Image Format:**
```json
{
  "error": "Image processing failed",
  "detail": "Failed to load image: cannot identify image file"
}
```

**File Too Large:**
```json
{
  "error": "File size exceeds maximum",
  "detail": "File size 12582912 bytes exceeds maximum 10485760 bytes"
}
```

**Invalid URL:**
```json
{
  "error": "Failed to download image",
  "detail": "Invalid URL scheme: ftp://example.com/image.jpg"
}
```

---

## Rate Limiting

Currently, there are no rate limits. For production deployments, consider implementing rate limiting based on your requirements.

---

## Performance

### Expected Latency

- **p50**: < 50ms
- **p95**: < 100ms
- **p99**: < 150ms

*Note: Latency excludes network transfer time and depends on hardware.*

### File Size Limits

- **Maximum upload size**: 10MB
- **Recommended image size**: < 5MB

### Concurrent Requests

The API can handle multiple concurrent requests. The number depends on your deployment configuration and hardware.

---

## Code Examples

### JavaScript (Node.js)

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

// File upload
const form = new FormData();
form.append('file', fs.createReadStream('dog.jpg'));
form.append('top_k', '5');

axios.post('http://localhost:8000/predict', form, {
  headers: form.getHeaders()
})
.then(response => console.log(response.data))
.catch(error => console.error(error));

// URL prediction
axios.post('http://localhost:8000/predict/url', {
  url: 'https://example.com/dog.jpg',
  top_k: 5
})
.then(response => console.log(response.data))
.catch(error => console.error(error));
```

### Python (requests)

```python
import requests

# File upload
with open('dog.jpg', 'rb') as f:
    files = {'file': f}
    params = {'top_k': 5}
    response = requests.post(
        'http://localhost:8000/predict',
        files=files,
        params=params
    )
    print(response.json())

# URL prediction
response = requests.post(
    'http://localhost:8000/predict/url',
    json={
        'url': 'https://example.com/dog.jpg',
        'top_k': 5
    }
)
print(response.json())
```

### Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "io"
    "mime/multipart"
    "net/http"
    "os"
)

func predictFromFile(filePath string) {
    file, _ := os.Open(filePath)
    defer file.Close()

    body := &bytes.Buffer{}
    writer := multipart.NewWriter(body)

    part, _ := writer.CreateFormFile("file", filePath)
    io.Copy(part, file)
    writer.WriteField("top_k", "5")
    writer.Close()

    req, _ := http.NewRequest("POST", "http://localhost:8000/predict", body)
    req.Header.Set("Content-Type", writer.FormDataContentType())

    client := &http.Client{}
    resp, _ := client.Do(req)
    defer resp.Body.Close()

    // Parse response...
}
```

---

## Best Practices

1. **Always validate images before sending** - Check file size and format client-side
2. **Handle errors gracefully** - Implement retry logic for transient failures
3. **Use appropriate timeouts** - Set reasonable timeout values for your use case
4. **Cache results when possible** - Cache predictions for the same images
5. **Monitor your usage** - Track API calls and latency

---

## Versioning

Current API version: **v1.0.0**

The API follows semantic versioning. Breaking changes will result in a major version bump.

---

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Email: ai-infra-curriculum@joshua-ferguson.com

---

## OpenAPI Specification

The complete OpenAPI specification is available at `/openapi.json`. You can import this into tools like Postman or Insomnia for easy testing.
