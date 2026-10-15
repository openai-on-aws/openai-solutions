resource "aws_lb" "main" {
  name                       = var.name
  internal                   = var.alb_internal
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.alb_internal ? [for subnet in aws_subnet.application : subnet.id] : [for subnet in aws_subnet.public : subnet.id]
  enable_deletion_protection = var.deletion_protection
  drop_invalid_header_fields = true
  idle_timeout               = var.idle_timeout_seconds
}
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not found"
      status_code  = "404"
    }
  }
}
resource "aws_lb_target_group" "application" {
  for_each             = local.http_workloads
  name_prefix          = "mig-"
  port                 = each.value.port
  protocol             = each.value.backend_protocol
  target_type          = "ip"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = each.value.deregistration_delay
  health_check {
    enabled             = true
    path                = each.value.health_path
    protocol            = each.value.backend_protocol
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
  stickiness {
    type            = "lb_cookie"
    enabled         = each.value.sticky_sessions
    cookie_duration = 300
  }
  lifecycle { create_before_destroy = true }
}
resource "aws_lb_listener_rule" "application" {
  for_each     = local.http_workloads
  listener_arn = aws_lb_listener.https.arn
  priority     = each.value.listener_priority
  dynamic "action" {
    for_each = each.value.authentication_mode == "none" ? [] : [var.cognito_auth]
    content {
      type  = "authenticate-cognito"
      order = 1
      authenticate_cognito {
        user_pool_arn              = action.value.user_pool_arn
        user_pool_client_id        = action.value.user_pool_client_id
        user_pool_domain           = action.value.user_pool_domain
        scope                      = "openid"
        session_cookie_name        = "${var.name}Session"
        session_timeout            = action.value.session_seconds
        on_unauthenticated_request = each.value.authentication_mode
      }
    }
  }
  action {
    type             = "forward"
    order            = each.value.authentication_mode == "none" ? 1 : 2
    target_group_arn = aws_lb_target_group.application[each.key].arn
  }
  condition {
    host_header { values = [each.value.hostname] }
  }
  condition {
    path_pattern { values = sort(tolist(each.value.path_patterns)) }
  }
}
resource "aws_route53_record" "application" {
  for_each = local.http_hostnames
  zone_id  = var.hosted_zone_id
  name     = each.value
  type     = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
resource "aws_cloudwatch_metric_alarm" "unhealthy" {
  for_each            = local.http_workloads
  alarm_name          = "${var.name}-${each.key}-unhealthy"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "missing"
  alarm_actions       = var.alarm_topic_arns
  ok_actions          = var.alarm_topic_arns
  dimensions          = { LoadBalancer = aws_lb.main.arn_suffix, TargetGroup = aws_lb_target_group.application[each.key].arn_suffix }
}
