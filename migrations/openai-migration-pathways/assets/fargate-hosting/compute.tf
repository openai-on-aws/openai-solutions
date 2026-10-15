resource "aws_ecs_cluster" "main" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
resource "aws_cloudwatch_log_group" "application" {
  for_each          = var.workloads
  name              = "/${var.name}/${each.key}"
  retention_in_days = var.logs_retention_days
}
resource "aws_iam_role" "execution" {
  for_each           = var.workloads
  name               = "${var.name}-${each.key}-${substr(sha256(var.region), 0, 8)}-exec"
  assume_role_policy = local.task_trust
}
resource "aws_iam_role" "task" {
  for_each           = var.workloads
  name               = "${var.name}-${each.key}-${substr(sha256(var.region), 0, 8)}-task"
  assume_role_policy = local.task_trust
}
resource "aws_iam_role_policy" "execution" {
  for_each = var.workloads
  role     = aws_iam_role.execution[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"], Resource = local.ecr_repositories[each.key] },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.application[each.key].arn}:*" }
      ], length(each.value.secrets) == 0 ? [] : [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = values(each.value.secrets) }
      ], length(each.value.secrets_kms_key_arns) == 0 ? [] : [
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = each.value.secrets_kms_key_arns, Condition = { StringEquals = { "kms:ViaService" = "secretsmanager.${var.region}.amazonaws.com" } } }
    ])
  })
}
resource "aws_iam_role_policy" "task" {
  for_each = { for key, w in var.workloads : key => w if w.task_policy_json != null }
  role     = aws_iam_role.task[each.key].id
  policy   = each.value.task_policy_json
}
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.name}.internal"
  vpc  = aws_vpc.main.id
}
resource "aws_service_discovery_service" "application" {
  for_each = var.workloads
  name     = each.key
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config { failure_threshold = 1 }
}
resource "aws_ecs_task_definition" "application" {
  for_each                 = var.workloads
  family                   = "${var.name}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(each.value.cpu)
  memory                   = tostring(each.value.memory)
  execution_role_arn       = aws_iam_role.execution[each.key].arn
  task_role_arn            = aws_iam_role.task[each.key].arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = each.value.cpu_architecture
  }
  volume { name = "scratch" }
  container_definitions = jsonencode([{
    name                   = "app"
    image                  = each.value.image
    essential              = true
    user                   = each.value.user
    readonlyRootFilesystem = true
    stopTimeout            = 120
    linuxParameters        = { initProcessEnabled = true }
    mountPoints            = [{ sourceVolume = "scratch", containerPath = "/tmp", readOnly = false }]
    portMappings           = [{ containerPort = each.value.port, protocol = "tcp" }]
    environment = concat(
      [{ name = "AWS_REGION", value = var.region }, { name = "AWS_ACCOUNT_ID", value = var.account_id }],
      [for name, value in each.value.environment : { name = name, value = value }],
      each.value.authentication_mode != "none" ? [
        { name = "ALB_SIGNER_ARN", value = aws_lb.main.arn },
        { name = "OIDC_ISSUER", value = local.cognito_issuer },
        { name = "OIDC_CLIENT_ID", value = var.cognito_auth.user_pool_client_id },
        { name = "APPLICATION_ORIGINS", value = jsonencode(["https://${each.value.hostname}"]) }
      ] : [],
      each.value.uses_image_storage ? [
        { name = "S3_IMAGE_BUCKET", value = aws_s3_bucket.images[0].id },
        { name = "S3_IMAGE_PREFIX", value = local.image_prefixes[each.key] },
        { name = "S3_IMAGE_KMS_KEY_ID", value = aws_kms_key.images[0].arn }
      ] : [],
      each.value.uses_redis ? [
        { name = "REDIS_HOST", value = aws_elasticache_replication_group.main[0].primary_endpoint_address },
        { name = "REDIS_PORT", value = "6379" },
        { name = "REDIS_SSL", value = "true" }
      ] : []
    )
    secrets     = [for name, arn in each.value.secrets : { name = name, valueFrom = arn }]
    healthCheck = { command = each.value.health_check_command, interval = 30, timeout = 5, retries = 3, startPeriod = 60 }
    logConfiguration = {
      logDriver = "awslogs"
      options   = { awslogs-group = aws_cloudwatch_log_group.application[each.key].name, awslogs-region = var.region, awslogs-stream-prefix = "app" }
    }
  }])
}
resource "aws_ecs_service" "application" {
  for_each                           = var.workloads
  name                               = each.key
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.application[each.key].arn
  desired_count                      = each.value.min_tasks
  launch_type                        = "FARGATE"
  platform_version                   = "1.4.0"
  availability_zone_rebalancing      = each.value.rebalance_enabled ? "ENABLED" : "DISABLED"
  health_check_grace_period_seconds  = each.value.hostname == null ? null : 90
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = false
  wait_for_steady_state              = true
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = [for subnet in aws_subnet.application : subnet.id]
    security_groups  = [aws_security_group.application[each.key].id]
    assign_public_ip = false
  }
  dynamic "load_balancer" {
    for_each = each.value.hostname == null ? [] : [each.key]
    content {
      target_group_arn = aws_lb_target_group.application[each.key].arn
      container_name   = "app"
      container_port   = each.value.port
    }
  }
  service_registries { registry_arn = aws_service_discovery_service.application[each.key].arn }
  lifecycle { ignore_changes = [desired_count] }
  depends_on = [
    aws_lb_listener_rule.application, aws_iam_role_policy.execution, aws_iam_role_policy.task,
    aws_iam_role_policy.images, aws_s3_bucket_policy.images,
    aws_s3_bucket_public_access_block.images, aws_s3_bucket_ownership_controls.images,
    aws_s3_bucket_server_side_encryption_configuration.images, aws_s3_bucket_versioning.images,
    aws_route.application, aws_route_table_association.application,
    aws_route.internet, aws_route_table_association.public,
    aws_vpc_security_group_ingress_rule.clients, aws_vpc_security_group_ingress_rule.from_alb,
    aws_vpc_security_group_ingress_rule.internal, aws_vpc_security_group_ingress_rule.redis_client,
    aws_vpc_security_group_ingress_rule.redis_peer,
    aws_vpc_security_group_egress_rule.to_task, aws_vpc_security_group_egress_rule.https,
    aws_vpc_security_group_egress_rule.identity_provider,
    aws_vpc_security_group_egress_rule.internal, aws_vpc_security_group_egress_rule.dependency,
    aws_vpc_security_group_egress_rule.redis_client, aws_vpc_security_group_egress_rule.redis_peer
  ]
}
resource "aws_appautoscaling_target" "application" {
  for_each           = var.workloads
  min_capacity       = each.value.min_tasks
  max_capacity       = each.value.autoscaling_enabled ? each.value.max_tasks : each.value.min_tasks
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.application[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}
resource "aws_appautoscaling_policy" "cpu" {
  for_each           = local.scaling_workloads
  name               = "${var.name}-${each.key}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.application[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.application[each.key].scalable_dimension
  service_namespace  = "ecs"
  target_tracking_scaling_policy_configuration {
    disable_scale_in   = !each.value.scale_in_enabled
    target_value       = 60
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageCPUUtilization" }
  }
}
