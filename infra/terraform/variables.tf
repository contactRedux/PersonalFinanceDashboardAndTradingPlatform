variable "aws_region" {
  description = "AWS region to deploy resources."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (e.g. production, staging)."
  type        = string
  default     = "production"
}

variable "app_name" {
  description = "Application name prefix for all resources."
  type        = string
  default     = "quantnexus"
}

variable "backend_image" {
  description = "Full ECR image URI for the backend container."
  type        = string
}

variable "frontend_image" {
  description = "Full ECR image URI for the frontend container."
  type        = string
}

variable "database_url_secret_arn" {
  description = "AWS Secrets Manager ARN for DATABASE_URL."
  type        = string
}

variable "redis_url_secret_arn" {
  description = "AWS Secrets Manager ARN for REDIS_URL."
  type        = string
}

variable "jwt_secret_arn" {
  description = "AWS Secrets Manager ARN for JWT_SECRET_KEY."
  type        = string
}
