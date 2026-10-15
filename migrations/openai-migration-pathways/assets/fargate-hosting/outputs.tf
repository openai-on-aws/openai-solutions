output "vpc_id" { value = aws_vpc.main.id }
output "application_subnets" { value = [for subnet in aws_subnet.application : subnet.id] }
output "data_subnets" { value = [for subnet in aws_subnet.data : subnet.id] }
output "cluster_name" { value = aws_ecs_cluster.main.name }
output "service_names" { value = { for key, service in aws_ecs_service.application : key => service.name } }
output "service_dns_names" { value = { for key in keys(var.workloads) : key => "${key}.${aws_service_discovery_private_dns_namespace.main.name}" } }
output "https_endpoints" { value = { for key, w in local.http_workloads : key => "https://${w.hostname}" } }
output "task_role_arns" { value = { for key, role in aws_iam_role.task : key => role.arn } }
output "execution_role_arns" { value = { for key, role in aws_iam_role.execution : key => role.arn } }
output "redis_endpoint" { value = try(aws_elasticache_replication_group.main[0].primary_endpoint_address, null) }
output "authentication_bindings" {
  description = "One identity boundary shared by the authenticated frontend and API routes."
  value = { for key, w in local.authenticated_workloads : key => {
    ALB_SIGNER_ARN      = aws_lb.main.arn
    OIDC_ISSUER         = local.cognito_issuer
    OIDC_CLIENT_ID      = var.cognito_auth.user_pool_client_id
    APPLICATION_ORIGINS = jsonencode(["https://${w.hostname}"])
    callback_url        = "https://${w.hostname}/oauth2/idpresponse"
  } }
}
