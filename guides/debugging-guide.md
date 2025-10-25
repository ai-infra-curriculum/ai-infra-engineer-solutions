# AI Infrastructure Debugging Guide

> **A comprehensive guide to debugging AI infrastructure systems, from local development to production environments**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Debugging Methodology](#debugging-methodology)
3. [Essential Debugging Tools](#essential-debugging-tools)
4. [Component-Specific Debugging](#component-specific-debugging)
   - [Docker Debugging](#docker-debugging)
   - [Kubernetes Debugging](#kubernetes-debugging)
   - [Python Application Debugging](#python-application-debugging)
   - [GPU Debugging](#gpu-debugging)
   - [Database Debugging](#database-debugging)
   - [Network Debugging](#network-debugging)
5. [Log Analysis Techniques](#log-analysis-techniques)
6. [Performance Debugging](#performance-debugging)
7. [Monitoring-Based Debugging](#monitoring-based-debugging)
8. [Project-Specific Debugging](#project-specific-debugging)
   - [Project 01: Model Serving API](#project-01-model-serving-api)
   - [Project 02: Multi-Model Serving](#project-02-multi-model-serving)
   - [Project 03: GPU-Accelerated Inference](#project-03-gpu-accelerated-inference)
9. [Real-World Debugging Scenarios](#real-world-debugging-scenarios)
10. [Debugging Checklists](#debugging-checklists)
11. [Advanced Debugging Techniques](#advanced-debugging-techniques)
12. [Resources and References](#resources-and-references)

---

## Introduction

### What This Guide Covers

This guide provides systematic approaches to debugging AI infrastructure systems. Whether you're troubleshooting a containerized application, investigating Kubernetes pod failures, or diagnosing GPU memory issues, this guide offers practical techniques and real-world solutions.

### Who This Guide Is For

- AI Infrastructure Engineers
- DevOps Engineers working with ML systems
- Site Reliability Engineers (SREs)
- ML Engineers managing infrastructure
- Anyone deploying and maintaining AI systems

### How to Use This Guide

1. **Systematic Approach**: Start with the debugging methodology
2. **Component Focus**: Jump to specific sections for targeted issues
3. **Project-Specific**: Use project sections for context-aware debugging
4. **Reference**: Keep handy for quick command lookups

---

## Debugging Methodology

### The Scientific Method for Debugging

Effective debugging follows a systematic approach:

```
┌─────────────────────────────────────────────┐
│          1. OBSERVE THE PROBLEM             │
│  What is happening? What should happen?     │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│       2. GATHER INFORMATION                 │
│  Logs, metrics, traces, system state        │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│     3. FORM A HYPOTHESIS                    │
│  What could be causing this?                │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│       4. TEST THE HYPOTHESIS                │
│  Design an experiment to verify             │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      5. ANALYZE RESULTS                     │
│  Did the test confirm or reject?            │
└─────────────────┬───────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
    ┌────▼────┐      ┌────▼────┐
    │ SOLVED  │      │  RETRY  │
    └─────────┘      └─────────┘
```

### Step 1: Observe the Problem

**Document Everything:**
- What is the expected behavior?
- What is the actual behavior?
- When did it start happening?
- Is it consistent or intermittent?
- What changed recently?

**Example Documentation Template:**

```markdown
## Issue Report

**Date/Time**: 2025-10-16 14:30 UTC
**Environment**: Production / Staging / Dev
**Severity**: Critical / High / Medium / Low

**Expected Behavior**:
Model serving API should return predictions in <200ms

**Actual Behavior**:
API returns 504 Gateway Timeout after 30 seconds

**Frequency**:
- Intermittent
- Occurs during high traffic (>100 req/s)
- Started after deployment v1.2.3

**Impact**:
- 15% of requests failing
- User complaints increasing
- Revenue impact: $X/hour

**Recent Changes**:
- Deployed new model version
- Increased pod replicas
- Updated Python dependencies
```

### Step 2: Gather Information

**The Five Sources of Truth:**

1. **Application Logs**: What is the application saying?
2. **System Metrics**: How are resources being used?
3. **Distributed Traces**: Where is time being spent?
4. **Infrastructure State**: What is the system configuration?
5. **User Reports**: What are users experiencing?

**Information Gathering Commands:**

```bash
# Application logs
kubectl logs <pod-name> --tail=100 --follow
kubectl logs <pod-name> --previous  # Previous crashed container

# System metrics
kubectl top pods
kubectl top nodes
kubectl describe pod <pod-name>

# Infrastructure state
kubectl get pods -o wide
kubectl get events --sort-by='.lastTimestamp'
docker ps -a
docker stats

# Network state
kubectl get svc
kubectl get ingress
netstat -tlnp

# Resource availability
df -h  # Disk space
free -h  # Memory
lscpu  # CPU info
nvidia-smi  # GPU info (if applicable)
```

### Step 3: Form a Hypothesis

**Common Hypothesis Categories:**

1. **Resource Exhaustion**: Out of memory, CPU, disk, GPU memory
2. **Configuration Error**: Wrong environment variables, missing secrets
3. **Network Issues**: Timeouts, DNS resolution, firewall rules
4. **Code Bugs**: Logic errors, race conditions, memory leaks
5. **Dependency Problems**: External service down, API rate limits
6. **Data Issues**: Corrupt data, unexpected input formats

**Hypothesis Formation Framework:**

```
IF [condition] THEN [expected behavior] ELSE [observed behavior]

Example:
IF the model is loading correctly
THEN predictions should return in <200ms
ELSE we see 30s timeouts

Therefore, hypothesis: Model is not loading correctly or is too large
```

### Step 4: Test the Hypothesis

**Testing Strategies:**

1. **Isolation**: Remove variables to narrow down the cause
2. **Reproduction**: Can you reproduce the issue consistently?
3. **Comparison**: Compare working vs. broken environments
4. **Instrumentation**: Add logging, metrics, or debug code
5. **Binary Search**: Divide and conquer (e.g., git bisect)

**Example Test Plan:**

```bash
# Hypothesis: Model loading is slow causing timeouts

# Test 1: Check model load time
time python -c "import torch; model = torch.load('model.pth')"

# Test 2: Monitor memory during load
docker stats <container-id> &
docker exec <container-id> python load_model.py

# Test 3: Compare with smaller model
docker run --rm -e MODEL_PATH=small_model.pth app:latest

# Test 4: Check disk I/O
iostat -x 1 10  # Monitor disk performance
```

### Step 5: Analyze Results

**Analysis Questions:**

- Did the test confirm the hypothesis?
- Are there unexpected findings?
- Can we reproduce the issue reliably?
- What is the root cause?
- What is the appropriate fix?

**Decision Tree:**

```
Hypothesis confirmed?
├── Yes → Implement fix
│   ├── Test fix in dev
│   ├── Deploy to staging
│   ├── Verify resolution
│   └── Deploy to production
│
└── No → Refine hypothesis
    ├── Review additional data
    ├── Consider alternative causes
    └── Repeat testing cycle
```

---

## Essential Debugging Tools

### Command-Line Tools

#### Linux/Unix Utilities

```bash
# Process monitoring
top         # Interactive process viewer
htop        # Enhanced top (if available)
ps aux      # Process snapshot
pgrep       # Process grep

# Network debugging
netstat -tlnp       # Listening ports
ss -tlnp            # Socket statistics (modern alternative)
lsof -i :8080       # What's using port 8080?
tcpdump -i any port 8080  # Packet capture
curl -v http://localhost:8080/health  # Verbose HTTP
wget --spider http://localhost:8080   # Test connectivity

# File system
df -h               # Disk space
du -sh *            # Directory sizes
lsof +D /path       # Open files in directory
find /var/log -name "*.log" -mtime -1  # Recent logs

# System calls and debugging
strace -p <pid>     # Trace system calls
ltrace -p <pid>     # Trace library calls
gdb -p <pid>        # GNU debugger

# Resource limits
ulimit -a           # Show all limits
cat /proc/<pid>/limits  # Process-specific limits
```

#### Docker Debugging Commands

```bash
# Container inspection
docker ps -a                    # All containers
docker logs <container> -f      # Follow logs
docker inspect <container>      # Detailed info
docker stats <container>        # Resource usage
docker exec -it <container> /bin/bash  # Interactive shell

# Image debugging
docker images                   # List images
docker history <image>          # Layer history
docker inspect <image>          # Image details
dive <image>                    # Interactive image explorer

# Network debugging
docker network ls               # List networks
docker network inspect <network>  # Network details
docker port <container>         # Port mappings

# Volume debugging
docker volume ls                # List volumes
docker volume inspect <volume>  # Volume details

# System-wide
docker system df                # Disk usage
docker system events            # Real-time events
docker system prune             # Cleanup (careful!)
```

#### Kubernetes Debugging Commands

```bash
# Pod debugging
kubectl get pods -o wide
kubectl describe pod <pod-name>
kubectl logs <pod-name> --tail=100 -f
kubectl logs <pod-name> -c <container-name>  # Multi-container pods
kubectl logs <pod-name> --previous           # Previous crashed container
kubectl exec -it <pod-name> -- /bin/bash
kubectl port-forward <pod-name> 8080:8080

# Service debugging
kubectl get svc
kubectl describe svc <service-name>
kubectl get endpoints <service-name>

# Deployment debugging
kubectl get deployments
kubectl describe deployment <deployment-name>
kubectl rollout status deployment/<deployment-name>
kubectl rollout history deployment/<deployment-name>

# Events and logs
kubectl get events --sort-by='.lastTimestamp'
kubectl get events --field-selector involvedObject.name=<pod-name>

# Resource usage
kubectl top pods
kubectl top nodes
kubectl describe node <node-name>

# Configuration
kubectl get configmap
kubectl describe configmap <configmap-name>
kubectl get secret
kubectl describe secret <secret-name>

# Network policies
kubectl get networkpolicies
kubectl describe networkpolicy <policy-name>

# Debug with ephemeral containers (K8s 1.23+)
kubectl debug <pod-name> -it --image=busybox --target=<container-name>
```

#### Python Debugging Tools

```bash
# Interactive debugging
python -m pdb script.py         # Python debugger
python -m ipdb script.py        # IPython debugger (better)

# Profiling
python -m cProfile script.py    # CPU profiling
python -m memory_profiler script.py  # Memory profiling

# Tracing
python -m trace --trace script.py    # Line-by-line execution

# Package inspection
pip list                        # Installed packages
pip show <package>              # Package details
python -m site                  # Python path info
```

### Interactive Debugging Tools

#### Python Debugger (pdb) Commands

```python
# Basic commands
(Pdb) h              # Help
(Pdb) l              # List source code
(Pdb) n              # Next line
(Pdb) s              # Step into function
(Pdb) c              # Continue execution
(Pdb) b <line>       # Set breakpoint
(Pdb) p <var>        # Print variable
(Pdb) pp <var>       # Pretty print
(Pdb) a              # Print function arguments
(Pdb) w              # Print stack trace
(Pdb) u              # Move up stack frame
(Pdb) d              # Move down stack frame
(Pdb) q              # Quit debugger

# Advanced commands
(Pdb) bt             # Backtrace
(Pdb) commands <bp>  # Set commands for breakpoint
(Pdb) condition <bp> <expr>  # Conditional breakpoint
(Pdb) display <expr> # Display expression
(Pdb) interact       # Start interactive interpreter
```

**Example Usage:**

```python
import pdb

def predict(model, data):
    pdb.set_trace()  # Debugger will stop here

    # Inspect variables
    # (Pdb) p model
    # (Pdb) p data.shape
    # (Pdb) n  # Next line

    result = model(data)
    return result
```

#### Remote Debugging Setup

**Python Remote Debugging (debugpy):**

```python
# In your application
import debugpy

# Start debug server
debugpy.listen(("0.0.0.0", 5678))
print("Waiting for debugger attach...")
debugpy.wait_for_client()

# Your application code
def main():
    # Your code here
    pass
```

**Docker Configuration:**

```dockerfile
# Expose debug port
EXPOSE 5678

# Install debugpy
RUN pip install debugpy

# Run with debugging
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "app.py"]
```

**Kubernetes Port Forwarding:**

```bash
# Forward debug port
kubectl port-forward <pod-name> 5678:5678

# Connect with VS Code or PyCharm
# VS Code: Use "Python: Remote Attach" configuration
# PyCharm: Use "Python Debug Server" configuration
```

### Logging and Monitoring Tools

#### Structured Logging Best Practices

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        return json.dumps(log_data)

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage with context
def predict_endpoint(request_id, data):
    logger.info("Prediction request received", extra={"request_id": request_id})
    try:
        result = model.predict(data)
        logger.info("Prediction successful", extra={
            "request_id": request_id,
            "inference_time_ms": result["time"]
        })
        return result
    except Exception as e:
        logger.error("Prediction failed", extra={
            "request_id": request_id,
            "error": str(e)
        }, exc_info=True)
        raise
```

#### Log Analysis with jq

```bash
# Parse JSON logs
cat app.log | jq '.'

# Filter by level
cat app.log | jq 'select(.level == "ERROR")'

# Extract specific fields
cat app.log | jq '{timestamp, message, request_id}'

# Count errors by type
cat app.log | jq -r 'select(.level == "ERROR") | .message' | sort | uniq -c

# Time-based filtering
cat app.log | jq 'select(.timestamp > "2025-10-16T10:00:00")'

# Calculate average inference time
cat app.log | jq -r 'select(.inference_time_ms) | .inference_time_ms' | \
  awk '{sum+=$1; count++} END {print sum/count}'

# Find slow requests (>1000ms)
cat app.log | jq 'select(.inference_time_ms > 1000)'
```

#### Log Aggregation Commands

```bash
# Tail logs from all pods
kubectl logs -l app=model-serving --tail=100 -f --all-containers

# Aggregate logs with stern (Kubernetes)
stern --selector app=model-serving --tail 100

# Export logs to file
kubectl logs <pod-name> > pod.log

# Search logs with grep
kubectl logs <pod-name> | grep -i error
kubectl logs <pod-name> | grep -E "(error|exception|failed)"

# Count errors
kubectl logs <pod-name> | grep -c "ERROR"

# Find unique errors
kubectl logs <pod-name> | grep ERROR | sort | uniq -c | sort -rn
```

---

## Component-Specific Debugging

### Docker Debugging

#### Container Won't Start

**Symptoms:**
- Container immediately exits
- Status shows "Restarting" or "CrashLoopBackOff"
- No logs or minimal logs

**Debugging Steps:**

```bash
# 1. Check container status
docker ps -a | grep <container-name>

# 2. View container logs
docker logs <container-id>

# 3. Inspect container configuration
docker inspect <container-id>

# 4. Check exit code
docker inspect <container-id> --format='{{.State.ExitCode}}'

# Common exit codes:
# 0: Success
# 1: Application error
# 125: Docker daemon error
# 126: Command cannot execute
# 127: Command not found
# 137: SIGKILL (killed by system, often OOM)
# 139: SIGSEGV (segmentation fault)
# 143: SIGTERM (graceful termination)

# 5. Try running with interactive shell
docker run -it --entrypoint /bin/bash <image>

# 6. Override command to debug
docker run -it <image> /bin/sh -c "ls -la /app && cat /app/entrypoint.sh"

# 7. Check if entrypoint script has issues
docker run -it <image> /bin/bash
> cat /app/entrypoint.sh
> bash -x /app/entrypoint.sh  # Run with debug mode
```

**Common Issues and Solutions:**

```bash
# Issue: Missing required files
# Check if files exist in image
docker run --rm <image> ls -la /app

# Issue: Permission denied
# Check file permissions
docker run --rm <image> ls -l /app/entrypoint.sh
# Fix: chmod +x entrypoint.sh in Dockerfile

# Issue: Command not found
# Check PATH
docker run --rm <image> echo $PATH
docker run --rm <image> which python

# Issue: Python module not found
# Check installed packages
docker run --rm <image> pip list
docker run --rm <image> python -c "import torch"

# Issue: Wrong working directory
# Check WORKDIR
docker run --rm <image> pwd
```

#### Container Running But Not Responding

**Debugging Steps:**

```bash
# 1. Check if process is running inside container
docker exec <container-id> ps aux

# 2. Check network connectivity
docker exec <container-id> curl http://localhost:8080/health
docker exec <container-id> netstat -tlnp

# 3. Check port mapping
docker port <container-id>
# Expected: 8080/tcp -> 0.0.0.0:8080

# 4. Test from host
curl -v http://localhost:8080/health
telnet localhost 8080

# 5. Check container logs for startup messages
docker logs <container-id> --tail=50

# 6. Check resource usage
docker stats <container-id>

# 7. Execute interactive debugging inside container
docker exec -it <container-id> /bin/bash
```

**Common Issues:**

```bash
# Issue: Application bound to 127.0.0.1 instead of 0.0.0.0
# Check application binding
docker exec <container-id> netstat -tlnp
# Should show: 0.0.0.0:8080, not 127.0.0.1:8080

# Fix in application:
# Python FastAPI: uvicorn main:app --host 0.0.0.0 --port 8080
# Python Flask: app.run(host='0.0.0.0', port=8080)

# Issue: Firewall blocking connection
# Check iptables
sudo iptables -L -n
sudo iptables -L DOCKER -n

# Issue: Port conflict
# Find what's using the port
sudo lsof -i :8080
sudo netstat -tlnp | grep 8080
```

#### Container Crashes Under Load

**Debugging Steps:**

```bash
# 1. Monitor resource usage during load
docker stats <container-id>

# 2. Check for OOM (Out of Memory) kills
docker inspect <container-id> | jq '.[0].State.OOMKilled'
dmesg | grep -i "out of memory"
dmesg | grep <container-id>

# 3. Check memory limits
docker inspect <container-id> | jq '.[0].HostConfig.Memory'
docker inspect <container-id> | jq '.[0].HostConfig.MemorySwap'

# 4. Increase memory limit
docker run --memory=4g --memory-swap=4g <image>

# 5. Profile memory usage inside container
docker exec <container-id> python -m memory_profiler app.py

# 6. Check for memory leaks
# Monitor memory over time
watch -n 1 'docker stats <container-id> --no-stream'

# 7. Enable core dumps for crashes
docker run --ulimit core=-1 <image>
```

#### Build Issues

**Debugging Steps:**

```bash
# 1. Build with verbose output
docker build --progress=plain --no-cache -t <image> .

# 2. Check build context size
du -sh .dockerignore
du -sh .

# 3. Debug specific layer
# Add RUN commands to inspect state
RUN ls -la /app && cat requirements.txt

# 4. Build up to specific stage
docker build --target builder -t debug-image .

# 5. Inspect intermediate layers
docker build -t <image> .
# Note: Each RUN command creates a layer
docker history <image>

# 6. Check base image
docker pull <base-image>
docker run -it <base-image> /bin/bash

# 7. Test commands locally
# Run the same commands on your host to verify they work
```

**Common Build Issues:**

```dockerfile
# Issue: Cache not being used effectively
# Solution: Order commands from least to most frequently changing

# Bad:
COPY . /app
RUN pip install -r requirements.txt

# Good:
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt
COPY . /app

# Issue: Large image size
# Solution: Multi-stage builds

# Bad:
FROM python:3.11
COPY . /app
RUN pip install -r requirements.txt

# Good:
FROM python:3.11 as builder
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY . /app
ENV PATH=/root/.local/bin:$PATH

# Issue: Permission denied during build
# Solution: Fix ownership
RUN chown -R appuser:appuser /app
USER appuser
```

### Kubernetes Debugging

#### Pod Not Starting

**Symptoms:**
- Pod stuck in "Pending" state
- Pod stuck in "ContainerCreating"
- Pod in "CrashLoopBackOff"
- Pod in "ImagePullBackOff"

**Debugging Steps:**

```bash
# 1. Check pod status
kubectl get pods
kubectl get pods <pod-name> -o yaml

# 2. Describe pod for events
kubectl describe pod <pod-name>

# Look for:
# - Events section at bottom
# - Warning messages
# - Resource requests/limits
# - Node assignment

# 3. Check recent events
kubectl get events --sort-by='.lastTimestamp' | head -20
kubectl get events --field-selector involvedObject.name=<pod-name>

# 4. Check node resources
kubectl top nodes
kubectl describe node <node-name>
```

**Common Issues and Solutions:**

```bash
# Issue: ImagePullBackOff
# Symptoms: Cannot pull container image
kubectl describe pod <pod-name>
# Look for: "Failed to pull image" or "ErrImagePull"

# Solutions:
# 1. Check image name and tag
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].image}'

# 2. Check image exists
docker pull <image-name>

# 3. Check image pull secrets
kubectl get secrets
kubectl describe secret <imagePullSecret-name>

# 4. Add/verify imagePullSecrets in deployment
kubectl edit deployment <deployment-name>
# Add:
# imagePullSecrets:
# - name: regcred

# Issue: CrashLoopBackOff
# Symptoms: Container starts but immediately crashes
kubectl logs <pod-name>
kubectl logs <pod-name> --previous  # Previous crashed instance

# Check exit code
kubectl get pod <pod-name> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'

# Solutions:
# 1. Check application logs
# 2. Verify environment variables
kubectl get pod <pod-name> -o yaml | grep -A 20 env:

# 3. Check liveness/readiness probes
kubectl get pod <pod-name> -o yaml | grep -A 10 livenessProbe:
kubectl get pod <pod-name> -o yaml | grep -A 10 readinessProbe:

# 4. Disable probes temporarily to debug
kubectl edit deployment <deployment-name>
# Comment out or increase initialDelaySeconds

# Issue: Insufficient resources
# Symptoms: Pod stuck in "Pending"
kubectl describe pod <pod-name>
# Look for: "Insufficient cpu" or "Insufficient memory"

# Solutions:
# 1. Check resource requests
kubectl get pod <pod-name> -o yaml | grep -A 5 resources:

# 2. Check node capacity
kubectl describe nodes | grep -A 5 "Allocated resources:"

# 3. Reduce resource requests or add nodes
kubectl edit deployment <deployment-name>
```

#### Pod Running But Not Receiving Traffic

**Debugging Steps:**

```bash
# 1. Check pod readiness
kubectl get pods
# Look for: READY column (e.g., 1/1)

kubectl describe pod <pod-name>
# Look for: Ready True/False in Conditions

# 2. Check service endpoints
kubectl get svc
kubectl describe svc <service-name>
kubectl get endpoints <service-name>

# Should show pod IPs:
# Endpoints: 10.244.0.5:8080,10.244.0.6:8080

# 3. Test pod directly
kubectl port-forward <pod-name> 8080:8080
curl http://localhost:8080/health

# 4. Check service selector matches pod labels
kubectl get svc <service-name> -o yaml | grep -A 5 selector:
kubectl get pod <pod-name> --show-labels

# 5. Test service from another pod
kubectl run test-pod --rm -it --image=curlimages/curl -- sh
> curl http://<service-name>:8080/health

# 6. Check network policies
kubectl get networkpolicies
kubectl describe networkpolicy <policy-name>

# 7. Check ingress configuration
kubectl get ingress
kubectl describe ingress <ingress-name>
```

**Common Issues:**

```bash
# Issue: Label mismatch
# Service selector doesn't match pod labels

# Check service selector
kubectl get svc <service-name> -o yaml | grep -A 5 selector:
# Example output: app: model-serving

# Check pod labels
kubectl get pod <pod-name> --show-labels
# Example output: app=model-serving,version=v1

# Fix: Update service or deployment labels to match
kubectl label pod <pod-name> app=model-serving

# Issue: Readiness probe failing
# Pod is running but not ready

kubectl describe pod <pod-name>
# Look for: Readiness probe failed

kubectl logs <pod-name>
# Check why probe endpoint is failing

# Test probe endpoint
kubectl exec <pod-name> -- curl http://localhost:8080/health

# Fix: Update readiness probe or fix application
kubectl edit deployment <deployment-name>

# Issue: Wrong port configuration
# Service port doesn't match container port

kubectl get svc <service-name> -o yaml
# Check: port (service port) and targetPort (container port)

kubectl get pod <pod-name> -o yaml | grep -A 5 containerPort:

# Fix: Update service targetPort to match containerPort
```

#### High Pod Restart Count

**Debugging Steps:**

```bash
# 1. Check restart count
kubectl get pods
# Look for: RESTARTS column

# 2. Check pod events
kubectl describe pod <pod-name>
# Look for: Restart count and restart reason

# 3. Check logs from current and previous containers
kubectl logs <pod-name>
kubectl logs <pod-name> --previous
kubectl logs <pod-name> --all-containers

# 4. Check resource usage
kubectl top pod <pod-name>
kubectl describe pod <pod-name> | grep -A 10 "Limits:"

# 5. Check OOMKilled status
kubectl get pod <pod-name> -o yaml | grep -A 5 lastState:
# Look for: reason: OOMKilled

# 6. Monitor pod in real-time
watch kubectl get pod <pod-name>
kubectl logs <pod-name> -f

# 7. Check liveness probe configuration
kubectl get pod <pod-name> -o yaml | grep -A 10 livenessProbe:
```

**Common Causes:**

```yaml
# Cause 1: Aggressive liveness probe
# Probe timeout is too short or starts too early

# Bad configuration:
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10  # Too short for model loading
  periodSeconds: 5
  timeoutSeconds: 1  # Too short
  failureThreshold: 2  # Too aggressive

# Good configuration:
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 60  # Allow time for startup
  periodSeconds: 10
  timeoutSeconds: 5  # Reasonable timeout
  failureThreshold: 3  # More lenient

# Cause 2: Memory limits too low
# Container is OOMKilled

# Check current limits:
kubectl get pod <pod-name> -o yaml | grep -A 5 resources:

# Increase memory:
resources:
  requests:
    memory: "2Gi"
    cpu: "1"
  limits:
    memory: "4Gi"  # Increase this
    cpu: "2"

# Cause 3: Application crashes
# Check logs for errors
kubectl logs <pod-name> --previous

# Common patterns:
# - Unhandled exceptions
# - Signal 11 (SIGSEGV) - segmentation fault
# - Signal 9 (SIGKILL) - OOM kill
# - Signal 15 (SIGTERM) - graceful shutdown
```

#### Debugging Inter-Pod Communication

```bash
# Test 1: Can pod reach service?
kubectl exec <pod-name> -- curl http://<service-name>:8080/health

# Test 2: Can pod reach another pod directly?
kubectl get pod <target-pod> -o wide  # Get pod IP
kubectl exec <source-pod> -- curl http://<pod-ip>:8080/health

# Test 3: DNS resolution working?
kubectl exec <pod-name> -- nslookup <service-name>
kubectl exec <pod-name> -- nslookup <service-name>.<namespace>.svc.cluster.local

# Test 4: Check CoreDNS
kubectl get pods -n kube-system | grep coredns
kubectl logs -n kube-system <coredns-pod>

# Test 5: Network policies blocking traffic?
kubectl get networkpolicies --all-namespaces
kubectl describe networkpolicy <policy-name>

# Test 6: Use debug container for network testing
kubectl debug <pod-name> -it --image=nicolaka/netshoot
# Inside debug container:
> curl http://<service-name>:8080
> traceroute <service-name>
> nslookup <service-name>
> telnet <service-name> 8080
```

### Python Application Debugging

#### ImportError and ModuleNotFoundError

**Debugging Steps:**

```bash
# 1. Check installed packages
pip list
pip show <package-name>

# 2. Check Python path
python -c "import sys; print('\\n'.join(sys.path))"

# 3. Try importing interactively
python -c "import torch; print(torch.__version__)"

# 4. Check for conflicting packages
pip check

# 5. Verify package location
python -c "import torch; print(torch.__file__)"

# 6. Check for typos in import
python -c "import torch; help(torch)"  # Lists available modules
```

**Common Issues:**

```bash
# Issue: Package not installed
# Solution: Install package
pip install torch transformers

# Issue: Wrong package version
# Solution: Install specific version
pip install "torch==2.0.0"

# Issue: Virtual environment not activated
# Solution: Activate venv
source venv/bin/activate
# or in Docker: use full path to python
/opt/venv/bin/python app.py

# Issue: Package installed in wrong location
# Solution: Use --user flag or venv
pip install --user torch

# Issue: Circular imports
# Solution: Restructure code to avoid circular dependencies
# Or use lazy imports:
def my_function():
    import torch  # Import inside function
    return torch.tensor([1, 2, 3])
```

#### Performance Issues

**Debugging Steps:**

```bash
# 1. Profile CPU usage
python -m cProfile -o profile.stats app.py

# Analyze profile
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"

# 2. Profile specific function
python -m cProfile -s cumulative app.py

# 3. Line-by-line profiling
pip install line_profiler
# Add @profile decorator to functions
kernprof -l -v app.py

# 4. Memory profiling
pip install memory_profiler
python -m memory_profiler app.py

# 5. Trace execution
python -m trace --count app.py

# 6. Use py-spy for production profiling
pip install py-spy
py-spy top --pid <pid>
py-spy record --pid <pid> -o profile.svg
```

**Example: Profiling ML Inference:**

```python
import cProfile
import pstats
import io
from pstats import SortKey

def profile_inference():
    pr = cProfile.Profile()
    pr.enable()

    # Your inference code
    result = model.predict(data)

    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(20)

    print(s.getvalue())
    return result

# Line-by-line profiling
from memory_profiler import profile

@profile
def predict_batch(model, batch):
    # This function will show memory usage per line
    inputs = preprocess(batch)
    outputs = model(inputs)
    results = postprocess(outputs)
    return results
```

#### Memory Leaks

**Debugging Steps:**

```python
import gc
import tracemalloc

# Start tracing
tracemalloc.start()

# Your code here
for i in range(100):
    result = process_data(data)

# Get memory usage
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.2f} MB")
print(f"Peak: {peak / 1024 / 1024:.2f} MB")

# Get top memory consumers
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("Top 10 memory consumers:")
for stat in top_stats[:10]:
    print(stat)

tracemalloc.stop()
```

**Common Memory Leak Patterns:**

```python
# Pattern 1: Circular references
class Model:
    def __init__(self):
        self.cache = {}
        self.cache['self'] = self  # Circular reference!

# Solution: Use weak references
import weakref

class Model:
    def __init__(self):
        self.cache = {}
        self.cache['self'] = weakref.ref(self)

# Pattern 2: Unclosed resources
def process_file(filename):
    f = open(filename)  # Not closed!
    data = f.read()
    return process(data)

# Solution: Use context manager
def process_file(filename):
    with open(filename) as f:
        data = f.read()
    return process(data)

# Pattern 3: Growing cache without limit
class ModelCache:
    def __init__(self):
        self.cache = {}  # Grows forever!

    def predict(self, key, data):
        if key not in self.cache:
            self.cache[key] = self.model(data)
        return self.cache[key]

# Solution: Use LRU cache with size limit
from functools import lru_cache
from collections import OrderedDict

class ModelCache:
    def __init__(self, maxsize=1000):
        self.cache = OrderedDict()
        self.maxsize = maxsize

    def predict(self, key, data):
        if key not in self.cache:
            if len(self.cache) >= self.maxsize:
                self.cache.popitem(last=False)  # Remove oldest
            self.cache[key] = self.model(data)
        return self.cache[key]

# Pattern 4: PyTorch tensors not being released
def train_step(model, batch):
    loss = model(batch)
    loss.backward()
    return loss  # Keeps computation graph in memory!

# Solution: Detach or use .item()
def train_step(model, batch):
    loss = model(batch)
    loss.backward()
    return loss.item()  # Returns Python float, releases graph
```

### GPU Debugging

#### GPU Not Detected

**Debugging Steps:**

```bash
# 1. Check if GPU is visible to system
nvidia-smi

# Expected output:
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 525.60.11    Driver Version: 525.60.11    CUDA Version: 12.0     |
# |-------------------------------+----------------------+----------------------+
# | GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# | Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
# ...

# 2. Check NVIDIA driver
cat /proc/driver/nvidia/version

# 3. Check CUDA installation
nvcc --version

# 4. Check Docker GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# 5. Check Kubernetes GPU resources
kubectl describe node <node-name> | grep -A 5 "nvidia.com/gpu"

# 6. In Python, check PyTorch GPU access
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.device_count())"

# 7. Check GPU visibility
echo $CUDA_VISIBLE_DEVICES
```

**Common Issues:**

```bash
# Issue: nvidia-smi not found
# Solution: Install NVIDIA drivers
# Ubuntu:
sudo apt-get update
sudo apt-get install nvidia-driver-525

# Issue: CUDA version mismatch
# Check PyTorch CUDA version
python -c "import torch; print(torch.version.cuda)"

# Should match nvidia-smi CUDA version
# Reinstall PyTorch with correct CUDA:
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Issue: Docker can't access GPU
# Ensure nvidia-docker2 is installed
sudo apt-get install nvidia-docker2
sudo systemctl restart docker

# Test GPU access:
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Issue: Kubernetes can't see GPU
# Install NVIDIA device plugin
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/main/nvidia-device-plugin.yml

# Verify:
kubectl get nodes -o yaml | grep -A 10 "nvidia.com/gpu"
```

#### GPU Out of Memory (OOM)

**Debugging Steps:**

```bash
# 1. Check GPU memory usage
nvidia-smi
watch -n 1 nvidia-smi  # Monitor in real-time

# 2. Check specific process
nvidia-smi pmon -c 1  # Process monitoring

# 3. Inside Python, check memory allocation
python -c "
import torch
print(f'Allocated: {torch.cuda.memory_allocated() / 1024**3:.2f} GB')
print(f'Reserved: {torch.cuda.memory_reserved() / 1024**3:.2f} GB')
print(f'Max allocated: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB')
"
```

**Solutions:**

```python
import torch

# Solution 1: Clear cache
torch.cuda.empty_cache()

# Solution 2: Reduce batch size
batch_size = 16  # Try 8, 4, 2, 1

# Solution 3: Use gradient accumulation
accumulation_steps = 4
optimizer.zero_grad()
for i, batch in enumerate(dataloader):
    loss = model(batch) / accumulation_steps
    loss.backward()

    if (i + 1) % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()

# Solution 4: Use gradient checkpointing
from torch.utils.checkpoint import checkpoint

def forward_with_checkpointing(model, x):
    return checkpoint(model, x)

# Solution 5: Use mixed precision
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()

with autocast():
    outputs = model(inputs)
    loss = criterion(outputs, targets)

scaler.scale(loss).backward()
scaler.step(optimizer)
scaler.update()

# Solution 6: Monitor memory in real-time
def print_gpu_memory():
    for i in range(torch.cuda.device_count()):
        total = torch.cuda.get_device_properties(i).total_memory / 1024**3
        reserved = torch.cuda.memory_reserved(i) / 1024**3
        allocated = torch.cuda.memory_allocated(i) / 1024**3
        print(f"GPU {i}: Total={total:.2f}GB, Reserved={reserved:.2f}GB, Allocated={allocated:.2f}GB")

# Solution 7: Use smaller model
# Quantize model to reduce memory
model = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)

# Solution 8: Delete unnecessary tensors
del large_tensor
torch.cuda.empty_cache()

# Solution 9: Use CPU offloading
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# Move only necessary tensors to GPU
inputs = inputs.to(device)
outputs = model(inputs)
results = outputs.cpu()  # Move back to CPU
```

#### Slow GPU Performance

**Debugging Steps:**

```python
import torch
import time

# Profile GPU operations
with torch.autograd.profiler.profile(use_cuda=True) as prof:
    output = model(input_data)

print(prof.key_averages().table(sort_by="cuda_time_total"))

# Check for CPU-GPU synchronization issues
torch.cuda.synchronize()  # Ensure all GPU operations complete
start = time.time()
output = model(input_data)
torch.cuda.synchronize()
elapsed = time.time() - start
print(f"GPU inference time: {elapsed*1000:.2f}ms")

# Check GPU utilization
# Run: nvidia-smi dmon -s u
# Look for GPU utilization % (should be >80% during inference)
```

**Common Performance Issues:**

```python
# Issue 1: Frequent CPU-GPU transfers
# Bad:
for batch in dataloader:
    batch = batch.to('cuda')  # Transfer for each batch
    output = model(batch)
    result = output.cpu()  # Transfer back
    process(result)

# Good:
# Pre-load data to GPU or use pinned memory
dataloader = DataLoader(dataset, pin_memory=True, num_workers=4)
for batch in dataloader:
    batch = batch.to('cuda', non_blocking=True)  # Async transfer
    output = model(batch)

# Issue 2: Small batch sizes
# GPU underutilized with batch_size=1
# Increase batch size to maximize GPU utilization

# Issue 3: Model not in eval mode
model.train()  # Slower, calculates gradients
output = model(input)

# Fix:
model.eval()  # Faster, no gradients
with torch.no_grad():  # Even faster
    output = model(input)

# Issue 4: Using wrong data type
input = input.float()  # Slower on modern GPUs

# Fix: Use mixed precision
input = input.half()  # FP16, much faster
with torch.cuda.amp.autocast():
    output = model(input)

# Issue 5: Not using torch.compile (PyTorch 2.0+)
output = model(input)  # Interpreted mode

# Fix:
model = torch.compile(model)  # JIT compilation
output = model(input)  # Faster
```

### Database Debugging

#### Connection Issues

**Debugging Steps:**

```bash
# 1. Check if database is running
# PostgreSQL:
pg_isready -h localhost -p 5432

# Docker:
docker ps | grep postgres
docker logs <postgres-container>

# Kubernetes:
kubectl get pods -l app=postgres
kubectl logs <postgres-pod>

# 2. Test connection
psql -h localhost -U postgres -d mydb
# or
telnet localhost 5432

# 3. Check connection string
echo $DATABASE_URL

# 4. Test from application
python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://user:pass@localhost:5432/mydb')
conn = engine.connect()
print('Connected successfully')
conn.close()
"

# 5. Check firewall/security groups
# On database server:
sudo iptables -L -n | grep 5432

# Kubernetes network policies:
kubectl get networkpolicies
```

**Common Issues:**

```python
# Issue: Connection refused
# Check if database is listening on correct interface

# PostgreSQL: Edit postgresql.conf
# listen_addresses = '*'  # or specific IP

# Check pg_hba.conf for authentication
# host all all 0.0.0.0/0 md5

# Issue: Too many connections
# Check current connections
SELECT count(*) FROM pg_stat_activity;

# Check max connections
SHOW max_connections;

# Solution: Use connection pooling
from sqlalchemy import create_engine, pool

engine = create_engine(
    'postgresql://user:pass@localhost:5432/mydb',
    poolclass=pool.QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True  # Verify connections before use
)

# Issue: Connection timeout
# Increase timeout in connection string
engine = create_engine(
    'postgresql://user:pass@localhost:5432/mydb',
    connect_args={'connect_timeout': 10}
)

# Issue: SSL required
# Add SSL mode to connection string
engine = create_engine(
    'postgresql://user:pass@localhost:5432/mydb?sslmode=require'
)
```

#### Slow Queries

**Debugging Steps:**

```sql
-- 1. Enable query logging
-- PostgreSQL:
ALTER DATABASE mydb SET log_statement = 'all';
ALTER DATABASE mydb SET log_duration = on;

-- 2. Find slow queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
  AND state = 'active';

-- 3. Explain query plan
EXPLAIN ANALYZE
SELECT * FROM predictions WHERE model_id = 'abc123';

-- 4. Check for missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE tablename = 'predictions';

-- 5. Check table statistics
SELECT * FROM pg_stat_user_tables WHERE relname = 'predictions';

-- 6. Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'predictions';
```

**Common Issues and Solutions:**

```sql
-- Issue: Missing index
-- Check query plan
EXPLAIN ANALYZE
SELECT * FROM predictions WHERE model_id = 'abc123';

-- If you see "Seq Scan", add index
CREATE INDEX idx_predictions_model_id ON predictions(model_id);

-- Verify index is used
EXPLAIN ANALYZE
SELECT * FROM predictions WHERE model_id = 'abc123';
-- Should show "Index Scan using idx_predictions_model_id"

-- Issue: Outdated statistics
-- Update statistics
ANALYZE predictions;

-- Or vacuum and analyze
VACUUM ANALYZE predictions;

-- Issue: Too many columns selected
-- Bad:
SELECT * FROM predictions;  -- Returns all columns

-- Good:
SELECT id, model_id, result FROM predictions;  -- Only needed columns

-- Issue: N+1 queries
-- Bad (ORM):
# for prediction in Prediction.query.all():
#     print(prediction.model.name)  # Separate query for each

-- Good:
# predictions = Prediction.query.options(
#     joinedload(Prediction.model)
# ).all()  # Single query with JOIN
```

### Network Debugging

#### Timeout Issues

**Debugging Steps:**

```bash
# 1. Test basic connectivity
ping <host>
telnet <host> <port>
nc -zv <host> <port>  # netcat

# 2. Trace route
traceroute <host>
mtr <host>  # Better than traceroute

# 3. DNS resolution
nslookup <host>
dig <host>
host <host>

# 4. Check if port is open
nmap -p <port> <host>

# 5. Monitor network traffic
sudo tcpdump -i any -n host <host>
sudo tcpdump -i any -n port <port>

# 6. Test HTTP endpoints
curl -v --connect-timeout 5 --max-time 10 http://<host>:<port>/health
wget --spider --timeout=10 http://<host>:<port>/health

# 7. Check firewall rules
sudo iptables -L -n
sudo iptables -L -n -t nat

# 8. Check routing
ip route show
netstat -rn
```

**Common Issues:**

```bash
# Issue: DNS resolution slow
# Check DNS servers
cat /etc/resolv.conf

# Test DNS speed
time nslookup google.com
time dig google.com

# Solution: Use faster DNS or add to /etc/hosts
echo "10.0.0.5 myservice.local" | sudo tee -a /etc/hosts

# Issue: Connection timeout
# Check if service is listening
sudo netstat -tlnp | grep <port>
sudo ss -tlnp | grep <port>

# Check if firewall is blocking
sudo iptables -L -n | grep <port>

# Temporarily disable firewall for testing (careful!)
sudo ufw disable

# Issue: Slow connection
# Check latency
ping -c 10 <host>

# Check bandwidth
iperf3 -c <host>  # Run server on host first

# Check for packet loss
ping -c 100 <host> | grep loss
```

#### Service Mesh Issues (Kubernetes)

```bash
# Check service mesh (Istio/Linkerd) if applicable
kubectl get pods -n istio-system
kubectl logs -n istio-system <istio-pod>

# Check sidecar injection
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].name}'
# Should show: app-container, istio-proxy

# Check virtual services
kubectl get virtualservice
kubectl describe virtualservice <vs-name>

# Check destination rules
kubectl get destinationrule
kubectl describe destinationrule <dr-name>

# Debug with istioctl
istioctl analyze
istioctl proxy-status
istioctl proxy-config routes <pod-name>
```

---

## Log Analysis Techniques

### Structured Log Analysis

**Example Log Entries:**

```json
{"timestamp":"2025-10-16T10:15:23.456Z","level":"INFO","service":"model-serving","request_id":"req-123","message":"Prediction request received","model_id":"resnet50","batch_size":32}
{"timestamp":"2025-10-16T10:15:23.567Z","level":"INFO","service":"model-serving","request_id":"req-123","message":"Model loaded","model_id":"resnet50","load_time_ms":45}
{"timestamp":"2025-10-16T10:15:24.678Z","level":"INFO","service":"model-serving","request_id":"req-123","message":"Inference completed","model_id":"resnet50","inference_time_ms":1111,"batch_size":32}
{"timestamp":"2025-10-16T10:15:24.890Z","level":"ERROR","service":"model-serving","request_id":"req-124","message":"Prediction failed","model_id":"bert","error":"CUDA out of memory"}
```

**Analysis Commands:**

```bash
# Extract all ERROR logs
cat app.log | jq 'select(.level == "ERROR")'

# Count errors by type
cat app.log | jq -r 'select(.level == "ERROR") | .error' | sort | uniq -c | sort -rn

# Calculate average inference time
cat app.log | jq -r 'select(.inference_time_ms) | .inference_time_ms' | \
  awk '{sum+=$1; count++} END {print "Average:", sum/count, "ms"}'

# Find slow requests (>1000ms)
cat app.log | jq 'select(.inference_time_ms > 1000)'

# Group by model
cat app.log | jq -r '.model_id' | sort | uniq -c | sort -rn

# Time series analysis (requests per minute)
cat app.log | jq -r '.timestamp' | cut -c1-16 | uniq -c

# Find requests with errors
cat app.log | jq 'select(.request_id) | select(.level == "ERROR") | .request_id' | \
  xargs -I {} grep {} app.log | jq .

# Calculate percentiles
cat app.log | jq -r 'select(.inference_time_ms) | .inference_time_ms' | \
  sort -n | awk '{a[NR]=$1} END {
    print "p50:", a[int(NR*0.5)]
    print "p95:", a[int(NR*0.95)]
    print "p99:", a[int(NR*0.99)]
  }'
```

### Log Correlation

**Tracing requests across services:**

```bash
# Extract all logs for a specific request_id
REQUEST_ID="req-123"
cat app.log | jq "select(.request_id == \"$REQUEST_ID\")"

# Timeline for a request
cat app.log | jq -r "select(.request_id == \"$REQUEST_ID\") | \"\(.timestamp) \(.message)\""

# Find related errors
cat app.log | jq "select(.request_id == \"$REQUEST_ID\") | select(.level == \"ERROR\")"
```

**Kubernetes log aggregation:**

```bash
# Collect logs from all pods
kubectl logs -l app=model-serving --all-containers > all-pods.log

# Analyze aggregated logs
cat all-pods.log | grep ERROR | sort

# Find which pod had the error
kubectl logs -l app=model-serving --all-containers --prefix > all-pods-prefixed.log
cat all-pods-prefixed.log | grep "req-123"
```

### Log Pattern Recognition

**Common Error Patterns:**

```bash
# Out of memory errors
grep -i "out of memory\|oom\|memory error" app.log

# Connection errors
grep -i "connection refused\|connection timeout\|connection reset" app.log

# Authentication errors
grep -i "unauthorized\|authentication failed\|invalid token" app.log

# Rate limiting
grep -i "rate limit\|too many requests\|429" app.log

# Database errors
grep -i "database\|sql\|connection pool" app.log | grep -i "error\|exception"

# GPU errors
grep -i "cuda\|gpu\|nvidia" app.log | grep -i "error\|exception"
```

**Creating alert patterns:**

```bash
# Critical errors requiring immediate attention
ERROR_PATTERNS=(
  "CUDA out of memory"
  "Connection refused"
  "500 Internal Server Error"
  "Database connection pool exhausted"
  "Pod OOMKilled"
)

for pattern in "${ERROR_PATTERNS[@]}"; do
  count=$(grep -c "$pattern" app.log)
  if [ $count -gt 0 ]; then
    echo "ALERT: Found $count occurrences of: $pattern"
  fi
done
```

---

## Performance Debugging

### CPU Profiling

**Using cProfile:**

```python
import cProfile
import pstats

# Profile entire script
cProfile.run('main()', 'profile.stats')

# Analyze results
p = pstats.Stats('profile.stats')
p.strip_dirs()
p.sort_stats('cumulative')
p.print_stats(20)

# Profile specific section
profiler = cProfile.Profile()
profiler.enable()

# Code to profile
for i in range(1000):
    result = expensive_function(data)

profiler.disable()
profiler.print_stats(sort='cumulative')
```

**Using py-spy (production):**

```bash
# Install py-spy
pip install py-spy

# Monitor running process
py-spy top --pid <pid>

# Record flame graph
py-spy record --pid <pid> --output profile.svg --duration 60

# Record with native extensions
py-spy record --pid <pid> --output profile.svg --native --duration 60
```

### Memory Profiling

**Using memory_profiler:**

```python
from memory_profiler import profile

@profile
def process_batch(data):
    # Line-by-line memory usage
    result = preprocess(data)
    features = extract_features(result)
    prediction = model.predict(features)
    return prediction

# Run with:
# python -m memory_profiler script.py
```

**Using tracemalloc:**

```python
import tracemalloc
import linecache

def display_top(snapshot, key_type='lineno', limit=10):
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    print(f"Top {limit} lines:")
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        print(f"#{index}: {frame.filename}:{frame.lineno}: "
              f"{stat.size / 1024:.1f} KiB")
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print(f'    {line}')

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print(f"{len(other)} other: {size / 1024:.1f} KiB")

    total = sum(stat.size for stat in top_stats)
    print(f"Total allocated size: {total / 1024:.1f} KiB")

# Start tracing
tracemalloc.start()

# Your code
process_data()

# Take snapshot
snapshot = tracemalloc.take_snapshot()
display_top(snapshot)

tracemalloc.stop()
```

### I/O Profiling

**Disk I/O:**

```bash
# Monitor disk I/O
iostat -x 1 10

# Per-process I/O
sudo iotop

# Trace file operations
strace -e trace=file -p <pid>

# Trace only open/read/write
strace -e trace=open,read,write -p <pid>
```

**Network I/O:**

```bash
# Monitor network connections
netstat -tunap | grep <pid>

# Monitor bandwidth
iftop -i eth0

# Per-process network usage
nethogs

# Trace network system calls
strace -e trace=network -p <pid>
```

---

## Monitoring-Based Debugging

### Using Prometheus Metrics

**Query Examples:**

```promql
# High error rate
rate(http_requests_total{status=~"5.."}[5m]) > 0.01

# High latency (p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1

# High memory usage
container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9

# High CPU usage
rate(container_cpu_usage_seconds_total[5m]) > 0.8

# GPU memory usage
nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes > 0.9

# Request rate drop
rate(http_requests_total[5m]) < 10
```

**Debugging with Metrics:**

```bash
# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=up'

# Query rate of errors
curl 'http://localhost:9090/api/v1/query?query=rate(http_requests_total{status="500"}[5m])'

# Query range (time series)
curl 'http://localhost:9090/api/v1/query_range?query=rate(http_requests_total[5m])&start=2025-10-16T10:00:00Z&end=2025-10-16T11:00:00Z&step=60s'
```

### Distributed Tracing

**Jaeger Trace Analysis:**

```bash
# Query traces
curl 'http://localhost:16686/api/traces?service=model-serving&limit=100'

# Find slow traces
curl 'http://localhost:16686/api/traces?service=model-serving&minDuration=1s'

# Find traces with errors
curl 'http://localhost:16686/api/traces?service=model-serving&tags={"error":"true"}'
```

**Understanding trace spans:**

```
Trace: request-123 (total: 1250ms)
├─ model-serving: /predict (1250ms)
│  ├─ load-model (50ms)
│  ├─ preprocess (100ms)
│  ├─ inference (1000ms) ← BOTTLENECK
│  └─ postprocess (100ms)
```

---

## Project-Specific Debugging

### Project 01: Model Serving API

#### Common Issues

**Issue 1: Model fails to load**

```bash
# Symptoms
kubectl logs model-serving-pod | grep -i "model\|load\|error"

# Check model file exists
kubectl exec model-serving-pod -- ls -lh /models/

# Check model file integrity
kubectl exec model-serving-pod -- md5sum /models/model.pth

# Check available memory
kubectl exec model-serving-pod -- free -h

# Debug model loading
kubectl exec model-serving-pod -- python -c "
import torch
try:
    model = torch.load('/models/model.pth')
    print('Model loaded successfully')
    print(f'Model size: {sum(p.numel() for p in model.parameters())} parameters')
except Exception as e:
    print(f'Error: {e}')
"
```

**Issue 2: API responds slowly**

```bash
# Profile endpoint
time curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"input": [[1,2,3,4]]}'

# Check if model is compiled
kubectl logs model-serving-pod | grep -i "torch.compile\|jit"

# Check batch size
kubectl logs model-serving-pod | grep -i "batch"

# Monitor during request
kubectl exec model-serving-pod -- python -c "
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Current device: {torch.cuda.current_device() if torch.cuda.is_available() else \"CPU\"}')
"
```

**Issue 3: Health check failing**

```bash
# Test health endpoint
curl -v http://localhost:8080/health

# Check readiness probe configuration
kubectl get pod model-serving-pod -o yaml | grep -A 10 readinessProbe

# Check what health endpoint returns
kubectl exec model-serving-pod -- curl http://localhost:8080/health

# Check application logs
kubectl logs model-serving-pod | tail -50
```

#### Debug Checklist for Project 01

```markdown
- [ ] Model file exists at expected path
- [ ] Model loads without errors
- [ ] API server starts successfully
- [ ] Health endpoint returns 200
- [ ] Predict endpoint accepts requests
- [ ] Predictions are correct (test with known input)
- [ ] Response time is acceptable (<500ms)
- [ ] Memory usage is stable
- [ ] No error logs
- [ ] Prometheus metrics are exposed
```

### Project 02: Multi-Model Serving

#### Common Issues

**Issue 1: Wrong model selected**

```bash
# Check model routing
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"model_id": "resnet50", "input": [[1,2,3]]}'

# Check which models are loaded
kubectl exec model-serving-pod -- python -c "
from src.model_manager import ModelManager
manager = ModelManager()
print('Loaded models:', list(manager.models.keys()))
"

# Check model registry
kubectl exec model-serving-pod -- ls -la /models/

# Check model selection logic
kubectl logs model-serving-pod | grep -i "model_id\|selecting\|routing"
```

**Issue 2: Model caching not working**

```bash
# Check cache hit rate
kubectl logs model-serving-pod | grep -i "cache" | tail -20

# Monitor cache size
kubectl exec model-serving-pod -- python -c "
import sys
sys.path.append('/app')
from src.cache import cache_manager
print(f'Cache size: {len(cache_manager.cache)} entries')
print(f'Cache hits: {cache_manager.hits}')
print(f'Cache misses: {cache_manager.misses}')
print(f'Hit rate: {cache_manager.hits / (cache_manager.hits + cache_manager.misses) * 100:.2f}%')
"

# Check memory usage by cache
kubectl top pod model-serving-pod
```

**Issue 3: Model switching causes delays**

```bash
# Measure model load time
kubectl exec model-serving-pod -- python -c "
import time
import torch

models = ['resnet50', 'vgg16', 'efficientnet']
for model_name in models:
    start = time.time()
    model = torch.load(f'/models/{model_name}.pth')
    elapsed = time.time() - start
    print(f'{model_name}: {elapsed*1000:.2f}ms')
"

# Check if lazy loading is enabled
kubectl logs model-serving-pod | grep -i "lazy\|preload"

# Profile model switching
kubectl logs model-serving-pod | grep "model_id" | \
  awk '{print $NF}' | uniq -c
```

#### Debug Checklist for Project 02

```markdown
- [ ] All models present in /models/
- [ ] Model registry correctly configured
- [ ] Model routing works correctly
- [ ] Cache hit rate >50% under normal load
- [ ] Model switching completes in <100ms
- [ ] No memory leaks during model switching
- [ ] Concurrent requests handled correctly
- [ ] Metrics show per-model statistics
- [ ] Model selection logged correctly
```

### Project 03: GPU-Accelerated Inference

#### Common Issues

**Issue 1: GPU not being used**

```bash
# Check if GPU is available
kubectl exec gpu-model-pod -- nvidia-smi

# Check PyTorch GPU access
kubectl exec gpu-model-pod -- python -c "
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'GPU count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    print(f'GPU name: {torch.cuda.get_device_name(0)}')
"

# Check if model is on GPU
kubectl exec gpu-model-pod -- python -c "
import torch
import sys
sys.path.append('/app')
from src.model import model
print(f'Model device: {next(model.parameters()).device}')
"

# Monitor GPU utilization during inference
kubectl exec gpu-model-pod -- nvidia-smi dmon -s u -c 10

# Check pod GPU resource request
kubectl get pod gpu-model-pod -o yaml | grep -A 5 "nvidia.com/gpu"
```

**Issue 2: GPU memory errors**

```bash
# Check GPU memory usage
kubectl exec gpu-model-pod -- nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Check for OOM in logs
kubectl logs gpu-model-pod | grep -i "cuda.*out of memory\|oom"

# Profile memory usage
kubectl exec gpu-model-pod -- python -c "
import torch
print(f'Allocated: {torch.cuda.memory_allocated() / 1024**3:.2f} GB')
print(f'Reserved: {torch.cuda.memory_reserved() / 1024**3:.2f} GB')
print(f'Max allocated: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB')

# Print per-device memory
for i in range(torch.cuda.device_count()):
    print(f'GPU {i}:')
    print(f'  Total: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB')
    print(f'  Allocated: {torch.cuda.memory_allocated(i) / 1024**3:.2f} GB')
"

# Check batch size
kubectl logs gpu-model-pod | grep -i "batch_size"
```

**Issue 3: Slow GPU inference**

```bash
# Profile GPU operations
kubectl exec gpu-model-pod -- python -c "
import torch
import time

model = load_model()  # Your model loading code
input_data = torch.randn(32, 3, 224, 224).cuda()

# Warmup
for _ in range(10):
    _ = model(input_data)

# Benchmark
torch.cuda.synchronize()
start = time.time()
for _ in range(100):
    output = model(input_data)
torch.cuda.synchronize()
elapsed = time.time() - start
print(f'Average inference time: {elapsed*10:.2f}ms per batch')
print(f'Throughput: {100*32/elapsed:.2f} samples/sec')
"

# Check GPU utilization
kubectl exec gpu-model-pod -- nvidia-smi dmon -s u

# Should see:
# gpu   sm   mem   enc   dec
#   0   95    80     0     0  (Good - high utilization)
#   0   20    15     0     0  (Bad - low utilization)

# Check for CPU-GPU transfers
kubectl logs gpu-model-pod | grep -i "transfer\|cpu\|cuda"

# Profile with PyTorch profiler
kubectl exec gpu-model-pod -- python -c "
import torch
from torch.profiler import profile, ProfilerActivity

with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
    output = model(input_data)

print(prof.key_averages().table(sort_by='cuda_time_total', row_limit=10))
"
```

#### Debug Checklist for Project 03

```markdown
- [ ] GPU is visible (nvidia-smi works)
- [ ] PyTorch detects GPU (torch.cuda.is_available())
- [ ] Model is on GPU (check device)
- [ ] Input tensors moved to GPU
- [ ] GPU utilization >80% during inference
- [ ] No CUDA OOM errors
- [ ] Batch size optimized for GPU memory
- [ ] Mixed precision enabled (if supported)
- [ ] No frequent CPU-GPU transfers
- [ ] GPU memory released after inference
```

---

## Real-World Debugging Scenarios

### Scenario 1: Intermittent 504 Timeouts

**Problem:**
API randomly returns 504 Gateway Timeout errors, affecting ~5% of requests.

**Investigation:**

```bash
# Step 1: Check error pattern
kubectl logs -l app=model-serving | grep "504\|timeout" | head -20

# Step 2: Check if specific to certain requests
kubectl logs -l app=model-serving | grep "504" | jq '.request_id' | sort | uniq

# Step 3: Check resource usage during timeouts
kubectl top pods
# If high: resource exhaustion
# If normal: likely network or dependency issue

# Step 4: Check latency metrics
curl http://localhost:9090/api/v1/query?query='histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))'

# Step 5: Check for slow dependencies
kubectl logs -l app=model-serving | jq 'select(.duration_ms > 1000)'

# Step 6: Check network connectivity
kubectl exec model-serving-pod -- curl -v http://dependency-service/health
```

**Root Cause:**
Model loading timeout when cache is cold.

**Solution:**

```python
# Add timeout and retry logic
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def load_model_with_retry(model_path):
    try:
        return torch.load(model_path, weights_only=True)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

# Increase timeout in deployment
# readinessProbe:
#   httpGet:
#     path: /health
#     port: 8080
#   initialDelaySeconds: 60  # Increased from 30
#   timeoutSeconds: 10       # Increased from 5
```

### Scenario 2: Memory Leak in Production

**Problem:**
Pod memory usage grows continuously, eventually causing OOMKill.

**Investigation:**

```bash
# Step 1: Monitor memory over time
watch -n 5 'kubectl top pod model-serving-pod'

# Step 2: Check for OOMKill events
kubectl describe pod model-serving-pod | grep -A 5 "Last State"

# Step 3: Get memory allocation patterns
kubectl exec model-serving-pod -- python -c "
import tracemalloc
import gc

tracemalloc.start()

# Simulate some requests
for i in range(100):
    result = predict(data)

current, peak = tracemalloc.get_traced_memory()
print(f'Current: {current / 1024**2:.2f} MB')
print(f'Peak: {peak / 1024**2:.2f} MB')

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
"

# Step 4: Check for unreleased resources
kubectl exec model-serving-pod -- python -c "
import gc
print(f'Garbage objects: {len(gc.garbage)}')
print(f'Collections: {gc.get_count()}')
"
```

**Root Cause:**
Cache growing without bounds, storing every unique request.

**Solution:**

```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, maxsize=1000):
        self.cache = OrderedDict()
        self.maxsize = maxsize

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.maxsize:
                self.cache.popitem(last=False)
        self.cache[key] = value

# Replace unbounded dict with LRU cache
# cache = {}  # Old
cache = LRUCache(maxsize=1000)  # New
```

### Scenario 3: Database Connection Pool Exhausted

**Problem:**
Application fails with "connection pool exhausted" errors during high traffic.

**Investigation:**

```bash
# Step 1: Check error frequency
kubectl logs model-serving-pod | grep -c "connection pool exhausted"

# Step 2: Check current connections
kubectl exec postgres-pod -- psql -U postgres -c "
SELECT count(*) as total_connections,
       state,
       wait_event_type
FROM pg_stat_activity
GROUP BY state, wait_event_type;
"

# Step 3: Check connection pool configuration
kubectl exec model-serving-pod -- python -c "
from src.database import engine
print(f'Pool size: {engine.pool.size()}')
print(f'Checked out: {engine.pool.checkedout()}')
print(f'Overflow: {engine.pool.overflow()}')
"

# Step 4: Check for connection leaks
kubectl exec model-serving-pod -- python -c "
from src.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
connections = inspector.get_pool_status()
print(connections)
"
```

**Root Cause:**
Connections not being returned to pool due to missing context manager.

**Solution:**

```python
# Bad: Connection not returned
def get_prediction(pred_id):
    conn = engine.connect()
    result = conn.execute('SELECT * FROM predictions WHERE id = %s', pred_id)
    return result.fetchone()
    # Connection never closed!

# Good: Use context manager
def get_prediction(pred_id):
    with engine.connect() as conn:
        result = conn.execute('SELECT * FROM predictions WHERE id = %s', pred_id)
        return result.fetchone()
    # Connection automatically returned to pool

# Even better: Use ORM session
from sqlalchemy.orm import Session

def get_prediction(pred_id):
    with Session(engine) as session:
        return session.query(Prediction).filter_by(id=pred_id).first()
```

### Scenario 4: GPU Underutilization

**Problem:**
GPU utilization is only 30% despite high request load.

**Investigation:**

```bash
# Step 1: Monitor GPU utilization
kubectl exec gpu-pod -- nvidia-smi dmon -s u -c 20

# Step 2: Check batch size
kubectl logs gpu-pod | grep -i "batch_size"

# Step 3: Profile GPU operations
kubectl exec gpu-pod -- python -c "
import torch
from torch.profiler import profile, ProfilerActivity

with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
    for _ in range(10):
        output = model(input_data)

print(prof.key_averages().table(sort_by='cuda_time_total'))

# Look for:
# - High CPU time (data transfer overhead)
# - Small kernel execution time (batch too small)
# - Frequent cudaDeviceSynchronize (unnecessary sync)
"

# Step 4: Check for CPU bottlenecks
kubectl exec gpu-pod -- top -b -n 1 | head -20
```

**Root Cause:**
Batch size too small (1) and synchronous processing.

**Solution:**

```python
# Bad: Process one at a time
for request in requests:
    input_tensor = preprocess(request).to('cuda')
    output = model(input_tensor)
    result = postprocess(output.cpu())
    results.append(result)

# Good: Batch processing
batch_size = 32
batches = [requests[i:i+batch_size] for i in range(0, len(requests), batch_size)]

results = []
for batch in batches:
    # Preprocess on CPU
    inputs = torch.stack([preprocess(req) for req in batch])

    # Move to GPU once
    inputs = inputs.to('cuda', non_blocking=True)

    # Inference with no_grad
    with torch.no_grad():
        outputs = model(inputs)

    # Move back to CPU for postprocessing
    outputs = outputs.cpu()

    # Postprocess
    batch_results = [postprocess(out) for out in outputs]
    results.extend(batch_results)
```

---

## Debugging Checklists

### Quick Diagnostic Checklist

```markdown
## Initial Assessment
- [ ] What is the symptom?
- [ ] When did it start?
- [ ] Is it consistent or intermittent?
- [ ] What changed recently?
- [ ] What is the impact?

## Gather Information
- [ ] Check application logs
- [ ] Check system metrics (CPU, memory, disk, network)
- [ ] Check error rates
- [ ] Check recent deployments
- [ ] Check dependencies status

## Container/Pod Health
- [ ] Are pods running?
- [ ] Are containers healthy?
- [ ] Are readiness/liveness probes passing?
- [ ] Are there recent restarts?
- [ ] Are resources sufficient?

## Network Connectivity
- [ ] Can pods communicate?
- [ ] Are services accessible?
- [ ] Is DNS resolving?
- [ ] Are ports open?
- [ ] Are network policies allowing traffic?

## Application-Specific
- [ ] Is configuration correct?
- [ ] Are environment variables set?
- [ ] Are secrets accessible?
- [ ] Is database accessible?
- [ ] Are external dependencies available?
```

### Pre-Deployment Checklist

```markdown
## Code Quality
- [ ] All tests passing
- [ ] Code reviewed
- [ ] No security vulnerabilities
- [ ] Dependencies up to date
- [ ] Linter checks pass

## Configuration
- [ ] Environment variables documented
- [ ] Secrets created in target environment
- [ ] ConfigMaps updated
- [ ] Resource limits appropriate
- [ ] Probes configured correctly

## Docker Image
- [ ] Image builds successfully
- [ ] Image size reasonable (<1GB if possible)
- [ ] No secrets in image
- [ ] Security scan passed
- [ ] Image tagged correctly

## Kubernetes Resources
- [ ] Deployment YAML valid
- [ ] Service YAML valid
- [ ] Ingress configured (if needed)
- [ ] Labels and selectors match
- [ ] Resource requests/limits set
- [ ] Probes configured

## Testing
- [ ] Tested in dev environment
- [ ] Tested in staging environment
- [ ] Load tested (if applicable)
- [ ] Rollback plan ready
- [ ] Monitoring dashboard ready
```

### Post-Incident Checklist

```markdown
## Immediate Response
- [ ] Incident detected and logged
- [ ] Severity assessed
- [ ] Team notified
- [ ] Mitigation applied
- [ ] Service restored

## Investigation
- [ ] Root cause identified
- [ ] Timeline documented
- [ ] Logs collected
- [ ] Metrics analyzed
- [ ] Related incidents checked

## Resolution
- [ ] Permanent fix applied
- [ ] Fix tested
- [ ] Deployed to production
- [ ] Monitoring confirms resolution
- [ ] Documentation updated

## Prevention
- [ ] Monitoring gaps addressed
- [ ] Alerting rules updated
- [ ] Runbooks created/updated
- [ ] Team trained
- [ ] Postmortem completed
```

---

## Advanced Debugging Techniques

### Using eBPF for Deep Inspection

```bash
# Install bpftrace
sudo apt-get install bpftrace

# Trace all system calls
sudo bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }'

# Trace file opens
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_openat { printf("%s %s\n", comm, str(args->filename)); }'

# Trace network connections
sudo bpftrace -e 'kprobe:tcp_connect { printf("Connection from %d\n", pid); }'

# Trace memory allocations
sudo bpftrace -e 'tracepoint:kmem:kmalloc { @[comm] = sum(args->bytes_req); }'
```

### Core Dump Analysis

```bash
# Enable core dumps
ulimit -c unlimited
echo "core.%e.%p" | sudo tee /proc/sys/kernel/core_pattern

# Analyze core dump with gdb
gdb /path/to/binary /path/to/core

# Inside gdb:
(gdb) bt              # Backtrace
(gdb) frame <n>       # Switch to frame
(gdb) info locals     # Show local variables
(gdb) print <var>     # Print variable
(gdb) disassemble     # Show assembly
```

### Time Travel Debugging (rr)

```bash
# Install rr
sudo apt-get install rr

# Record execution
rr record python app.py

# Replay
rr replay

# Inside replay:
(gdb) continue        # Run forward
(gdb) reverse-continue  # Run backward
(gdb) reverse-step    # Step backward
(gdb) watch <var>     # Watch variable changes
```

### Distributed Debugging

```bash
# Attach to multiple pods simultaneously
pods=$(kubectl get pods -l app=model-serving -o name)
for pod in $pods; do
    kubectl logs $pod -f &
done
wait

# Run command in all pods
kubectl exec -l app=model-serving -- curl http://localhost:8080/health

# Debug with service mesh (Istio)
istioctl dashboard envoy <pod-name>
istioctl analyze
```

---

## Resources and References

### Official Documentation

- **Kubernetes Debugging**: https://kubernetes.io/docs/tasks/debug/
- **Docker Debugging**: https://docs.docker.com/config/containers/troubleshoot/
- **Python Debugging**: https://docs.python.org/3/library/debug.html
- **PyTorch Debugging**: https://pytorch.org/docs/stable/notes/debugging.html
- **PostgreSQL Troubleshooting**: https://www.postgresql.org/docs/current/troubleshooting.html

### Tools

- **Kubernetes Debugging Tools**:
  - kubectl: https://kubernetes.io/docs/reference/kubectl/
  - stern: https://github.com/stern/stern
  - kubectx/kubens: https://github.com/ahmetb/kubectx
  - k9s: https://k9scli.io/

- **Python Debugging Tools**:
  - pdb: https://docs.python.org/3/library/pdb.html
  - ipdb: https://github.com/gotcha/ipdb
  - pudb: https://github.com/inducer/pudb
  - py-spy: https://github.com/benfred/py-spy

- **Profiling Tools**:
  - cProfile: https://docs.python.org/3/library/profile.html
  - line_profiler: https://github.com/pyutils/line_profiler
  - memory_profiler: https://github.com/pythonprofilers/memory_profiler
  - py-spy: https://github.com/benfred/py-spy

- **Network Debugging**:
  - tcpdump: https://www.tcpdump.org/
  - wireshark: https://www.wireshark.org/
  - mtr: https://github.com/traviscross/mtr
  - netshoot: https://github.com/nicolaka/netshoot

### Books

- "The Art of Debugging with GDB, DDD, and Eclipse"
- "Systems Performance: Enterprise and the Cloud" by Brendan Gregg
- "Debugging: The 9 Indispensable Rules for Finding Even the Most Elusive Software and Hardware Problems" by David J. Agans

### Community Resources

- **Stack Overflow**: https://stackoverflow.com/questions/tagged/debugging
- **Kubernetes Slack**: https://kubernetes.slack.com/
- **PyTorch Forums**: https://discuss.pytorch.org/
- **Reddit**: r/kubernetes, r/docker, r/python

---

## Pro Tips

1. **Always start with logs**: 90% of issues can be diagnosed from logs
2. **Reproduce consistently**: Can't fix what you can't reproduce
3. **Isolate variables**: Change one thing at a time
4. **Document everything**: Future you will thank present you
5. **Use version control**: Git bisect is your friend
6. **Automate diagnostics**: Scripts save time and reduce errors
7. **Learn the tools**: Time invested in learning tools pays dividends
8. **Ask for help**: Fresh eyes see new patterns
9. **Keep learning**: Technology evolves, so should your skills
10. **Stay calm**: Panic clouds judgment

---

## Common Pitfalls

1. **Assuming root cause**: Test your hypothesis
2. **Not reading error messages**: They usually tell you what's wrong
3. **Debugging in production**: Use staging when possible
4. **Not checking recent changes**: Start with what changed
5. **Ignoring resource limits**: Memory and CPU matter
6. **Not using version pinning**: "Works on my machine" syndrome
7. **Skipping logs**: They're there for a reason
8. **Over-complicating**: Simple explanations are often correct
9. **Not documenting**: You'll encounter this again
10. **Giving up too soon**: Persistence pays off

---

**Remember**: Debugging is a skill that improves with practice. Every bug you solve makes you better at solving the next one.

**Happy Debugging!**
