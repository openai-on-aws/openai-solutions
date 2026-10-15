resource "aws_security_group" "redis" {
  count       = var.redis == null ? 0 : 1
  name_prefix = "${var.name}-redis-"
  description = "TLS Redis access for declared callers"
  vpc_id      = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "redis_client" {
  for_each                     = { for key, w in var.workloads : key => w if w.uses_redis }
  security_group_id            = aws_security_group.redis[0].id
  referenced_security_group_id = aws_security_group.application[each.key].id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}
resource "aws_vpc_security_group_egress_rule" "redis_client" {
  for_each                     = { for key, w in var.workloads : key => w if w.uses_redis }
  security_group_id            = aws_security_group.application[each.key].id
  referenced_security_group_id = aws_security_group.redis[0].id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}
resource "aws_vpc_security_group_ingress_rule" "redis_peer" {
  count                        = var.redis == null ? 0 : 1
  security_group_id            = aws_security_group.redis[0].id
  referenced_security_group_id = aws_security_group.redis[0].id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}
resource "aws_vpc_security_group_egress_rule" "redis_peer" {
  count                        = var.redis == null ? 0 : 1
  security_group_id            = aws_security_group.redis[0].id
  referenced_security_group_id = aws_security_group.redis[0].id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}
resource "aws_elasticache_subnet_group" "main" {
  count      = var.redis == null ? 0 : 1
  name       = "${var.name}-data"
  subnet_ids = [for subnet in aws_subnet.data : subnet.id]
}
resource "aws_elasticache_replication_group" "main" {
  count                       = var.redis == null ? 0 : 1
  replication_group_id        = "${var.name}-redis"
  description                 = "Redis-compatible application queues and pub/sub"
  engine                      = "redis"
  engine_version              = var.redis.engine_version
  node_type                   = var.redis.node_type
  num_cache_clusters          = 2
  automatic_failover_enabled  = true
  multi_az_enabled            = true
  preferred_cache_cluster_azs = var.availability_zones
  subnet_group_name           = aws_elasticache_subnet_group.main[0].name
  security_group_ids          = [aws_security_group.redis[0].id]
  port                        = 6379
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  transit_encryption_mode     = "required"
  user_group_ids              = [var.redis.user_group_id]
  snapshot_retention_limit    = 7
  apply_immediately           = false
}
