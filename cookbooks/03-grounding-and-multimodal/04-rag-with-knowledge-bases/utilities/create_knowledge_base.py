"""Provision a Bedrock Knowledge Base from a zip of documents, end to end.

This is the automation companion to Appendix A of the recipe README. It takes a
zip of source documents (default: the NASA wind-tunnel corpus in
``assets/nasa.zip``) and stands up everything a Bedrock Knowledge Base needs,
using **Amazon S3 Vectors** as the vector store — the lowest-friction, lowest-cost
option, with no cluster or index policies to manage:

    1. Unzip the documents locally (macOS ``__MACOSX`` junk is already stripped).
    2. Create an S3 bucket and upload the documents (the KB data source).
    3. Create an S3 Vectors vector bucket + index (the vector store).
    4. Create an IAM service role the KB assumes (embed model + S3 + S3 Vectors).
    5. CreateKnowledgeBase (VECTOR / S3_VECTORS, Titan embed text v2).
    6. CreateDataSource (S3) and StartIngestionJob.

Every step is idempotent: re-running reuses resources that already exist by name,
so a partial run can be resumed. Configuration comes from the environment; nothing
is hard-coded except sensible defaults. Credentials come from the standard AWS
credential chain (env vars, shared config, or an assumed role) — there are no
secrets in this file.

Run it from the cookbooks/ directory:

    uv run --env-file .env python \
      03-grounding-and-multimodal/04-rag-with-knowledge-bases/utilities/create_knowledge_base.py

Tear everything down again (KB, data source, role, buckets, vector store) by
passing ``--teardown`` to the same script:

    uv run --env-file .env python .../utilities/create_knowledge_base.py --teardown

Environment variables (all optional except where noted):

    AWS_REGION            Region for every resource   (default us-east-1)
    KB_NAME               Knowledge Base name         (default nasa-windtunnel-kb)
    KB_SOURCE_ZIP         Path to the documents zip   (default assets/nasa.zip,
                          resolved relative to the repo root)
    KB_DOC_BUCKET         S3 bucket for source docs   (default derived from
                          KB_NAME + account id)
    KB_VECTOR_BUCKET      S3 Vectors bucket name      (default KB_NAME + "-vectors")
    KB_VECTOR_INDEX       S3 Vectors index name       (default KB_NAME + "-index")
    KB_ROLE_NAME          IAM service role name       (default KB_NAME + "-role")
    KB_EMBED_MODEL        Embedding model id          (default
                          amazon.titan-embed-text-v2:0)
    KB_EMBED_DIMENSION    Embedding dimension         (1024/512/256; default 1024)

The KB id is printed at the end — set it as ``KNOWLEDGE_BASE_ID`` for the
retrieval recipe (``rag_with_knowledge_bases.py``).

See README.md (Appendix A) for the manual/console equivalent and the permissions
the *caller* needs to run this (Bedrock, S3, S3 Vectors, and IAM role creation).
"""

import argparse
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# --- Configuration ----------------------------------------------------------
# All tunables come from the environment with sensible defaults. Only the
# derived names depend on the account id, which we look up at runtime.

