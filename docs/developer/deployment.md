# Deployment Guide

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| kubectl | 1.28+ | https://kubernetes.io/docs/tasks/tools/ |
| Terraform | 1.6+ | https://developer.hashicorp.com/terraform/install |
| AWS CLI | 2.x | https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html |

---

## Local Development (docker-compose)

```bash
# Copy environment template
cp .env.example .env
# Edit .env and fill in API keys

# Start the full local stack (Postgres, Redis, backend, frontend)
make dev

# Or start only the backend
make dev-backend

# Or only the frontend
make dev-frontend
```

The API will be available at http://localhost:8000 and the UI at http://localhost:3000.

---

## Kubernetes Deployment

### 1. Create the namespace first

```bash
kubectl apply -f infra/k8s/namespace.yaml
```

### 2. Populate secrets

Edit `infra/k8s/secrets.yaml` — replace the placeholder base64 values with real
ones (base64-encoded). **Never commit real secrets.**

Alternatively, pull directly from AWS Secrets Manager:

```bash
aws secretsmanager get-secret-value --secret-id quantnexus/prod \
  --query SecretString --output text | base64
```

```bash
kubectl apply -f infra/k8s/secrets.yaml
```

### 3. Apply remaining manifests

```bash
kubectl apply -f infra/k8s/
```

Or use the Makefile target:

```bash
make k8s-deploy
```

### 4. Verify rollout

```bash
kubectl rollout status deployment/backend  -n quantnexus
kubectl rollout status deployment/frontend -n quantnexus
kubectl get pods -n quantnexus
```

---

## Terraform (AWS ECS Fargate)

### 1. Authenticate with AWS

```bash
aws configure           # or use an IAM role / SSO profile
aws sts get-caller-identity   # confirm credentials
```

### 2. Create a `terraform.tfvars` file

```hcl
# infra/terraform/terraform.tfvars — never commit this file
aws_region              = "us-east-1"
environment             = "production"
backend_image           = "123456789.dkr.ecr.us-east-1.amazonaws.com/quantnexus-backend:latest"
frontend_image          = "123456789.dkr.ecr.us-east-1.amazonaws.com/quantnexus-frontend:latest"
database_url_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:quantnexus/db-url"
redis_url_secret_arn    = "arn:aws:secretsmanager:us-east-1:123456789:secret:quantnexus/redis-url"
jwt_secret_arn          = "arn:aws:secretsmanager:us-east-1:123456789:secret:quantnexus/jwt-secret"
```

### 3. Initialise, plan, and apply

```bash
make tf-plan    # preview changes
make tf-apply   # deploy to AWS
```

Or run directly:

```bash
cd infra/terraform
terraform init
terraform plan  -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL async DSN (`postgresql+asyncpg://...`) |
| `DATABASE_SYNC_URL` | Yes | Sync DSN for Alembic migrations |
| `REDIS_URL` | Yes | Redis connection string (`redis://...`) |
| `JWT_SECRET_KEY` | Yes | ≥32-char secret for JWT signing |
| `ALPACA_API_KEY` | No | Alpaca Markets API key (live/paper trading) |
| `ALPACA_API_SECRET` | No | Alpaca Markets API secret |
| `OPENAI_API_KEY` | No | OpenAI key (AI assistant features) |
| `FRED_API_KEY` | No | FRED API key (macro indicators) |
| `POLYGON_API_KEY` | No | Polygon.io key (VIX, options data) |
| `MARKET_DATA_PROVIDER` | No | `alpaca` \| `yfinance` (default: `alpaca`) |
| `APP_ENV` | No | `development` \| `production` \| `test` |
| `FRONTEND_URL` | No | URL of the Next.js frontend (CORS) |
