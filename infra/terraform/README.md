# infra/terraform — AWS Deployment with Terraform

## What is this folder?

**Terraform** is a tool that lets you describe cloud infrastructure as code — instead of clicking through the AWS console to create servers, databases, and load balancers, you write configuration files and Terraform creates everything automatically.

Think of Terraform like an architect's blueprint: you describe *what* you want (a load balancer, two app servers, a Redis cache), and Terraform builds it on AWS, tracks what was created, and can update or tear it all down in one command.

This folder deploys QuantNexus to **AWS ECS Fargate** — Amazon's serverless container platform. Fargate runs your Docker containers in the cloud without you managing any virtual machines directly.

---

## Files

| File | What it configures |
|---|---|
| `main.tf` | AWS provider settings and the ECS Cluster definition |
| `ecs.tf` | ECS Task Definitions and Services — how containers run (CPU, memory, environment variables from AWS Secrets Manager) |
| `alb.tf` | ALB (Application Load Balancer — the cloud-based reverse proxy that distributes traffic) and HTTPS listener with TLS certificate |
| `variables.tf` | All configurable inputs: AWS region, environment name, container image URIs, Secrets Manager ARNs |
| `outputs.tf` | Values printed after `terraform apply`: the load balancer DNS name, cluster ARN, etc. |

---

## Prerequisites

| Tool | Minimum | Install |
|---|---|---|
| Terraform | ≥ 1.6 | https://developer.hashicorp.com/terraform/install |
| AWS CLI | 2.x | https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html |
| Docker | any | Container images must be pushed to ECR before deploying |

---

## Deployment Steps

```bash
# 1. Authenticate with AWS
aws configure
aws sts get-caller-identity  # confirm credentials are working

# 2. Create a terraform.tfvars file (never commit this file)
# infra/terraform/terraform.tfvars:
# aws_region             = "us-east-1"
# environment            = "production"
# backend_image          = "123456789.dkr.ecr.us-east-1.amazonaws.com/quantnexus-backend:latest"
# frontend_image         = "123456789.dkr.ecr.us-east-1.amazonaws.com/quantnexus-frontend:latest"
# database_url_secret_arn = "arn:aws:secretsmanager:..."
# redis_url_secret_arn    = "arn:aws:secretsmanager:..."
# jwt_secret_arn          = "arn:aws:secretsmanager:..."

# 3. Preview what will be created (safe — doesn't change anything)
make tf-plan

# 4. Apply the changes to AWS (this costs money!)
make tf-apply
```

---

## What Gets Created on AWS

After `terraform apply`, you'll have:

- **ECS Cluster** — The cluster that manages all containers (backend, frontend, celery worker)
- **ECS Task Definitions** — Blueprints for each container: which Docker image, how much CPU/RAM, which environment variables from Secrets Manager
- **ECS Services** — Keep the specified number of tasks running; replace failed tasks automatically
- **Application Load Balancer** — Routes HTTPS traffic from the internet to the right ECS service
- **HTTPS Listener** — TLS termination so traffic is encrypted between users and the load balancer

Secrets (API keys, database credentials) are stored in **AWS Secrets Manager** and injected into containers at startup — they never appear in the Terraform files or container images.

---

## Cost Estimate

Running the default configuration (2 backend tasks + 1 frontend + 1 celery worker) on Fargate in `us-east-1` costs approximately **$50-100/month** depending on traffic. You can reduce costs by:
- Using smaller task sizes during development
- Setting `desired_count = 0` on non-critical services when not in use

---

## Important Security Notes

- **Never commit `terraform.tfvars`** — it contains ARNs pointing to real secrets
- **Never put actual API keys in `.tf` files** — always use Secrets Manager ARNs
- Run `terraform plan` before `terraform apply` to review changes
- Use separate AWS accounts for `staging` and `production` environments

---

## How does this connect to the rest of the app?

- The Docker images deployed here are built from `backend/Dockerfile` and `frontend/Dockerfile`
- Environment variables referenced in `ecs.tf` correspond to the variables documented in `.env.example`
- The Kubernetes manifests in `infra/k8s/` serve the same purpose for K8s-based deployments
- After deploying, Prometheus scraping and Grafana dashboards in `infra/monitoring/` can be configured to point at the production endpoints
