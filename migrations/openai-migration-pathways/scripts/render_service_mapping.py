#!/usr/bin/env python3
"""Validate and render the Azure-to-AWS service decision matrix."""

import argparse
import json
from pathlib import Path

CONTRACT = "azure-aws-service-mapping-v1"
PATTERNS = {"rehost", "replatform", "refactor", "replace", "retain", "retire", "unresolved"}
DECISIONS = {"confirmed", "recommended", "conditional", "unresolved"}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)

def text(value, name):
    require(isinstance(value, str) and value.strip(), f"Missing mapping {name}")
    return value.strip()

def text_list(value, name, *, allow_empty=False):
    require(isinstance(value, list), f"Invalid mapping {name}")
    require(allow_empty or value, f"Missing mapping {name}")
    require(all(isinstance(item, str) and item.strip() for item in value), f"Invalid mapping {name}")
    require(len(value) == len(set(value)), f"Duplicate mapping {name}")
    return value

def validate(mapping, graph=None, artifacts=None):
    require(mapping.get("contract") == CONTRACT, "Unsupported service-mapping contract")
    require(set(mapping) == {"contract", "source_commit", "entries"}, "Invalid service-mapping fields")
    text(mapping["source_commit"], "source commit")
    require(isinstance(mapping["entries"], list) and mapping["entries"], "Service mapping has no entries")
    nodes = {node["id"]: node for node in graph.get("nodes", [])} if graph else {}
    seen = set()
    required = {"id", "source_node_ids", "source_service", "target_node_ids", "target_service",
                "capability", "pattern", "decision", "rationale", "required_changes", "evidence"}
    for entry in mapping["entries"]:
        require(isinstance(entry, dict) and set(entry) == required, "Invalid service-mapping entry fields")
        ident = text(entry["id"], "id")
        require(ident not in seen, "Duplicate service-mapping entry")
        seen.add(ident)
        source_ids = text_list(entry["source_node_ids"], "source nodes")
        target_ids = text_list(entry["target_node_ids"], "target nodes",
                               allow_empty=entry["pattern"] in {"retain", "retire", "unresolved"})
        for field in ("source_service", "target_service", "capability"):
            text(entry[field], field)
        require(entry["pattern"] in PATTERNS, "Invalid migration pattern")
        require(entry["decision"] in DECISIONS, "Invalid mapping decision")
        require(len(text(entry["rationale"], "rationale")) >= 20, "Mapping rationale is too short")
        text_list(entry["required_changes"], "required changes")
        evidence = text_list(entry["evidence"], "evidence")
        if graph is not None:
            require(all(i in nodes and nodes[i]["cloud"] == "azure" for i in source_ids),
                    "Mapping source is not an Azure graph node")
            require(all(i in nodes and nodes[i]["cloud"] == "aws" for i in target_ids),
                    "Mapping target is not an AWS graph node")
        if artifacts is not None:
            require(all(name in artifacts and artifacts[name].strip() for name in evidence),
                    "Mapping evidence artifact is missing")
    return mapping["entries"]

def escape(value):
    return value.replace("|", "\\|").replace("\n", " ").strip()

def render(mapping, graph=None, artifacts=None):
    entries = validate(mapping, graph, artifacts)
    lines = ["# Azure to AWS service mapping", "",
             f"Repository commit: `{mapping['source_commit']}`", "",
             "This matrix records implementation decisions, not claims of one-to-one service equivalence.", "",
             "| Azure source | AWS target | Capability | Pattern | Decision | Rationale | Required changes | Evidence |",
             "|---|---|---|---|---|---|---|---|"]
    for entry in sorted(entries, key=lambda item: item["id"]):
        cells = [entry["source_service"], entry["target_service"], entry["capability"],
                 entry["pattern"], entry["decision"], entry["rationale"],
                 "; ".join(entry["required_changes"]),
                 "; ".join(f"`{item}`" for item in entry["evidence"])]
        lines.append("| " + " | ".join(escape(value) for value in cells) + " |")
    return ("\n".join(lines) + "\n").encode("utf-8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    mapping = load(args.mapping)
    require(not args.output.exists(), "Output already exists")
    args.output.write_bytes(render(mapping))
    print(f"Rendered service mapping: {args.output}")

if __name__ == "__main__":
    main()
