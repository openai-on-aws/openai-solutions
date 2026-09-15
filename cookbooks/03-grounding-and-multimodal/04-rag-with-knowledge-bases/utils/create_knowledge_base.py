"""Provision a Bedrock Knowledge Base from a directory of documents, end to end.

This is the automation companion to Appendix A of the recipe README. It takes a
directory of source documents (default: the NASA wind-tunnel corpus in the
recipe's ``assets/`` folder) and stands up everything a Bedrock Knowledge Base
needs, using **Amazon S3 Vectors** as the vector store — the lowest-friction,
lowest-cost option, with no cluster or index policies to manage:

    1. Scan the source directory for documents (``.txt``; the HTML index and
       other non-document files are skipped).
    2. Create an S3 bucket and upload the documents (the KB data source), each
       with a ``.metadata.json`` sidecar carrying its public source URL so
       retrieval can cite the real link, not just the S3 URI.
    3. Create an S3 Vectors vector bucket + index (the vector store).
    4. Create an IAM service role the KB assumes (embed model + S3 + S3 Vectors).
    5. CreateKnowledgeBase (VECTOR / S3_VECTORS, Titan embed text v2).
    6. CreateDataSource (S3) and StartIngestionJob.

The retrieval recipe reads the ``source_url`` metadata attribute back from each
retrieved chunk (``retrievalResults[].metadata``) to render proper citations.

Every step is idempotent: re-running reuses resources that already exist by name,
so a partial run can be resumed. Configuration comes from the environment; nothing
is hard-coded except sensible defaults. Credentials come from the standard AWS
credential chain (env vars, shared config, or an assumed role) — there are no
secrets in this file.

Run it from the cookbooks/ directory:

    uv run --env-file .env python \
      03-grounding-and-multimodal/04-rag-with-knowledge-bases/utils/create_knowledge_base.py

Tear everything down again (KB, data source, role, buckets, vector store) by
passing ``--teardown`` to the same script:

    uv run --env-file .env python .../utils/create_knowledge_base.py --teardown

Environment variables (all optional except where noted):

    AWS_REGION            Region for every resource   (default us-east-1)
    KB_NAME               Knowledge Base name         (default nasa-windtunnel-kb)
    KB_SOURCE_DIR         Directory of documents      (default the recipe's
                          assets/ folder)
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

# How long to wait (seconds) for the KB to become ACTIVE after creation.
# KB provisioning can take a few minutes; the wait is generous and resumable.
KB_ACTIVE_TIMEOUT = int(os.environ.get("KB_ACTIVE_TIMEOUT", "600"))

VECTOR_BUCKET = os.environ.get("KB_VECTOR_BUCKET", f"{KB_NAME}-vectors")
VECTOR_INDEX = os.environ.get("KB_VECTOR_INDEX", f"{KB_NAME}-index")
ROLE_NAME = os.environ.get("KB_ROLE_NAME", f"{KB_NAME}-role")

# The documents live in the recipe's assets/ folder, which sits alongside this
# utils/ directory (i.e. one level up). Default to that so the script runs the
# same regardless of the current working directory; override with KB_SOURCE_DIR.
_DEFAULT_SOURCE_DIR = Path(__file__).resolve().parent.parent / "assets"

SOURCE_DIR = Path(
    os.environ.get("KB_SOURCE_DIR", str(_DEFAULT_SOURCE_DIR))
).expanduser()

# Document extensions to ingest. Everything else in the source directory (the
# HTML index, stray metadata sidecars, etc.) is skipped.
DOCUMENT_EXTENSIONS = {".txt"}

# Public source URL for each document, keyed by the file stem (name without
# extension). Uploaded to S3 as a per-document metadata sidecar so retrieval
# returns the real citation link (NTRS record) instead of only the S3 URI.
# These are the NASA Technical Reports Server records for the corpus; see the
# NASA_Wind_Tunnel_Reports_index.html in this folder.
SOURCE_URLS = {
    "01_Acoustic_Testing_Tiltrotor_TestRig_40x80": "https://ntrs.nasa.gov/citations/20190025111",
    "03_Cryogenic_Force_Balance_Calibration": "https://ntrs.nasa.gov/citations/20190027135",
    "04_9x15_AeroThermal_Characterization": "https://ntrs.nasa.gov/citations/20210016041",
    "05_Capabilities_Unitary_Plan_Wind_Tunnel": "https://ntrs.nasa.gov/citations/20170011246",
    "06_9x15_Acoustic_Improvement_Program": "https://ntrs.nasa.gov/citations/20210016839",
    "07_Acoustic_Testing_Tiltrotor_TestRig_companion": "https://ntrs.nasa.gov/citations/20190025116",
    "08_FlowVisualization_HighSpeed": "https://ntrs.nasa.gov/citations/20010046863",
    "09_DMD_PressureSensitivePaint": "https://ntrs.nasa.gov/citations/20230006831",
    "12_CompositeLift_VTOL_Model": "https://ntrs.nasa.gov/citations/19690018719",
    "13_FullScale_Proprotor_Performance_Tests": "https://ntrs.nasa.gov/citations/20210021871",
    "14_9x15_Acoustic_Improvements": "https://ntrs.nasa.gov/citations/20210017002",
    "15_Tiltrotor_TestRig_Data_Catalog": "https://ntrs.nasa.gov/citations/20240008170",
    "16_CFD_based_Wind_Tunnel_Calibrations": "https://ntrs.nasa.gov/citations/20230015022",
    "17_ERA_Integrated_CFD_HybridWingBody": "https://ntrs.nasa.gov/citations/20170006533",
    "19_FullScale_Proprotor_Addendum": "https://ntrs.nasa.gov/citations/20260001349",
    "22_Mars_Retropropulsion_Langley_UPWT": "https://ntrs.nasa.gov/citations/20210024629",
    "23_CRM_ETW_vs_NASA_Comparison": "https://ntrs.nasa.gov/citations/20150006851",
    "24_VTOL_Propellers_in_Descent": "https://ntrs.nasa.gov/citations/19630003345",
}

EMBED_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/{EMBED_MODEL}"

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


# --- Step 1: Collect documents ----------------------------------------------

def collect_documents() -> list[Path]:
    """List the documents in the source directory (recursively).

    Skips hidden files and macOS resource-fork junk (``._*``) so a directory
    populated by unzipping a macOS archive is safe to use as-is.
    """
    if not SOURCE_DIR.is_dir():
        sys.exit(f"Source directory not found: {SOURCE_DIR}")

    docs = [
        p
        for p in sorted(SOURCE_DIR.rglob("*"))
        if p.is_file()
        and not p.name.startswith(".")
        and not p.name.startswith("._")
        and p.suffix.lower() in DOCUMENT_EXTENSIONS
        and not p.name.endswith(".metadata.json")
    ]
    if not docs:
        sys.exit(
            f"No documents ({', '.join(sorted(DOCUMENT_EXTENSIONS))}) found "
            f"in {SOURCE_DIR}"
        )
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


def _metadata_sidecar(source_url: str) -> bytes:
    """Build a Bedrock KB metadata sidecar carrying the document's source URL.

    ``includeForEmbedding`` is False so the URL is retrievable citation data
    without polluting the embedded text. The attribute comes back on every
    retrieved chunk in ``retrievalResults[].metadata`` so the generation step
    can cite the real link instead of the S3 URI.
    """
    doc = {
        "metadataAttributes": {
            "source_url": {
                "value": {"type": "STRING", "stringValue": source_url},
                "includeForEmbedding": False,
            }
        }
    }
    return json.dumps(doc).encode("utf-8")


def upload_documents(c: dict, bucket: str, docs: list[Path]) -> int:
    """Upload each document under a documents/ prefix, with metadata sidecars.

    For every document whose stem has a known source URL, also uploads a
    ``<name>.metadata.json`` sidecar next to it so retrieval returns the URL.
    Returns the number of sidecars written.
    """
    sidecars = 0
    for doc in docs:
        key = f"documents/{doc.name}"
        c["s3"].upload_file(str(doc), bucket, key)

        source_url = SOURCE_URLS.get(doc.stem)
        if source_url:
            c["s3"].put_object(
                Bucket=bucket,
                Key=f"{key}.metadata.json",
                Body=_metadata_sidecar(source_url),
                ContentType="application/json",
            )
            sidecars += 1
    return sidecars


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
            # S3 Vectors caps *filterable* metadata at 2 KB per vector. Bedrock
            # stores the chunk text under AMAZON_BEDROCK_TEXT, which easily
            # exceeds that, so mark it non-filterable to keep it out of the
            # filterable budget (it stays retrievable). source_url and other
            # small attributes remain filterable. This cannot be changed after
            # the index is created.
            metadataConfiguration={
                "nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT"]
            },
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


def _wait_kb_active(c: dict, kb_id: str, timeout: int = KB_ACTIVE_TIMEOUT) -> None:
    """Poll until the KB leaves CREATING; raise if it fails or times out.

    Creating a knowledge base (provisioning the vector store binding) can take
    several minutes, so the default timeout is generous and overridable via
    KB_ACTIVE_TIMEOUT. Because create is idempotent (it reuses a KB with the
    same name), re-running the script after a timeout simply resumes the wait.
    """
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
    sys.exit(
        f"Timed out after {timeout}s waiting for knowledge base {kb_id} to "
        f"become ACTIVE (it is still CREATING). Re-run the script to resume — "
        f"create is idempotent and will pick up the same knowledge base. To "
        f"wait longer, set KB_ACTIVE_TIMEOUT to a larger value."
    )


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
    print(f"   source_dir        {SOURCE_DIR}")
    print(f"   doc_bucket        {doc_bucket}")
    print(f"   vector_bucket     {VECTOR_BUCKET}")
    print(f"   vector_index      {VECTOR_INDEX}")
    print(f"   embed_model       {EMBED_MODEL}")
    print(f"   embed_dimension   {EMBED_DIMENSION}")
    print()

    docs = collect_documents()
    print(f"← documents        {len(docs)} files from {SOURCE_DIR.name}/")

    ensure_bucket(c, doc_bucket)
    sidecars = upload_documents(c, doc_bucket, docs)
    print(f"← upload           s3://{doc_bucket}/documents/ ({len(docs)} docs)")
    print(f"   metadata sidecars {sidecars} (source_url for citations)")

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
        description="Create (or tear down) a Bedrock Knowledge Base from a "
        "directory of documents, using Amazon S3 Vectors as the vector store."
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
