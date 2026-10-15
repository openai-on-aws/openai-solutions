#!/usr/bin/env python3
"""Check package consistency and artifact hashes; this does not certify deployment."""

import argparse
import hashlib
import importlib.util
from pathlib import Path
import re

_renderer_spec = importlib.util.spec_from_file_location(
    "migration_package_renderer",
    Path(__file__).resolve().with_name("render_architecture.py"),
)
if _renderer_spec is None or _renderer_spec.loader is None:
    raise RuntimeError("Bundled architecture renderer is missing")
_renderer = importlib.util.module_from_spec(_renderer_spec)
_renderer_spec.loader.exec_module(_renderer)
load, render, require = _renderer.load, _renderer.render, _renderer.require

_mapping_spec = importlib.util.spec_from_file_location(
    "migration_service_mapping",
    Path(__file__).resolve().with_name("render_service_mapping.py"),
)
if _mapping_spec is None or _mapping_spec.loader is None:
    raise RuntimeError("Bundled service-mapping renderer is missing")
_mapping = importlib.util.module_from_spec(_mapping_spec)
_mapping_spec.loader.exec_module(_mapping)

_assessment_spec = importlib.util.spec_from_file_location(
    "migration_assessment", Path(__file__).resolve().with_name("verify_assessment.py")
)
if _assessment_spec is None or _assessment_spec.loader is None:
    raise RuntimeError("Bundled assessment checker is missing")
_assessment = importlib.util.module_from_spec(_assessment_spec)
_assessment_spec.loader.exec_module(_assessment)

LEVELS = ["source_only", "statically_checked", "build_verified", "deployment_verified"]
REQUIRED = [
    "assessment.md",
    "assessment-contract.json",
    "deployment/ai-routes.json",
    "evidence.json",
    "migration-waves.md",
    "validation.json",
    "implementation-ledger.json",
    "service-mapping.json",
    "service-mapping.md",
    "deployment/README.md",
    "architecture/architecture.json",
    "architecture/migration-deployment-architecture.svg",
    "architecture/migration-deployment-architecture.drawio",
]


def files(root):
    result = {}
    for path in sorted(root.rglob("*")):
        require(
            not path.is_symlink(), f"Symlink is not a portable package artifact: {path}"
        )
        relative = path.relative_to(root).as_posix()
        require(
            not any(
                part in {".git", ".terraform", "__pycache__", "node_modules"}
                for part in path.relative_to(root).parts
            ),
            f"Remove cache/checkout content from package: {relative}",
        )
        require(
            path.name != ".env"
            and path.suffix.lower() not in {".pem", ".key", ".tfstate"},
            f"Remove potentially secret-bearing file: {relative}",
        )
        require(
            "\n" not in relative and "\r" not in relative, "Invalid artifact filename"
        )
        if path.is_file() and relative != "checksums.sha256":
            result[relative] = path.read_bytes()
    return result


def execution_scope(check):
    """Validate optional execution annotations; older receipts remain readable."""
    if "execution" not in check:
        return None
    execution = check["execution"]
    require(isinstance(execution, dict), "Invalid execution annotation")
    require(set(execution) == {"subject", "mode", "environment", "substitutes"}, "Invalid execution fields")
    require(isinstance(execution["subject"], str) and execution["subject"] in {"application", "helper", "fixture"}, "Invalid execution subject")
    require(isinstance(execution["mode"], str) and execution["mode"] in {"source", "fragments", "import", "local", "build", "deployed"}, "Invalid execution mode")
    require(isinstance(execution["environment"], str) and execution["environment"].strip(), "Missing execution environment")
    substitutes = execution["substitutes"]
    require(isinstance(substitutes, list) and all(isinstance(item, str) and item.strip() for item in substitutes), "Invalid execution substitutes")
    require(len(set(substitutes)) == len(substitutes), "Duplicate execution substitutes")
    if check["status"] == "passed":
        if check["category"] == "build":
            require(execution["mode"] == "build", "A build check must record an actual build")
        if check["category"] == "deployment":
            require(execution["mode"] == "deployed" and execution["subject"] == "application" and not substitutes,
                    "Deployment evidence cannot be a local or substituted execution")
    return execution


def qualifies_for_stage(check, category):
    execution = check.get("execution")
    if execution is None or category == "static":
        return True
    if category == "build":
        return execution["subject"] == "application" and execution["mode"] == "build" and not execution["substitutes"]
    return execution["subject"] == "application" and execution["mode"] == "deployed" and not execution["substitutes"]


