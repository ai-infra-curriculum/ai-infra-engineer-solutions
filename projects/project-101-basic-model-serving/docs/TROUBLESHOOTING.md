# Troubleshooting Guide

This guide covers common issues and their solutions for the Model Serving System.

## Table of Contents

1. [Application Issues](#application-issues)
2. [Docker Issues](#docker-issues)
3. [Kubernetes Issues](#kubernetes-issues)
4. [Performance Issues](#performance-issues)
5. [Monitoring Issues](#monitoring-issues)
6. [Common Error Messages](#common-error-messages)

## Application Issues

### Issue: Model Not Loading

**Symptoms:**
- Health check returns `model_loaded: false`
- 503 Service Unavailable errors
- Logs show "Model not initialized"

**Possible Causes:**
1. Insufficient memory
2. Network issues downloading model weights
3. Incorrect MODEL_DEVICE setting

**Solutions:**

```bash
# Check logs
kubectl logs <pod-name> -n model-serving | grep -i "model"

# Solution 1: Increase memory
# Edit kubernetes/deployment.yaml:
resources:
  limits:
    memory: "6Gi"  # Increased from 4Gi

# Solution 2: Pre-download model weights
# Add init container to download model before starting

# Solution 3: Check device setting
kubectl get configmap model-serving-config -n model-serving -o yaml
# Ensure MODEL_DEVICE is "cpu" (unless you have GPU)
```

### Issue: Slow Startup Time

**Symptoms:**
- Pods take >2 minutes to become ready
- Startup probe failures

**Causes:**
- Large model download on first start
- Slow network connection

**Solutions:**

```bash
# Increase startup probe delay
# Edit kubernetes/deployment.yaml:
startupProbe:
  initialDelaySeconds: 30  # Increase from 10
  failureThreshold: 20     # Increase from 12
```

### Issue: Import Errors

**Symptoms:**
- Pods crash with `ModuleNotFoundError`
- Application fails to start

**Causes:**
- Missing dependencies
- Incorrect Python version

**Solutions:**

```bash
# Verify dependencies are in requirements.txt
cat requirements.txt

# Rebuild Docker image
docker build --no-cache -t model-serving-api:latest .

# Check Python version in Dockerfile
grep "FROM python" Dockerfile
# Should be: FROM python:3.11-slim
```

### Issue: Image Processing Errors

**Symptoms:**
- 400 Bad Request errors
- "Image processing failed" messages

**Causes:**
- Invalid image format
- Corrupted image file
- Image too large

**Solutions:**

```bash
# Test with known-good image
curl -X POST http://localhost:8000/predict \
  -F "file=@test.jpg"

# Check file size limit
curl http://localhost:8000/model/info | jq

# Validate image locally
python3 << EOF
from PIL import Image
img = Image.open('test.jpg')
print(f"Size: {img.size}, Mode: {img.mode}")
EOF
```

## Docker Issues

### Issue: Build Fails

**Symptoms:**
- `docker build` command fails
- Compilation errors

**Causes:**
- Network issues
- Disk space issues
- Missing build dependencies

**Solutions:**

```bash
# Check disk space
df -h

# Clean Docker cache
docker system prune -a

# Build with verbose output
docker build -t model-serving-api:latest . --progress=plain

# Check network
ping pypi.org
```

### Issue: Container Crashes Immediately

**Symptoms:**
- Container starts then immediately exits
- `docker ps` shows no running container

**Causes:**
- Application crash on startup
- Missing environment variables

**Solutions:**

```bash
# View container logs
docker logs <container-id>

# Run container interactively
docker run -it --entrypoint /bin/bash model-serving-api:latest

# Check environment variables
docker run model-serving-api:latest env
```

### Issue: Large Image Size

**Symptoms:**
- Docker image >3GB
- Slow deployments

**Causes:**
- Not using multi-stage build
- Including unnecessary files

**Solutions:**

```bash
# Check image layers
docker history model-serving-api:latest

# Verify .dockerignore
cat .dockerignore

# Use multi-stage build (already implemented)
# Ensure Dockerfile starts with:
FROM python:3.11-slim as builder
```

## Kubernetes Issues

### Issue: Pods Stuck in Pending

**Symptoms:**
- `kubectl get pods` shows "Pending" status
- Pods never start

**Causes:**
- Insufficient cluster resources
- Image pull errors
- Node selector mismatch

**Solutions:**

```bash
# Check pod events
kubectl describe pod <pod-name> -n model-serving

# Check node resources
kubectl top nodes

# Check image pull
kubectl get events -n model-serving | grep Pull

# Solution: Scale down or add nodes
kubectl scale deployment/model-serving --replicas=1 -n model-serving
```

### Issue: Pods Crash Looping

**Symptoms:**
- Pods in CrashLoopBackOff state
- Restart count increasing

**Causes:**
- Application crash on startup
- OOM (Out of Memory) kills
- Failed health checks

**Solutions:**

```bash
# Check pod logs
kubectl logs <pod-name> -n model-serving --previous

# Check resource usage
kubectl top pod <pod-name> -n model-serving

# Check events
kubectl get events -n model-serving --sort-by='.lastTimestamp'

# Solution for OOM: Increase memory
# Edit deployment.yaml:
resources:
  limits:
    memory: "6Gi"
```

### Issue: Service Not Reachable

**Symptoms:**
- Cannot access API
- Connection timeout errors

**Causes:**
- Service not created
- Selector mismatch
- Network policy blocking

**Solutions:**

```bash
# Check service
kubectl get svc -n model-serving

# Check endpoints
kubectl get endpoints model-serving -n model-serving
# Should show pod IPs

# Check selector match
kubectl get pods -n model-serving --show-labels
kubectl get svc model-serving -n model-serving -o yaml | grep selector

# Test from within cluster
kubectl run test --image=curlimages/curl -it --rm -- sh
curl http://model-serving.model-serving.svc.cluster.local/health
```

### Issue: Rolling Update Stuck

**Symptoms:**
- Deployment shows "Progressing" but never completes
- Old pods still running

**Causes:**
- New pods failing readiness probe
- Insufficient resources

**Solutions:**

```bash
# Check rollout status
kubectl rollout status deployment/model-serving -n model-serving

# Check pod status
kubectl get pods -n model-serving

# Check new pod logs
kubectl logs <new-pod-name> -n model-serving

# Rollback if needed
kubectl rollout undo deployment/model-serving -n model-serving
```

### Issue: HPA Not Scaling

**Symptoms:**
- Load increasing but pods not scaling
- HPA shows unknown metrics

**Causes:**
- Metrics server not installed
- Resource requests not set
- Metrics not available

**Solutions:**

```bash
# Check HPA status
kubectl get hpa -n model-serving

# Check metrics server
kubectl get deployment metrics-server -n kube-system

# Install metrics server if missing
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify resource requests in deployment
kubectl get deployment model-serving -n model-serving -o yaml | grep -A 2 requests
```

## Performance Issues

### Issue: High Latency

**Symptoms:**
- Response time >500ms
- Slow predictions

**Causes:**
- CPU bottleneck
- Model not loaded
- Network latency

**Solutions:**

```bash
# Check resource usage
kubectl top pods -n model-serving

# Check if model is loaded
curl http://<service-url>/model/info

# Solution 1: Scale horizontally
kubectl scale deployment/model-serving --replicas=5 -n model-serving

# Solution 2: Increase CPU
# Edit deployment.yaml:
resources:
  limits:
    cpu: "4000m"

# Solution 3: Enable GPU (if available)
# Edit configmap.yaml:
MODEL_DEVICE: "cuda"
```

### Issue: Low Throughput

**Symptoms:**
- Cannot handle many concurrent requests
- Queue building up

**Causes:**
- Too few replicas
- Resource constraints
- Blocking I/O

**Solutions:**

```bash
# Check current replicas
kubectl get deployment model-serving -n model-serving

# Scale up
kubectl scale deployment/model-serving --replicas=10 -n model-serving

# Enable HPA for auto-scaling
kubectl apply -f kubernetes/hpa.yaml

# Run load test
./scripts/load-test.sh
```

### Issue: Memory Leaks

**Symptoms:**
- Memory usage continuously increasing
- OOM kills after running for hours

**Causes:**
- Not releasing resources
- Accumulating tensors

**Solutions:**

```bash
# Monitor memory over time
watch kubectl top pods -n model-serving

# Check for memory leaks in code
# Ensure torch.no_grad() is used
# Verify cleanup in model.py

# Temporary fix: Restart pods periodically
# Add to deployment annotations:
kubectl patch deployment model-serving -n model-serving -p \
  '{"spec":{"template":{"metadata":{"annotations":{"restartedAt":"'$(date +%Y-%m-%d-%H-%M-%S)'"}}}}}'
```

## Monitoring Issues

### Issue: Metrics Not Showing

**Symptoms:**
- Grafana dashboards empty
- Prometheus not scraping

**Causes:**
- Prometheus not configured
- Pod annotations missing
- Network issues

**Solutions:**

```bash
# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Open http://localhost:9090/targets

# Verify pod annotations
kubectl get pods -n model-serving -o yaml | grep annotations -A 5
# Should see:
#   prometheus.io/scrape: "true"
#   prometheus.io/port: "8000"
#   prometheus.io/path: "/metrics"

# Test metrics endpoint
kubectl port-forward -n model-serving svc/model-serving 8000:80
curl http://localhost:8000/metrics
```

### Issue: Alerts Not Firing

**Symptoms:**
- Issues occurring but no alerts
- AlertManager not receiving alerts

**Causes:**
- Alert rules not loaded
- Alert conditions not met
- AlertManager not configured

**Solutions:**

```bash
# Check Prometheus rules
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Open http://localhost:9090/rules

# Check AlertManager
kubectl port-forward -n monitoring svc/alertmanager 9093:9093
# Open http://localhost:9093

# Verify alert rules
cat monitoring/prometheus/alerts.yml

# Reload Prometheus config
kubectl delete pod -n monitoring -l app=prometheus
```

## Common Error Messages

### "Model not initialized"

**Solution:**
```bash
# Check if model loading succeeded
kubectl logs <pod-name> -n model-serving | grep "Model loaded"

# Increase startup time
# Edit deployment.yaml to increase startupProbe initialDelaySeconds
```

### "Image size exceeds maximum"

**Solution:**
```bash
# Increase max upload size
# Edit configmap.yaml:
MAX_UPLOAD_SIZE: "52428800"  # 50MB

# Redeploy
kubectl apply -f kubernetes/configmap.yaml
kubectl rollout restart deployment/model-serving -n model-serving
```

### "Failed to download image"

**Solution:**
```bash
# Check URL is accessible
curl -I <image-url>

# Verify network connectivity from pod
kubectl exec -it <pod-name> -n model-serving -- curl -I <image-url>

# Check timeout settings
# Edit configmap.yaml:
INFERENCE_TIMEOUT: "60.0"
```

### "CUDA out of memory"

**Solution:**
```bash
# Switch to CPU
kubectl edit configmap model-serving-config -n model-serving
# Change MODEL_DEVICE to "cpu"

# Or reduce batch size
# Edit configmap.yaml:
BATCH_SIZE: "1"

# Restart pods
kubectl rollout restart deployment/model-serving -n model-serving
```

### "413 Payload Too Large"

**Solution:**
```bash
# Increase nginx/ingress limits if using ingress
# For direct service access, increase MAX_UPLOAD_SIZE in configmap

# Edit configmap.yaml:
MAX_UPLOAD_SIZE: "52428800"  # 50MB

kubectl apply -f kubernetes/configmap.yaml
kubectl rollout restart deployment/model-serving -n model-serving
```

## Debug Commands Reference

### Pod Debugging

```bash
# Get pod logs
kubectl logs <pod-name> -n model-serving

# Get previous pod logs (after crash)
kubectl logs <pod-name> -n model-serving --previous

# Execute command in pod
kubectl exec -it <pod-name> -n model-serving -- bash

# Port forward to pod
kubectl port-forward <pod-name> -n model-serving 8000:8000

# Describe pod
kubectl describe pod <pod-name> -n model-serving
```

### Service Debugging

```bash
# Test service from inside cluster
kubectl run curl-test --image=curlimages/curl -it --rm -- sh
curl http://model-serving.model-serving.svc.cluster.local/health

# Check endpoints
kubectl get endpoints model-serving -n model-serving

# Port forward to service
kubectl port-forward svc/model-serving -n model-serving 8000:80
```

### Resource Monitoring

```bash
# Pod resource usage
kubectl top pods -n model-serving

# Node resource usage
kubectl top nodes

# Watch resource usage
watch kubectl top pods -n model-serving
```

## Getting Help

If you're still experiencing issues:

1. Collect diagnostic information:
```bash
# Generate diagnostic report
kubectl describe deployment model-serving -n model-serving > deployment.txt
kubectl logs -l app=model-serving -n model-serving --tail=1000 > logs.txt
kubectl get events -n model-serving --sort-by='.lastTimestamp' > events.txt
```

2. Check documentation:
   - [API Documentation](API.md)
   - [Architecture Documentation](ARCHITECTURE.md)
   - [Deployment Guide](DEPLOYMENT.md)

3. Contact support:
   - Email: ai-infra-curriculum@joshua-ferguson.com
   - Include diagnostic files and description of issue
