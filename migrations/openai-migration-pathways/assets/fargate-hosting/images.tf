# Optional storage for the S3 session-image adapter. No public ACLs or automatic
# expiration; deploy only after reviewing storage scope and retention requirements.
resource "aws_kms_key" "images" {
  count                   = var.image_storage == null ? 0 : 1
  description             = "Session images for ${var.name}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "EnableAccountIAMPolicies", Effect = "Allow", Action = "kms:*", Resource = "*"
      Principal = { AWS = "arn:aws:iam::${var.account_id}:root" }
    }]
  })
}
resource "aws_s3_bucket" "images" {
  count         = var.image_storage == null ? 0 : 1
  bucket        = var.image_storage.bucket_name
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "images" {
  count                   = var.image_storage == null ? 0 : 1
  bucket                  = aws_s3_bucket.images[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "images" {
  count  = var.image_storage == null ? 0 : 1
  bucket = aws_s3_bucket.images[0].id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_versioning" "images" {
  count  = var.image_storage == null ? 0 : 1
  bucket = aws_s3_bucket.images[0].id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "images" {
  count  = var.image_storage == null ? 0 : 1
  bucket = aws_s3_bucket.images[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.images[0].arn
    }
    # Object-level encryption context is used by the scoped task-role grants.
    bucket_key_enabled = false
  }
}
resource "aws_s3_bucket_policy" "images" {
  count  = var.image_storage == null ? 0 : 1
  bucket = aws_s3_bucket.images[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonTLS", Effect = "Deny", Principal = "*", Action = "s3:*"
        Resource  = [aws_s3_bucket.images[0].arn, "${aws_s3_bucket.images[0].arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "RequireKMS", Effect = "Deny", Principal = "*", Action = "s3:PutObject"
        Resource  = "${aws_s3_bucket.images[0].arn}/*"
        Condition = { StringNotEquals = { "s3:x-amz-server-side-encryption" = "aws:kms" } }
      },
      {
        Sid       = "RequireImageKey", Effect = "Deny", Principal = "*", Action = "s3:PutObject"
        Resource  = "${aws_s3_bucket.images[0].arn}/*"
        Condition = { StringNotEquals = { "s3:x-amz-server-side-encryption-aws-kms-key-id" = aws_kms_key.images[0].arn } }
      }
    ]
  })
}
resource "aws_s3_bucket_cors_configuration" "images" {
  count  = var.image_storage == null ? 0 : (length(var.image_storage.browser_origins) == 0 ? 0 : 1)
  bucket = aws_s3_bucket.images[0].id
  cors_rule {
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = sort(tolist(var.image_storage.browser_origins))
    expose_headers  = ["ETag"]
    max_age_seconds = 600
  }
}
resource "aws_iam_role_policy" "images" {
  for_each = local.image_workloads
  role     = aws_iam_role.task[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow", Action = local.image_actions[each.key]
        Resource = "${aws_s3_bucket.images[0].arn}/${local.image_prefixes[each.key]}/*"
      },
      {
        Effect   = "Allow", Action = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = aws_kms_key.images[0].arn
        Condition = {
          StringEquals = { "kms:ViaService" = "s3.${var.region}.amazonaws.com", "kms:CallerAccount" = var.account_id }
          ArnLike      = { "kms:EncryptionContext:aws:s3:arn" = "${aws_s3_bucket.images[0].arn}/${local.image_prefixes[each.key]}/*" }
        }
      }
    ]
  })
}
output "image_storage_bindings" {
  description = "Generated environment and task role for each image-enabled service; empty when disabled."
  value = { for key, workload in local.image_workloads : key => {
    task_role_arn = aws_iam_role.task[key].arn
    environment = {
      AWS_REGION          = var.region
      AWS_ACCOUNT_ID      = var.account_id
      S3_IMAGE_BUCKET     = aws_s3_bucket.images[0].id
      S3_IMAGE_PREFIX     = local.image_prefixes[key]
      S3_IMAGE_KMS_KEY_ID = aws_kms_key.images[0].arn
    }
  } }
}
