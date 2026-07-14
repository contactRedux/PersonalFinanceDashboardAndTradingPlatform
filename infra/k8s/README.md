# infra/k8s — Kubernetes Deployment

## What is this folder?

**Kubernetes** (often abbreviated K8s) is a system for running and managing containerized applications in production. Think of it like an air traffic controller for your Docker containers — it decides where each container runs, restarts them if they crash, scales up more copies when traffic is high, and routes requests to healthy instances.

This folder contains **YAML manifest files** — declarative configuration files that tell Kubernetes what to run and how. You apply them with `kubectl apply -f infra/k8s/` and Kubernetes figures out how to make reality match your specification.

---

## Files

| File | What it creates |
|---|---|
| `namespace.yaml` | A `quantnexus` namespace — an isolated partition of the cluster for this app's resources |
| `secrets.yaml` | API keys and passwords stored securely in Kubernetes Secrets (base64-encoded, **never commit real values**) |
| `backend.yaml` | The FastAPI server Deployment + Service + HorizontalPodAutoscaler |
| `frontend.yaml` | The Next.js Deployment + Service |
| `celery-worker.yaml` | The Celery background job worker Deployment |
| `redis.yaml` | A Redis Deployment + Service for in-cluster caching |
| `ingress.yaml` | An NGINX Ingress controller that routes external HTTP/S traffic to the right Service |
| `timescaledb.yaml` | A TimescaleDB StatefulSet + Service + PVC (10Gi) for time-series market data storage |
| `mongodb.yaml` | A MongoDB StatefulSet + Service + PVC (10Gi) for document storage (trade journal, news, etc.) |
| `monitoring.yaml` | Prometheus Deployment + Service + ConfigMap and Grafana Deployment + Service for observability |
| `hpa.yaml` | HorizontalPodAutoscalers for `backend` (2–10 replicas) and `celery-worker` (1–5 replicas) |

---

## Key Concepts Explained

**Deployment** — Tells Kubernetes to keep N identical copies (replicas) of a container running. If one crashes, K8s automatically starts a replacement. `backend.yaml` runs 2 replicas by default.

**Service** — An internal load balancer and DNS name for a set of pods. Other containers talk to `backend:8000` instead of a specific IP address — K8s routes the request to any healthy pod.

**HorizontalPodAutoscaler (HPA)** — Automatically adds or removes replicas based on CPU usage. `backend.yaml` defines min 2 / max 10 replicas, scaling up when average CPU exceeds 70%.

**Ingress** — The front door for external traffic. `ingress.yaml` routes `api.quantnexus.io/api/` to the backend Service and `*.quantnexus.io/` to the frontend Service.

**Secrets** — Kubernetes Secrets store sensitive data (API keys, database passwords) separately from application code. They're mounted as environment variables in the container. Always replace the placeholder base64 values before deploying.

---

## How to Deploy

```bash
# 1. Apply the namespace first
kubectl apply -f infra/k8s/namespace.yaml

# 2. Create secrets (edit secrets.yaml first with real base64-encoded values)
kubectl apply -f infra/k8s/secrets.yaml

# 3. Apply everything else
kubectl apply -f infra/k8s/

# 4. Check that all pods started correctly
kubectl get pods -n quantnexus

# 5. Check the backend is healthy
kubectl rollout status deployment/backend -n quantnexus
```

Or use the Makefile shortcut: `make k8s-deploy`

---

## Reading the backend.yaml

The backend deployment (`backend.yaml`) configures:
- **2 replicas** (always 2 copies running for high availability)
- **Readiness probe** — Kubernetes checks `GET /health` every 5 seconds; only routes traffic to pods that return 200
- **Resource limits** — each pod gets 0.25 CPU cores and 512MB RAM minimum, up to 1 CPU core and 1GB RAM maximum
- **HPA** — scales to up to 10 pods if average CPU exceeds 70%

---

## How does this connect to the rest of the app?

- The container images referenced here (`quantnexus-backend:latest`, `quantnexus-frontend:latest`) are built from `backend/Dockerfile` and `frontend/Dockerfile`
- Secrets referenced in these manifests correspond to the environment variables in `.env.example`
- The Terraform configs in `infra/terraform/` can provision the AWS EKS cluster (Elastic Kubernetes Service) that these manifests deploy into
- In development, `docker-compose.yml` at the project root serves the same role — it's the simpler single-machine equivalent of these Kubernetes configs
