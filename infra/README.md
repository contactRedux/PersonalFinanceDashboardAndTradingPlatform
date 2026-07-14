# infra/ — Infrastructure and Deployment

## What is this folder?

This folder contains everything needed to *deploy* QuantNexus — the configuration files that tell cloud providers, container orchestrators, and monitoring tools how to run the platform. If the application code is the blueprints for a building, this folder is the construction equipment and site planning.

---

## Subfolders

| Folder | What it manages |
|---|---|
| [`docker/`](docker/) | Docker build helpers: Nginx config, TimescaleDB initialization SQL |
| [`k8s/`](k8s/) | Kubernetes manifests for production container orchestration |
| [`terraform/`](terraform/) | Terraform files for deploying to AWS ECS Fargate (cloud) |
| [`monitoring/`](monitoring/) | Prometheus scrape config and Grafana dashboard definitions |

---

## Deployment Options

### Option 1: Local Development (`docker-compose.yml` at project root)
The fastest path. One command starts 9 services:
```bash
docker compose up -d
```
Runs everything on your laptop. Not suitable for production (no TLS, no scaling).

### Option 2: Kubernetes (`infra/k8s/`)
For teams or self-hosted production deployments. Requires a Kubernetes cluster (local with minikube, or cloud-managed like EKS/GKE).

```bash
kubectl apply -f infra/k8s/
# or shortcut:
make k8s-deploy
```

### Option 3: AWS ECS Fargate via Terraform (`infra/terraform/`)
For fully managed cloud deployment on AWS. Terraform handles provisioning the load balancer, ECS cluster, task definitions, and networking.

```bash
make tf-plan   # Preview what will be created
make tf-apply  # Actually create it
```

---

## Monitoring Stack

QuantNexus ships with a built-in monitoring stack:

- **Prometheus** — Collects metrics from the FastAPI backend (`/metrics` endpoint, exposed via `prometheus-fastapi-instrumentator`). Runs at `http://localhost:9090`.
- **Grafana** — Visualizes Prometheus metrics in pre-built dashboards. Runs at `http://localhost:3001` (admin / changeme by default — **change this in production**).

Key metrics collected: HTTP request count and latency by endpoint, WebSocket connection count, Celery task queue depth, database query time.

---

## How does this connect to the rest of the app?

- `infra/docker/nginx.conf` — The Nginx reverse proxy routes `/api/` to the FastAPI backend and everything else to the Next.js frontend
- `infra/docker/init-timescaledb.sql` — Runs on first database startup to create the TimescaleDB extension and hypertables
- `infra/k8s/` — Contains separate Deployments for backend, frontend, and celery-worker (see `k8s/README.md`)
- `infra/terraform/` — Creates the AWS infrastructure that the Kubernetes manifests deploy into (see `terraform/README.md`)
- `infra/monitoring/prometheus.yml` — Configures Prometheus to scrape the backend's `/metrics` endpoint every 15 seconds
