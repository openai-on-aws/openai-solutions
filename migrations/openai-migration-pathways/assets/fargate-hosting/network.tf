resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
}
resource "aws_internet_gateway" "main" { vpc_id = aws_vpc.main.id }
resource "aws_subnet" "public" {
  for_each          = local.zones
  vpc_id            = aws_vpc.main.id
  availability_zone = each.value
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, tonumber(each.key))
  tags              = { Tier = "public" }
}
resource "aws_subnet" "application" {
  for_each          = local.zones
  vpc_id            = aws_vpc.main.id
  availability_zone = each.value
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, tonumber(each.key) + 2)
  tags              = { Tier = "private-application" }
}
resource "aws_subnet" "data" {
  for_each          = local.zones
  vpc_id            = aws_vpc.main.id
  availability_zone = each.value
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, tonumber(each.key) + 4)
  tags              = { Tier = "isolated-data" }
}
resource "aws_eip" "nat" {
  for_each = local.zones
  domain   = "vpc"
}
resource "aws_nat_gateway" "main" {
  for_each      = local.zones
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  depends_on    = [aws_internet_gateway.main]
}
resource "aws_route_table" "public" { vpc_id = aws_vpc.main.id }
resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}
resource "aws_route_table_association" "public" {
  for_each       = local.zones
  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table" "application" {
  for_each = local.zones
  vpc_id   = aws_vpc.main.id
}
resource "aws_route" "application" {
  for_each               = local.zones
  route_table_id         = aws_route_table.application[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[each.key].id
}
resource "aws_route_table_association" "application" {
  for_each       = local.zones
  subnet_id      = aws_subnet.application[each.key].id
  route_table_id = aws_route_table.application[each.key].id
}
resource "aws_route_table" "data" {
  for_each = local.zones
  vpc_id   = aws_vpc.main.id
}
resource "aws_route_table_association" "data" {
  for_each       = local.zones
  subnet_id      = aws_subnet.data[each.key].id
  route_table_id = aws_route_table.data[each.key].id
}
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [for table in aws_route_table.application : table.id]
}
resource "aws_security_group" "alb" {
  name_prefix = "${var.name}-alb-"
  description = "HTTPS ingress from configured clients only"
  vpc_id      = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "clients" {
  for_each          = var.client_cidrs
  security_group_id = aws_security_group.alb.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = each.value
}
resource "aws_security_group" "application" {
  for_each    = var.workloads
  name_prefix = "${var.name}-${each.key}-"
  description = "Isolated task interfaces for ${each.key}"
  vpc_id      = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "from_alb" {
  for_each                     = local.http_workloads
  security_group_id            = aws_security_group.application[each.key].id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
}
resource "aws_vpc_security_group_egress_rule" "to_task" {
  for_each                     = local.http_workloads
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.application[each.key].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
}
resource "aws_vpc_security_group_egress_rule" "https" {
  for_each          = var.workloads
  security_group_id = aws_security_group.application[each.key].id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}
resource "aws_vpc_security_group_egress_rule" "identity_provider" {
  count             = length(local.authenticated_workloads) == 0 ? 0 : 1
  security_group_id = aws_security_group.alb.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
  description       = "HTTPS to Cognito identity endpoints"
}
resource "aws_vpc_security_group_ingress_rule" "internal" {
  for_each                     = local.connections
  security_group_id            = aws_security_group.application[each.value.target].id
  referenced_security_group_id = aws_security_group.application[each.value.source].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
}
resource "aws_vpc_security_group_egress_rule" "dependency" {
  for_each                     = local.extra_egress
  security_group_id            = aws_security_group.application[each.value.workload].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
  cidr_ipv4                    = each.value.cidr_ipv4
  referenced_security_group_id = each.value.security_group_id
  description                  = each.value.description
}
resource "aws_vpc_security_group_egress_rule" "internal" {
  for_each                     = local.connections
  security_group_id            = aws_security_group.application[each.value.source].id
  referenced_security_group_id = aws_security_group.application[each.value.target].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
}
