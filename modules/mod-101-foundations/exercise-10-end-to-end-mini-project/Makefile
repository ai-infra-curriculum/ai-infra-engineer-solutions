.PHONY: help up down image test load dashboard

CLUSTER_NAME ?= mini-platform
IMAGE_TAG    ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

up: cluster ingress prometheus image deploy ## Bring up the full stack

cluster: ## Create kind cluster
	kind create cluster --name $(CLUSTER_NAME) --config infra/kind-config.yaml || true
	kubectl wait --for=condition=Ready node --all --timeout=2m

ingress: ## Install NGINX Ingress Controller
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/kind/deploy.yaml
	kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=controller -n ingress-nginx --timeout=2m

prometheus: ## Install kube-prometheus-stack
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
	helm repo update
	helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
		--namespace monitoring --create-namespace \
		--set grafana.enabled=true --set grafana.adminPassword=admin \
		--set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
		--wait

test: ## Run app tests
	cd ../exercise-08-production-model-serving && pytest tests/

image: test ## Build + load app image
	cd ../exercise-08-production-model-serving && docker build -t iris-api:$(IMAGE_TAG) .
	kind load docker-image iris-api:$(IMAGE_TAG) --name $(CLUSTER_NAME)

deploy: ## Deploy app + ServiceMonitor
	sed 's/IMAGE_TAG/$(IMAGE_TAG)/g' deploy/deployment.yaml | kubectl apply -f -
	kubectl apply -f deploy/service.yaml -f deploy/hpa.yaml -f deploy/servicemonitor.yaml
	kubectl rollout status deployment/iris-api --timeout=2m
	@echo "App:        http://localhost:8080"
	@echo "Grafana:    http://localhost:3000  (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &
	kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &

load: ## Run locust load test
	cd loadtest && locust -f locustfile.py --headless -u 50 -r 5 -t 30s -H http://localhost:8080

dashboard: ## Open Grafana
	open http://localhost:3000 || xdg-open http://localhost:3000

down: ## Destroy cluster + cleanup
	-pkill -f "port-forward" 2>/dev/null
	kind delete cluster --name $(CLUSTER_NAME)
