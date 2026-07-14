output "backend_url" {
  description = "Public URL for the backend ALB target."
  value       = "http://${aws_lb.main.dns_name}/api"
}

output "frontend_url" {
  description = "Public URL for the frontend ALB target."
  value       = "http://${aws_lb.main.dns_name}"
}

output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}
