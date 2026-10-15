terraform {
  required_version = ">= 1.9.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.10.0, < 7.0.0" }
  }
}

variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,18}[a-z0-9]$", var.name)) && !startswith(var.name, "internal-") && !strcontains(var.name, "--")
    error_message = "Use 3-20 lowercase characters, start with a letter, end with a letter/digit, and avoid consecutive hyphens or the internal- prefix."
  }
}
variable "account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Provide the target AWS account ID."
  }
}
variable "region" { type = string }
variable "availability_zones" {
  type = list(string)
  validation {
    condition     = length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2 && alltrue([for az in var.availability_zones : can(regex("^${var.region}[a-z]$", az))])
    error_message = "Provide two distinct standard availability zones in the target Region."
  }
}
variable "vpc_cidr" {
  type = string
  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && can(cidrsubnet(var.vpc_cidr, 4, 5)) && try(tonumber(split("/", var.vpc_cidr)[1]) >= 16 && tonumber(split("/", var.vpc_cidr)[1]) <= 20, false)
    error_message = "Provide a reviewed IPv4 CIDR between /16 and /20; six disjoint subnet ranges will be derived."
  }
}
variable "client_cidrs" {
  type = set(string)
  validation {
    condition     = length(var.client_cidrs) > 0 && alltrue([for cidr in var.client_cidrs : can(cidrnetmask(cidr))])
    error_message = "Specify the IPv4 client networks allowed to reach HTTPS ingress."
  }
}
variable "certificate_arn" {
  type = string
  validation {
    condition     = can(regex("^arn:aws:acm:${var.region}:${var.account_id}:certificate/[a-zA-Z0-9-]+$", var.certificate_arn))
    error_message = "Supply an existing ACM certificate in the target account and Region."
  }
}
variable "hosted_zone_id" { type = string }
variable "alb_internal" { type = bool }
variable "idle_timeout_seconds" {
  description = "Align with the application's longest quiet response and WebSocket heartbeat interval."
  type        = number
  default     = 600
  validation {
    condition     = var.idle_timeout_seconds >= 1 && var.idle_timeout_seconds <= 4000 && floor(var.idle_timeout_seconds) == var.idle_timeout_seconds
    error_message = "ALB idle timeout must be an integer from 1 to 4000 seconds."
  }
}
variable "deletion_protection" {
  type    = bool
  default = true
}
variable "alarm_topic_arns" {
  type    = list(string)
  default = []
}
variable "logs_retention_days" {
  type    = number
  default = 30
}
variable "redis" {
  description = "Existing ACL user group, not a password. Null omits the Redis service."
  type        = object({ user_group_id = string, node_type = string, engine_version = string })
  default     = null
}
variable "cognito_auth" {
  description = "Existing Cognito app client for one shared application identity boundary. No client secret is read into this module."
  type = object({
    user_pool_arn       = string
    user_pool_client_id = string
    user_pool_domain    = string
    session_seconds     = optional(number, 3600)
  })
  default = null
  validation {
    condition = var.cognito_auth == null ? true : (
      can(regex("^arn:aws:cognito-idp:${var.region}:${var.account_id}:userpool/${var.region}_[A-Za-z0-9]+$", var.cognito_auth.user_pool_arn)) &&
      can(regex("^[a-z0-9]{1,128}$", var.cognito_auth.user_pool_client_id)) &&
      length(var.cognito_auth.user_pool_domain) <= 253 &&
      alltrue([for label in split(".", var.cognito_auth.user_pool_domain) : can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", label))]) &&
      var.cognito_auth.session_seconds >= 60 && var.cognito_auth.session_seconds <= 3600 && floor(var.cognito_auth.session_seconds) == var.cognito_auth.session_seconds
    )
    error_message = "Use a Cognito pool in this account/Region, its existing client ID and domain (not a URL), and a 60-3600 second session."
  }
}
variable "image_storage" {
  description = "Optional new private image bucket. Null preserves external/manual storage bindings. No object expiration is enabled automatically."
  type = object({
    bucket_name     = string
    browser_origins = optional(set(string), [])
  })
  default = null
  validation {
    condition = var.image_storage == null ? true : (
      can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", var.image_storage.bucket_name)) &&
      !can(regex("^(xn--|sthree-|amzn-s3-demo-)|(-s3alias|--ol-s3|--x-s3|--table-s3|-an)$", var.image_storage.bucket_name)) &&
      alltrue([for origin in var.image_storage.browser_origins : can(regex("^https://[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]+)?$", origin))])
    )
    error_message = "Use a 3-63 character lowercase, non-dotted shared-namespace bucket name without AWS-reserved prefixes/suffixes, and exact HTTPS browser origins without paths or wildcards."
  }
}
variable "workloads" {
  description = "One entry per ported Linux service, not one entry per repository. Null hostname means private worker/service."
  type = map(object({
    image                = string
    port                 = number
    cpu_architecture     = string
    cpu                  = number
    memory               = number
    user                 = string
    health_check_command = list(string)
    hostname             = optional(string)
    listener_priority    = optional(number)
    path_patterns        = optional(set(string), ["/*"])
    authentication_mode  = optional(string, "none")
    health_path          = optional(string, "/health")
    backend_protocol     = optional(string, "HTTP")
    sticky_sessions      = optional(bool, false)
    deregistration_delay = optional(number, 120)
    autoscaling_enabled  = optional(bool, false)
    scale_in_enabled     = optional(bool, false)
    rebalance_enabled    = optional(bool, false)
    min_tasks            = optional(number, 2)
    max_tasks            = optional(number, 4)
    environment          = optional(map(string), {})
    secrets              = optional(map(string), {})
    secrets_kms_key_arns = optional(list(string), [])
    task_policy_json     = optional(string)
    allowed_callers      = optional(set(string), [])
    uses_redis           = optional(bool, false)
    uses_image_storage   = optional(bool, false)
    image_storage_owner  = optional(string)
    egress = optional(map(object({
      port              = number
      cidr_ipv4         = optional(string)
      security_group_id = optional(string)
      description       = string
    })), {})
  }))
  validation {
    condition     = length(var.workloads) > 0 && length(var.workloads) <= 80 && alltrue([for key, w in var.workloads : can(regex("^[a-z][a-z0-9-]{0,23}$", key))])
    error_message = "Provide 1-80 services with lowercase 1-24 character names."
  }
  validation {
    condition     = alltrue([for w in values(var.workloads) : can(regex("^${var.account_id}\\.dkr\\.ecr\\.${var.region}\\.amazonaws\\.com/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$", w.image))])
    error_message = "Use actual digest-pinned ECR images in the target account and Region."
  }
  validation {
    condition = alltrue([for w in values(var.workloads) :
      w.port >= 1 && w.port <= 65535 && floor(w.port) == w.port &&
      contains(["X86_64", "ARM64"], w.cpu_architecture) &&
      contains(try(local.memory_by_cpu[tostring(w.cpu)], []), w.memory) &&
      w.min_tasks >= 1 && w.max_tasks >= w.min_tasks && w.max_tasks <= 100 &&
      floor(w.min_tasks) == w.min_tasks && floor(w.max_tasks) == w.max_tasks &&
      can(regex("^[1-9][0-9]*(:[0-9]+)?$", w.user)) &&
      length(w.health_check_command) >= 2 && contains(["CMD", "CMD-SHELL"], try(w.health_check_command[0], "")) &&
      contains(["HTTP", "HTTPS"], w.backend_protocol) && startswith(w.health_path, "/")
      && w.deregistration_delay >= 0 && w.deregistration_delay <= 3600 && floor(w.deregistration_delay) == w.deregistration_delay
      && (!w.scale_in_enabled || w.autoscaling_enabled)
    ])
    error_message = "Validate ports, Linux platform, Fargate CPU/memory, task counts, non-root UID, health command and backend protocol."
  }
  validation {
    condition = (
      anytrue([for w in values(var.workloads) : w.hostname != null]) &&
      alltrue([for w in values(var.workloads) : w.hostname == null ? true : (
        length(w.hostname) <= 253 && length(split(".", w.hostname)) >= 2 &&
        alltrue([for label in split(".", w.hostname) : can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", label))]) &&
        try(w.listener_priority >= 1 && w.listener_priority <= 50000 && floor(w.listener_priority) == w.listener_priority, false)
      )]) &&
      length(distinct([for w in values(var.workloads) : w.listener_priority if w.hostname != null])) == length([for w in values(var.workloads) : w if w.hostname != null])
    )
    error_message = "HTTP services need valid hostnames and stable unique listener priorities from 1 to 50000; workers may omit both."
  }
  validation {
    condition = alltrue([for w in values(var.workloads) :
      length(w.path_patterns) >= 1 && length(w.path_patterns) <= 3 &&
      alltrue([for pattern in w.path_patterns : length(pattern) <= 128 && can(regex("^/[A-Za-z0-9_./-]*\\*?$", pattern)) && !strcontains(pattern, "..")]) &&
      contains(["none", "authenticate", "deny"], w.authentication_mode) &&
      (w.authentication_mode == "none" ? true : (var.cognito_auth != null && w.hostname != null && w.backend_protocol == "HTTPS" && length(w.allowed_callers) == 0))
    ])
    error_message = "Use 1-3 absolute path patterns with only a trailing wildcard. Authenticated services require Cognito, HTTPS backends, a hostname and ALB-only ingress."
  }
  validation {
    condition = alltrue(flatten([for key, w in var.workloads : [for other_key, other in var.workloads :
      key == other_key || w.hostname == null || other.hostname != w.hostname ? true : (
        (w.authentication_mode == "none") == (other.authentication_mode == "none") &&
        alltrue(flatten([for pattern in w.path_patterns : [for other_pattern in other.path_patterns :
          pattern != other_pattern &&
          (endswith(pattern, "*") && startswith(other_pattern, trimsuffix(pattern, "*")) ? try(w.listener_priority > other.listener_priority, false) : true)
        ]]))
      )
    ]]))
    error_message = "Shared host routes must have consistent authentication, distinct paths, and more-specific paths before wildcard fallbacks."
  }
  validation {
    condition = alltrue([for key, w in var.workloads : w.image_storage_owner == null ? true : try(
      w.uses_image_storage && w.image_storage_owner != key && var.workloads[w.image_storage_owner].uses_image_storage && var.workloads[w.image_storage_owner].image_storage_owner == null,
      false
    )])
    error_message = "A document reader must opt into storage and name a distinct image-enabled writer; missing owners and chained readers are invalid."
  }
  validation {
    condition = alltrue(flatten([for w in values(var.workloads) : [for rule in values(w.egress) :
      rule.port >= 1 && rule.port <= 65535 && floor(rule.port) == rule.port &&
      ((rule.cidr_ipv4 == null) != (rule.security_group_id == null)) &&
      (rule.cidr_ipv4 == null ? true : can(cidrnetmask(rule.cidr_ipv4))) &&
      (rule.security_group_id == null ? true : can(regex("^sg-[0-9a-f]+$", rule.security_group_id))) &&
      length(trimspace(rule.description)) > 0
    ]]))
    error_message = "Each TCP egress rule needs one valid port, a purpose, and exactly one IPv4 CIDR or reachable destination security group."
  }
  validation {
    condition = alltrue([for w in values(var.workloads) :
      alltrue([for caller in w.allowed_callers : contains(keys(var.workloads), caller)]) &&
      (!w.uses_redis || var.redis != null) &&
      (!w.uses_image_storage || var.image_storage != null) &&
      (!w.uses_image_storage || length(setintersection(setunion(toset(keys(w.environment)), toset(keys(w.secrets))), toset(["S3_IMAGE_BUCKET", "S3_IMAGE_PREFIX", "S3_IMAGE_KMS_KEY_ID"]))) == 0) &&
      (w.task_policy_json == null ? true : can(jsondecode(w.task_policy_json))) &&
      length(setintersection(toset(keys(w.environment)), toset(keys(w.secrets)))) == 0 &&
      length(setintersection(setunion(toset(keys(w.environment)), toset(keys(w.secrets))), toset(["AWS_REGION", "AWS_ACCOUNT_ID", "REDIS_HOST", "REDIS_PORT", "REDIS_SSL"]))) == 0 &&
      (w.authentication_mode == "none" || length(setintersection(setunion(toset(keys(w.environment)), toset(keys(w.secrets))), toset(["ALB_SIGNER_ARN", "OIDC_ISSUER", "OIDC_CLIENT_ID", "APPLICATION_ORIGINS"]))) == 0) &&
      alltrue([for arn in values(w.secrets) : can(regex("^arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:[A-Za-z0-9/_+=.@-]+$", arn))])
    ])
    error_message = "Check internal callers, Redis settings, policy JSON, unique environment names and whole-secret ARNs. Reserved environment names are generated by this module."
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags { tags = { Deployment = var.name, ManagedBy = "terraform" } }
}

locals {
  zones                   = { for index, az in var.availability_zones : tostring(index) => az }
  http_workloads          = { for key, w in var.workloads : key => w if w.hostname != null }
  http_hostnames          = toset([for w in values(local.http_workloads) : w.hostname])
  authenticated_workloads = { for key, w in var.workloads : key => w if w.authentication_mode != "none" }
  cognito_issuer          = var.cognito_auth == null ? null : "https://cognito-idp.${var.region}.amazonaws.com/${split("/", var.cognito_auth.user_pool_arn)[1]}"
  scaling_workloads       = { for key, w in var.workloads : key => w if w.autoscaling_enabled }
  image_workloads         = { for key, w in var.workloads : key => w if w.uses_image_storage }
  image_prefixes          = { for key, w in local.image_workloads : key => "${var.name}/${coalesce(w.image_storage_owner, key)}/images" }
  image_actions           = { for key, w in local.image_workloads : key => concat(["s3:GetObject", "s3:GetObjectVersion"], w.image_storage_owner == null ? ["s3:PutObject"] : []) }
  extra_egress            = { for rule in flatten([for key, w in var.workloads : [for id, r in w.egress : merge(r, { id = jsonencode([key, id]), workload = key })]]) : rule.id => rule }
  memory_by_cpu = {
    "256"  = [512, 1024, 2048]
    "512"  = [1024, 2048, 3072, 4096]
    "1024" = [2048, 3072, 4096, 5120, 6144, 7168, 8192]
    "2048" = [for n in range(4, 17) : n * 1024]
    "4096" = [for n in range(8, 31) : n * 1024]
  }
  connections      = { for pair in flatten([for key, w in var.workloads : [for caller in w.allowed_callers : { id = jsonencode([caller, key]), source = caller, target = key, port = w.port }]]) : pair.id => pair }
  ecr_repositories = { for key, w in var.workloads : key => "arn:aws:ecr:${var.region}:${var.account_id}:repository/${split("@", join("/", slice(split("/", w.image), 1, length(split("/", w.image)))))[0]}" }
  task_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" }, Condition = {
      StringEquals = { "aws:SourceAccount" = var.account_id }
      ArnLike      = { "aws:SourceArn" = "arn:aws:ecs:${var.region}:${var.account_id}:*" }
    } }]
  })
}