REGION = os.environ.get("AWS_REGION", "us-east-1")
KB_NAME = os.environ.get("KB_NAME", "nasa-windtunnel-kb")
EMBED_MODEL = os.environ.get("KB_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
EMBED_DIMENSION = int(os.environ.get("KB_EMBED_DIMENSION", "1024"))

VECTOR_BUCKET = os.environ.get("KB_VECTOR_BUCKET", f"{KB_NAME}-vectors")
VECTOR_INDEX = os.environ.get("KB_VECTOR_INDEX", f"{KB_NAME}-index")
ROLE_NAME = os.environ.get("KB_ROLE_NAME", f"{KB_NAME}-role")

# The source zip is resolved relative to the repo root so the script runs the
# same whether invoked from cookbooks/ or elsewhere. Walk up to find the repo
# root (the directory that contains the assets/ folder).
_DEFAULT_ZIP_REL = "assets/nasa.zip"


def _repo_root() -> Path:
    """Find the repo root by walking up until we see an assets/ directory."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "assets").is_dir():
            return parent
    # Fall back to the current working directory.
    return Path.cwd()


SOURCE_ZIP = Path(
    os.environ.get("KB_SOURCE_ZIP", str(_repo_root() / _DEFAULT_ZIP_REL))
).expanduser()

EMBED_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/{EMBED_MODEL}"

# Where documents are extracted before upload.
_EXTRACT_DIR = Path(__file__).resolve().parent / ".kb_documents"

# --- Clients ----------------------------------------------------------------
# Built lazily inside main() so importing the module (e.g. for --help or a lint
# pass) never requires live credentials.


def _clients() -> dict:
    session = boto3.Session(region_name=REGION)
    return {
        "sts": session.client("sts"),
        "s3": session.client("s3"),
        "s3vectors": session.client("s3vectors"),
        "iam": session.client("iam"),
        "bedrock_agent": session.client("bedrock-agent"),
    }


def _doc_bucket(account_id: str) -> str:
    """Documents bucket name — globally unique, so scope it to the account."""
    return os.environ.get("KB_DOC_BUCKET", f"{KB_NAME}-docs-{account_id}")


# --- Step 1: Unzip ----------------------------------------------------------

def unzip_documents() -> list[Path]:
    """Extract the source zip locally, returning the list of document paths.

    The zip has already had macOS ``__MACOSX`` entries stripped, but we guard
    against them anyway so the function is safe on any zip.
    """
    if not SOURCE_ZIP.is_file():
        sys.exit(f"Source zip not found: {SOURCE_ZIP}")

    _EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    docs: list[Path] = []
    with zipfile.ZipFile(SOURCE_ZIP) as zf:
        for info in zf.infolist():
            name = info.filename
            if info.is_dir():
                continue
            # Skip macOS resource-fork junk defensively.
            base = os.path.basename(name)
            if name.startswith("__MACOSX/") or base.startswith("._"):
                continue
            target = _EXTRACT_DIR / base
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            docs.append(target)
    return docs


# --- Step 2: Documents bucket + upload --------------------------------------

def ensure_bucket(c: dict, bucket: str) -> None:
    """Create a regular S3 bucket if it does not already exist (idempotent)."""
    try:
        c["s3"].head_bucket(Bucket=bucket)
        return
    except ClientError as err:
        if err.response["Error"]["Code"] not in ("404", "NoSuchBucket", "403"):
            raise
    # us-east-1 must NOT pass a LocationConstraint; every other region must.
    kwargs = {"Bucket": bucket}
    if REGION != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": REGION}
    c["s3"].create_bucket(**kwargs)
    c["s3"].get_waiter("bucket_exists").wait(Bucket=bucket)


def upload_documents(c: dict, bucket: str, docs: list[Path]) -> None:
    """Upload each document to the bucket under a documents/ prefix."""
    for doc in docs:
        c["s3"].upload_file(str(doc), bucket, f"documents/{doc.name}")


# --- Step 3: S3 Vectors store -----------------------------------------------

def ensure_vector_store(c: dict) -> str:
    """Create the S3 Vectors bucket + index if absent; return the index ARN.

    The index dimension MUST match the embedding model's output dimension, or
    ingestion fails. distanceMetric=cosine pairs with Titan embeddings.
    """
    sv = c["s3vectors"]
    try:
        sv.get_vector_bucket(vectorBucketName=VECTOR_BUCKET)
    except sv.exceptions.NotFoundException:
        sv.create_vector_bucket(vectorBucketName=VECTOR_BUCKET)

    try:
        sv.get_index(vectorBucketName=VECTOR_BUCKET, indexName=VECTOR_INDEX)
    except sv.exceptions.NotFoundException:
        sv.create_index(
            vectorBucketName=VECTOR_BUCKET,
            indexName=VECTOR_INDEX,
            dimension=EMBED_DIMENSION,
            dataType="float32",
            distanceMetric="cosine",
        )

    idx = sv.get_index(vectorBucketName=VECTOR_BUCKET, indexName=VECTOR_INDEX)
    return idx["index"]["indexArn"]


# --- Step 4: IAM service role -----------------------------------------------

def _trust_policy(account_id: str) -> dict:
    """Let the Bedrock service assume this role, scoped to our account."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock:{REGION}:{account_id}:knowledge-base/*"
                        )
                    },
                },
            }
        ],
    }


def _permissions_policy(doc_bucket: str, vector_index_arn: str) -> dict:
    """Least-privilege: invoke the embed model, read docs, write vectors."""
    vector_bucket_arn = vector_index_arn.split("/index/")[0]
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeEmbeddingModel",
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": [EMBED_MODEL_ARN],
            },
            {
                "Sid": "ReadSourceDocuments",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{doc_bucket}",
                    f"arn:aws:s3:::{doc_bucket}/*",
                ],
            },
            {
                "Sid": "AccessVectorStore",
                "Effect": "Allow",
                "Action": ["s3vectors:*"],
                "Resource": [vector_bucket_arn, vector_index_arn],
            },
        ],
    }