def audit(root):
    artifacts = files(root)
    for name in REQUIRED:
        require(
            name in artifacts and artifacts[name].strip(), f"Missing artifact: {name}"
        )
    _assessment.audit(root, package=True)
    evidence = load(root / "evidence.json")
    graph = load(root / "architecture/architecture.json")
    commit = evidence.get("source_commit")
    require(
        isinstance(commit, str)
        and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit),
        "Missing resolved source commit",
    )
    require(graph.get("source_commit") == commit, "Architecture/source commit mismatch")
    mapping = _mapping.load(root / "service-mapping.json")
    require(mapping.get("source_commit") == commit, "Service mapping/source commit mismatch")
    require(
        artifacts["service-mapping.md"] == _mapping.render(mapping, graph, artifacts),
        "Service-mapping Markdown differs from its semantic JSON",
    )
    if "implementation_revision" in graph:
        revision = graph["implementation_revision"]
        require(isinstance(revision, dict), "Invalid architecture implementation revision")
        patch_name = revision.get("patch_path", "deployment/application/agent-aws-runtime.patch")
        patch_digest = revision.get("patch_sha256")
        require(isinstance(patch_name, str) and patch_name in artifacts,
                "Architecture implementation patch is missing")
        require(isinstance(patch_digest, str) and re.fullmatch(r"[0-9a-f]{64}", patch_digest),
                "Invalid architecture implementation digest")
        require(hashlib.sha256(artifacts[patch_name]).hexdigest() == patch_digest,
                "Architecture implementation digest differs from delivered patch")
    svg, drawio = render(graph)
    require(
        artifacts["architecture/migration-deployment-architecture.svg"] == svg,
        "SVG differs from semantic graph",
    )
    require(
        artifacts["architecture/migration-deployment-architecture.drawio"] == drawio,
        "Draw.io differs from semantic graph",
    )
    validation = load(root / "validation.json")
    require(validation.get("readiness") in LEVELS, "Invalid package readiness")
    components = {}
    for component in validation["components"]:
        require(component["id"] not in components, "Duplicate component")
        require(
            component["readiness"] in LEVELS and type(component["required"]) is bool,
            "Invalid component readiness",
        )
        components[component["id"]] = component
    required = [c for c in components.values() if c["required"]]
    require(required, "No required components recorded")
    require(
        LEVELS.index(validation["readiness"])
        <= min(LEVELS.index(c["readiness"]) for c in required),
        "Package readiness exceeds component evidence",
    )
    seen = set()
    for check in validation["checks"]:
        require(check["id"] not in seen, "Duplicate validation check")
        seen.add(check["id"])
        require(
            check["status"] in {"passed", "failed", "blocked", "not_run"},
            "Invalid check status",
        )
        require(
            check["category"]
            in {"static", "build", "deployment", "smoke", "visual", "coverage"},
            "Invalid check category",
        )
        require(
            isinstance(check["reason"], str) and isinstance(check["scope"], list),
            "Missing check reason/scope",
        )
        require(
            all(ident in components for ident in check["scope"]),
            "Check names unknown component",
        )
        require(isinstance(check["evidence"], list), "Missing check evidence list")
        if check["status"] == "passed":
            require(check["evidence"], "Passed check needs saved evidence")
        for name in check["evidence"]:
            require(
                name in artifacts and artifacts[name].strip(),
                f"Missing check evidence: {name}",
            )
        execution_scope(check)
    for component in components.values():
        level = LEVELS.index(component["readiness"])
        categories = (
            (["static"] if level >= 1 else [])
            + (["build"] if level >= 2 else [])
            + (["deployment", "smoke"] if level >= 3 else [])
        )
        for category in categories:
            relevant = [
                check
                for check in validation["checks"]
                if check["category"] == category and component["id"] in check["scope"]
            ]
            require(
                relevant and all(check["status"] == "passed" for check in relevant)
                and any(qualifies_for_stage(check, category) for check in relevant),
                f"Unproven {category} readiness: {component['id']}",
            )
    ledger = load(root / "implementation-ledger.json")
    capability_ids = set()
    covered_components = set()
    graph_ids = {node["id"] for node in graph["nodes"]}
    for capability in ledger["capabilities"]:
        require(capability["id"] not in capability_ids, "Duplicate capability")
        capability_ids.add(capability["id"])
        component = capability["component_id"]
        require(component in components, "Capability names unknown component")
        covered_components.add(component)
        require(
            capability["status"]
            in {"implemented", "architecture_only", "blocked", "verified"},
            "Invalid capability status",
        )
        require(
            capability["source_evidence"] and capability["required_tests"],
            "Capability needs source evidence and acceptance tests",
        )
        require(
            all(ident in graph_ids for ident in capability["target_node_ids"]),
            "Capability names unknown target node",
        )
        paths = capability["implementation_paths"]
        require(
            all(name in artifacts for name in paths),
            "Capability implementation artifact missing",
        )
        if capability["status"] in {"implemented", "verified"}:
            require(paths, "Implemented capability has no source artifact")
        if capability["status"] == "verified":
            require(
                LEVELS.index(components[component]["readiness"]) >= 2,
                "Verified capability lacks build evidence",
            )
        if capability["status"] in {"blocked", "architecture_only"}:
            require(
                LEVELS.index(components[component]["readiness"]) <= 1,
                "Component promoted with unimplemented capability",
            )
    require(
        all(c["id"] in covered_components for c in required),
        "Required component missing capability ledger",
    )
    return artifacts, validation["readiness"]


def manifest(artifacts):
    return "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(artifacts.items())
    )


def verify(root, seal=False):
    artifacts, readiness = audit(root)
    receipt = root / "checksums.sha256"
    expected = manifest(artifacts)
    if seal:
        with receipt.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(expected)
    require(
        receipt.is_file() and not receipt.is_symlink(),
        "Missing checksums.sha256; use --seal once after finalizing",
    )
    require(
        receipt.read_text(encoding="utf-8") == expected,
        "Package hashes changed or file inventory differs",
    )
    return len(artifacts), readiness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument(
        "--seal",
        action="store_true",
        help="Write a new checksum manifest after all checks pass",
    )
    args = parser.parse_args()
    count, readiness = verify(args.package.resolve(), args.seal)
    print(
        f"PASS: {count} artifacts; graph/render parity; recorded readiness: {readiness}."
    )
    print(
        "This checks consistency and hashes, not the authenticity or sufficiency of test evidence."
    )


if __name__ == "__main__":
    main()