def ensure_role(c: dict, account_id: str, doc_bucket: str, index_arn: str) -> str:
    """Create the KB service role (idempotent); return its ARN.

    Newly created roles need a few seconds before Bedrock can assume them, so
    we pause after creation to avoid a race on CreateKnowledgeBase.
    """
    iam = c["iam"]
    created = False
    try:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
    except iam.exceptions.NoSuchEntityException:
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(_trust_policy(account_id)),
            Description=f"Bedrock Knowledge Base service role for {KB_NAME}",
        )["Role"]
        created = True

    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=f"{KB_NAME}-permissions",
        PolicyDocument=json.dumps(_permissions_policy(doc_bucket, index_arn)),
    )

    if created:
        # IAM is eventually consistent; give the role time to propagate.
        time.sleep(10)
    return role["Arn"]


# --- Step 5: Knowledge Base -------------------------------------------------

def _find_kb_by_name(c: dict, name: str) -> str | None:
    paginator = c["bedrock_agent"].get_paginator("list_knowledge_bases")
    for page in paginator.paginate():
        for summary in page["knowledgeBaseSummaries"]:
            if summary["name"] == name:
                return summary["knowledgeBaseId"]
    return None


def ensure_knowledge_base(c: dict, role_arn: str, index_arn: str) -> str:
    """Create the KB if one with this name does not already exist."""
    existing = _find_kb_by_name(c, KB_NAME)
    if existing:
        return existing

    vector_bucket_arn = index_arn.split("/index/")[0]
    resp = c["bedrock_agent"].create_knowledge_base(
        name=KB_NAME,
        description="NASA wind-tunnel corpus (created by create_knowledge_base.py)",
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": EMBED_MODEL_ARN,
                "embeddingModelConfiguration": {
                    "bedrockEmbeddingModelConfiguration": {
                        "dimensions": EMBED_DIMENSION,
                        "embeddingDataType": "FLOAT32",
                    }
                },
            },
        },
        storageConfiguration={
            "type": "S3_VECTORS",
            "s3VectorsConfiguration": {
                "indexArn": index_arn,
                "vectorBucketArn": vector_bucket_arn,
            },
        },
    )
    return resp["knowledgeBase"]["knowledgeBaseId"]


def _wait_kb_active(c: dict, kb_id: str, timeout: int = 120) -> None:
    """Poll until the KB leaves CREATING; raise if it fails or times out."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        kb = c["bedrock_agent"].get_knowledge_base(knowledgeBaseId=kb_id)
        status = kb["knowledgeBase"]["status"]
        if status == "ACTIVE":
            return
        if status == "FAILED":
            reasons = kb["knowledgeBase"].get("failureReasons", [])
            sys.exit(f"Knowledge base creation failed: {reasons}")
        time.sleep(5)
    sys.exit(f"Timed out waiting for knowledge base {kb_id} to become ACTIVE")


# --- Step 6: Data source + ingestion ----------------------------------------

def _find_data_source(c: dict, kb_id: str, name: str) -> str | None:
    resp = c["bedrock_agent"].list_data_sources(knowledgeBaseId=kb_id)
    for summary in resp.get("dataSourceSummaries", []):
        if summary["name"] == name:
            return summary["dataSourceId"]
    return None


def ensure_data_source(c: dict, kb_id: str, doc_bucket: str, account_id: str) -> str:
    """Attach the S3 documents bucket as a data source (idempotent)."""
    ds_name = f"{KB_NAME}-s3-source"
    existing = _find_data_source(c, kb_id, ds_name)
    if existing:
        return existing

    resp = c["bedrock_agent"].create_data_source(
        knowledgeBaseId=kb_id,
        name=ds_name,
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{doc_bucket}",
                "bucketOwnerAccountId": account_id,
                "inclusionPrefixes": ["documents/"],
            },
        },
    )
    return resp["dataSource"]["dataSourceId"]


def ingest(c: dict, kb_id: str, ds_id: str, timeout: int = 900) -> dict:
    """Start an ingestion job and poll to completion."""
    job = c["bedrock_agent"].start_ingestion_job(
        knowledgeBaseId=kb_id, dataSourceId=ds_id
    )["ingestionJob"]
    job_id = job["ingestionJobId"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        job = c["bedrock_agent"].get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]
        status = job["status"]
        if status in ("COMPLETE", "FAILED"):
            return job
        time.sleep(10)
    sys.exit(f"Timed out waiting for ingestion job {job_id}")


# --- Orchestration ----------------------------------------------------------

def create() -> None:
    c = _clients()
    account_id = c["sts"].get_caller_identity()["Account"]
    doc_bucket = _doc_bucket(account_id)

    print("→ create")
    print(f"   region            {REGION}")
    print(f"   knowledge_base    {KB_NAME}")
    print(f"   source_zip        {SOURCE_ZIP}")
    print(f"   doc_bucket        {doc_bucket}")
    print(f"   vector_bucket     {VECTOR_BUCKET}")
    print(f"   vector_index      {VECTOR_INDEX}")
    print(f"   embed_model       {EMBED_MODEL}")
    print(f"   embed_dimension   {EMBED_DIMENSION}")
    print()

    docs = unzip_documents()
    print(f"← unzip            {len(docs)} documents")

    ensure_bucket(c, doc_bucket)
    upload_documents(c, doc_bucket, docs)
    print(f"← upload           s3://{doc_bucket}/documents/ ({len(docs)} objects)")

    index_arn = ensure_vector_store(c)
    print(f"← vector store     {index_arn}")

    role_arn = ensure_role(c, account_id, doc_bucket, index_arn)
    print(f"← iam role         {role_arn}")

    kb_id = ensure_knowledge_base(c, role_arn, index_arn)
    _wait_kb_active(c, kb_id)
    print(f"← knowledge base   {kb_id} (ACTIVE)")

    ds_id = ensure_data_source(c, kb_id, doc_bucket, account_id)
    print(f"← data source      {ds_id}")

    print("← ingestion        running (this can take several minutes)...")
    job = ingest(c, kb_id, ds_id)
    stats = job.get("statistics", {})
    print(f"   status            {job['status']}")
    if stats:
        print(f"   docs scanned      {stats.get('numberOfDocumentsScanned', '?')}")
        print(f"   docs indexed      {stats.get('numberOfNewDocumentsIndexed', '?')}")
    if job["status"] == "FAILED":
        sys.exit(f"Ingestion failed: {job.get('failureReasons', [])}")
    print()

    print("✓ done")
    print(f"   KNOWLEDGE_BASE_ID={kb_id}")
    print("   Set that in your .env and run rag_with_knowledge_bases.py to query it.")


# --- Teardown ---------------------------------------------------------------

def teardown() -> None:
    """Delete everything create() made. Safe to run repeatedly.

    Order matters: KB (with its data sources) first, then the vector store,
    then the role, then the documents bucket. Missing resources are ignored so a
    partial teardown can be completed by re-running.
    """
    c = _clients()
    account_id = c["sts"].get_caller_identity()["Account"]
    doc_bucket = _doc_bucket(account_id)

    print("→ teardown")
    print(f"   region            {REGION}")
    print(f"   knowledge_base    {KB_NAME}")
    print()

    # 1. Knowledge base (deleting the KB deletes its data sources too).
    kb_id = _find_kb_by_name(c, KB_NAME)
    if kb_id:
        c["bedrock_agent"].delete_knowledge_base(knowledgeBaseId=kb_id)
        print(f"← deleted KB       {kb_id}")
    else:
        print("← KB               (none)")

    # 2. S3 Vectors index + bucket.
    sv = c["s3vectors"]
    try:
        sv.delete_index(vectorBucketName=VECTOR_BUCKET, indexName=VECTOR_INDEX)
        print(f"← deleted index    {VECTOR_INDEX}")
    except sv.exceptions.NotFoundException:
        print("← vector index     (none)")
    try:
        sv.delete_vector_bucket(vectorBucketName=VECTOR_BUCKET)
        print(f"← deleted vectors  {VECTOR_BUCKET}")
    except sv.exceptions.NotFoundException:
        print("← vector bucket    (none)")

    # 3. IAM role (detach inline policies first).
    iam = c["iam"]
    try:
        for pol in iam.list_role_policies(RoleName=ROLE_NAME)["PolicyNames"]:
            iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName=pol)
        iam.delete_role(RoleName=ROLE_NAME)
        print(f"← deleted role     {ROLE_NAME}")
    except iam.exceptions.NoSuchEntityException:
        print("← iam role         (none)")

    # 4. Documents bucket (empty it, then delete).
    try:
        c["s3"].head_bucket(Bucket=doc_bucket)
        paginator = c["s3"].get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=doc_bucket):
            objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objects:
                c["s3"].delete_objects(
                    Bucket=doc_bucket, Delete={"Objects": objects}
                )
        c["s3"].delete_bucket(Bucket=doc_bucket)
        print(f"← deleted bucket   {doc_bucket}")
    except ClientError as err:
        if err.response["Error"]["Code"] in ("404", "NoSuchBucket", "403"):
            print("← doc bucket       (none)")
        else:
            raise

    print()
    print("✓ teardown complete")


# --- Main -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create (or tear down) a Bedrock Knowledge Base from a zip "
        "of documents, using Amazon S3 Vectors as the vector store."
    )
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="Delete every resource this script creates, then exit.",
    )
    args = parser.parse_args()

    if args.teardown:
        teardown()
    else:
        create()


if __name__ == "__main__":
    main()
