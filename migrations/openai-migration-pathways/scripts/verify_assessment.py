#!/usr/bin/env python3
"""Render and check declared assessment coverage; does not certify source completeness."""

import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlparse
import verify_report


CONTRACT = "azure-aws-assessment-v1"
FEATURES = (
    "instructions", "input", "output", "parameters", "tools", "history",
    "streaming", "auth", "errors", "retries", "retention", "modalities",
)
HEADINGS = (
    "Decision and target-model recommendations",
    "Scope, evidence and execution provenance",
    "Workload and route inventory",
    "Source AI contracts",
    "Bedrock feature mapping and API migration",
    "Azure-to-AWS service mapping",
    "Unified architecture and data flows",
    "Deployment implementation and gaps",
    "Validation, readiness and next actions",
)
BLOCK_SECTIONS = {"models": 0, "routes": 2, "source-contracts": 3, "api-mapping": 4}
MODEL_FIELDS = (
    "model_id", "region", "endpoint", "base_url", "inference_path", "api", "inference_geography",
)
CLAIMS = {"model_id", "region", "endpoint", "api", "inference_geography"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def texts(value, nonempty=False):
    return isinstance(value, list) and (bool(value) or not nonempty) and all(text(x) for x in value)


def need_texts(obj, keys, context):
    for key in keys:
        require(text(obj.get(key)), f"{context}: missing {key}")


def indexed(items, context):
    require(isinstance(items, list), f"{context}: expected a list")
    result = {}
    for item in items:
        require(isinstance(item, dict) and text(item.get("id")), f"{context}: missing id")
        require(item["id"] not in result, f"{context}: duplicate id {item['id']}")
        result[item["id"]] = item
    return result


def file_refs(root, values, context, nonempty=True):
    require(texts(values, nonempty), f"{context}: missing evidence file list")
    for value in values:
        path = Path(value)
        require(not path.is_absolute() and ".." not in path.parts, f"{context}: unsafe path")
        target = root / path
        require(target.resolve().is_relative_to(root.resolve()), f"{context}: escaped evidence path")
        require(target.is_file() and target.stat().st_size, f"{context}: missing evidence {value}")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root, data, package=False, historical=False):
    require(data.get("contract") == CONTRACT, "Unsupported assessment contract")
    require(re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", data.get("source_commit", "")),
            "Assessment requires a resolved source commit")
    provenance = data.get("provenance", {})
    need_texts(provenance, ("plugin_name", "plugin_version", "skill_path"), "provenance")
    require(re.fullmatch(r"[a-f0-9]{64}", provenance.get("skill_sha256", "")),
            "Missing loaded skill digest")
    policy = data.get("evidence_policy")
    require(policy in {"repository_only", "repository_and_official_docs"}, "Invalid evidence policy")
    model_policy = data.get("model_policy", {})
    require(texts(model_policy.get("allowed_providers")), "Missing allowed model providers")
    need_texts(model_policy, ("constraint",), "model policy")
    coverage = data.get("coverage", {})
    require(coverage.get("status") in {"complete", "partial"}, "Missing coverage status")
    need_texts(coverage, ("scope",), "coverage")
    require(texts(coverage.get("reviewed_paths"), True), "Missing reviewed source paths")
    require(texts(coverage.get("omissions")), "Missing omissions list")
    require((coverage["status"] == "partial") == bool(coverage["omissions"]),
            "Coverage status contradicts omissions")
    file_refs(root, coverage.get("discovery_evidence"), "discovery")
    discoveries = indexed(data.get("discoveries"), "discoveries")
    require(discoveries, "Record discovery results, including excluded/no-route scope")
    routes = indexed(data.get("routes"), "routes")
    models = indexed(data.get("models"), "models")
    linked = set()
    for ident, item in discoveries.items():
        need_texts(item, ("kind", "source_location", "reason"), ident)
        file_refs(root, item.get("evidence"), ident)
        require(item.get("disposition") in {"included", "excluded"}, f"{ident}: invalid disposition")
        if item["disposition"] == "included":
            require(item.get("route_id") in routes, f"{ident}: discovered route is unaccounted for")
            linked.add(item["route_id"])
        else:
            require(item.get("route_id") is None, f"{ident}: excluded item names an included route")
    require(linked == set(routes), "Routes and discovered call sites do not agree")
    revision = data.get("assessment_revision", 1)
    require(revision in {1, 2, 3}, "Unsupported assessment revision")
    approved = json.loads((Path(__file__).resolve().parents[1] / "data/capabilities.json").read_text())["target_policy"]
    official_paths = set()
    for ident, model in models.items():
        need_texts(model, ("provider", "name", "region", "endpoint", "base_url", "inference_path", "api",
                          "inference_geography", "rationale", "fallback_policy", "verification_notes"), ident)
        require(not model_policy["allowed_providers"] or model["provider"] in model_policy["allowed_providers"],
                f"{ident}: model violates allowed-provider policy")
        require(model.get("model_id") is None or text(model["model_id"]), f"{ident}: invalid model ID")
        require(texts(model.get("evaluation_criteria"), True), f"{ident}: missing model evaluation")
        require(model.get("verification") in {"documented", "unverified", "blocked"},
                f"{ident}: invalid model verification")
        if revision >= 2 and model.get("model_id"):
            base_id = re.sub(r"^(us|in|global)\.", "", model["model_id"])
            require(base_id in approved["allowed_base_model_ids"], f"{ident}: target outside approved nine-model catalog")
        refs = model.get("official_evidence")
        require(isinstance(refs, list), f"{ident}: missing official evidence list")
        require(policy != "repository_only" or not refs, "Official evidence violates repository-only policy")
        claims = set()
        for ref in refs:
            need_texts(ref, ("url", "snapshot_path", "checked_at"), ident)
            url = urlparse(ref["url"])
            require(url.scheme == "https" and url.hostname in {
                "docs.aws.amazon.com", "aws.amazon.com", "developers.openai.com",
                "platform.openai.com", "openai.com", "learn.microsoft.com",
            }, f"{ident}: expected official documentation URL")
            require(re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", ref["checked_at"]),
                    f"{ident}: missing documentation retrieval date")
            file_refs(root, [ref["snapshot_path"]], ident)
            require(texts(ref.get("supports"), True) and set(ref["supports"]) <= CLAIMS,
                    f"{ident}: invalid model evidence claims")
            claims.update(ref["supports"])
            official_paths.add(ref["snapshot_path"])
        if model["verification"] == "documented":
            require(text(model.get("model_id")) and claims == CLAIMS,
                    f"{ident}: documented model lacks exact ID/route evidence")
            require(model["endpoint"] in {"bedrock-runtime", "bedrock-mantle"},
                    f"{ident}: documented Bedrock decision has an unknown endpoint")
            base = urlparse(model["base_url"])
            require(base.scheme == "https" and base.hostname
                    and base.hostname.startswith(model["endpoint"] + "." + model["region"] + "."),
                    f"{ident}: endpoint/Region and URL disagree")
            require(model["inference_path"].startswith("/"), f"{ident}: missing inference URL path")
    ai_ids = {ident for ident, route in routes.items() if route.get("kind") == "ai_call"}
    require(ai_ids or text(coverage.get("no_ai_reason")), "Missing explanation for no AI calls")
    used_models = set()
    for ident, route in routes.items():
        need_texts(route, ("workload", "source_location", "trigger", "purpose", "disposition"), ident)
        require(route.get("kind") in {"http", "websocket", "worker", "scheduled", "local",
                                      "tool", "external_call", "ai_call"}, f"{ident}: invalid route kind")
        require(route.get("runtime_scope") in {"runtime", "optional"}, f"{ident}: missing runtime scope")
        file_refs(root, route.get("evidence"), ident)
        require(texts(route.get("acceptance_criteria"), True), f"{ident}: missing acceptance criteria")
        for key in ("ai_route_ids", "service_mapping_ids", "target_node_ids", "capability_ids"):
            require(texts(route.get(key)), f"{ident}: missing {key}")
            require(len(route[key]) == len(set(route[key])), f"{ident}: duplicate {key}")
        usage = route.get("ai_usage")
        require(usage in {"direct", "indirect", "none"}, f"{ident}: invalid AI usage")
        require(set(route["ai_route_ids"]) <= ai_ids, f"{ident}: caller references absent AI call")
        if ident in ai_ids:
            require(usage == "direct" and route["ai_route_ids"] == [ident],
                    f"{ident}: AI call must identify itself")
        else:
            require(usage != "direct", f"{ident}: direct invocation must be an ai_call")
            require(bool(route["ai_route_ids"]) == (usage == "indirect"),
                    f"{ident}: indirect/none AI linkage is inconsistent")
            continue
        source = route.get("source_contract", {})
        need_texts(source, ("sdk_method", "source_model") + FEATURES, ident)
        require("model_ref" in route, f"{ident}: missing target-model decision")
        model_ref = route["model_ref"]
        if model_ref is None:
            require(text(route.get("target_gap")), f"{ident}: unselected model needs explicit gap")
        else:
            require(model_ref in models, f"{ident}: unknown model decision")
            used_models.add(model_ref)
        mappings = route.get("feature_mapping")
        require(isinstance(mappings, list) and len(mappings) == len(FEATURES),
                f"{ident}: incomplete API feature mapping")
        require({m.get("feature") for m in mappings} == set(FEATURES),
                f"{ident}: missing or duplicate API feature")
        for mapping in mappings:
            need_texts(mapping, ("source_behavior", "target_behavior", "implementation"), ident)
            require(mapping.get("status") in {"supported", "application_change", "other_service",
                                              "unsupported", "unverified", "not_applicable"},
                    f"{ident}: invalid feature support")
            file_refs(root, mapping.get("evidence"), ident)
            if mapping["status"] == "supported":
                selected_paths = {ref["snapshot_path"] for ref in models[model_ref]["official_evidence"]} if model_ref else set()
                require(selected_paths.intersection(mapping["evidence"]),
                        f"{ident}: supported feature lacks selected-model official evidence")
        if revision >= 2:
            decision = route.get("route_selection", {})
            need_texts(decision, ("rationale", "tradeoffs", "next_validation"), ident)
            require(texts(decision.get("alternatives")), f"{ident}: missing alternatives")
            require(model_ref is None or text(decision.get("selected_candidate_id")), f"{ident}: missing exact selected candidate")
            gaps = indexed(route.get("gaps"), ident + " gaps")
            changed = {m["feature"] for m in mappings if m["status"] not in {"supported", "not_applicable"}}
            require({g.get("feature") for g in gaps.values()} == changed, f"{ident}: every feature gap needs an explicit disposition")
            for gap in gaps.values():
                need_texts(gap, ("proposed_change", "control_flow", "state", "failure_handling", "behavior_difference"), ident)
                require(texts(gap.get("affected_files"), True) and texts(gap.get("required_tests"), True), f"{ident}: gap needs affected files and tests")
                require(gap.get("kind") in {"application", "service", "orchestration", "blocker", "investigation"}, f"{ident}: invalid gap kind")
                require(gap.get("implementation_status") in {"design_only", "implemented", "verified", "blocked"}, f"{ident}: invalid implementation status")
                file_refs(root, gap.get("evidence"), ident)
                if gap["implementation_status"] in {"implemented", "verified"}:
                    file_refs(root, gap.get("implementation_paths"), ident)
                if gap["implementation_status"] == "verified":
                    file_refs(root, gap.get("validation_evidence"), ident)
        need_texts(route.get("examples", {}), ("source_request", "target_request", "target_response"), ident)
    require(used_models == set(models), "Model recommendations include unused/unmapped decisions")
    if revision >= 3:
        shared = load(root / "report-contract.json")
        require(shared.get("mode") == "code_assessment", "Code assessment requires the matching shared report mode")
        verify_report.validate(root, shared, assessment=data, package=package, historical=historical)
    if package:
        mapping = load(root / "service-mapping.json")
        graph = load(root / "architecture/architecture.json")
        ledger = load(root / "implementation-ledger.json")
        evidence = load(root / "evidence.json")
        for obj in (mapping, graph, evidence):
            require(obj.get("source_commit") == data["source_commit"], "Assessment/source commit mismatch")
        mapping_ids = set(indexed(mapping.get("entries"), "service mappings"))
        node_ids = set(indexed(graph.get("nodes"), "graph nodes"))
        capability_ids = set(indexed(ledger.get("capabilities"), "capabilities"))
        for ident, route in routes.items():
            for key, allowed in (("service_mapping_ids", mapping_ids),
                                 ("target_node_ids", node_ids), ("capability_ids", capability_ids)):
                require(set(route[key]) <= allowed, f"{ident}: unknown {key}")
                if key != "target_node_ids":
                    require(route[key], f"{ident}: missing deployment {key}")
        require(load(root / "deployment/ai-routes.json") == deployment_routes(data),
                "Deployment model routes differ from assessment decisions")


def cell(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\n", "<br>")


def table(headers, rows):
    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    )


def blocks(data):
    models = {m["id"]: m for m in data["models"]}
    ai = [r for r in data["routes"] if r["kind"] == "ai_call"]
    recommendations = []
    for route in ai:
        model = models.get(route["model_ref"])
        recommendations.append((
            route["id"],
            f'{model["name"]} / {model["model_id"] or "ID unverified"}' if model else "Unresolved",
            " / ".join(model[k] for k in ("region", "endpoint", "api", "inference_geography"))
            + " / " + model["base_url"] + " (inference path " + model["inference_path"] + ")" if model else route["target_gap"],
            model["rationale"] if model else route["target_gap"],
            f'{model["verification"]}: {model["verification_notes"]}' if model else "unresolved",
            "; ".join(model["evaluation_criteria"]) if model else "; ".join(route["acceptance_criteria"]),
            model["fallback_policy"] if model else "No selected fallback",
        ))
    no_ai = data["coverage"].get("no_ai_reason", "No AI calls recorded.")
    result = {
        "models": table(("AI route", "Recommended model / exact ID", "Region / endpoint / API / geography",
                         "Rationale", "Evidence state / constraints", "Evaluation", "Fallback policy"),
                        recommendations) if ai else no_ai,
        "routes": table(("Route", "Kind / scope", "Source / trigger", "Purpose / AI calls", "Target disposition"),
                        [(r["id"], f'{r["kind"]} / {r["runtime_scope"]}',
                          f'{r["source_location"]} / {r["trigger"]}',
                          r["purpose"] + " / " + ", ".join(r["ai_route_ids"]), r["disposition"])
                         for r in data["routes"]]),
        "source-contracts": "\n\n".join(
            f'### Source contract: {r["id"]}\n\n' + table(("Property", "Observed source behavior"),
                list(r["source_contract"].items())) for r in ai) if ai else no_ai,
        "api-mapping": "\n\n".join(
            f'### API migration: {r["id"]}\n\n'
            + table(("Feature", "Source behavior", "Target behavior", "Bedrock feature / implementation", "Status", "Evidence"),
                    [(m["feature"], m["source_behavior"], m["target_behavior"], m["implementation"],
                      m["status"], ", ".join(m["evidence"])) for m in r["feature_mapping"]])
            + "\n\n" + table(("Illustrative contract example", "Content"),
                              list(r["examples"].items()))
            + "\n\nAcceptance: " + "; ".join(r["acceptance_criteria"])
            for r in ai) if ai else no_ai,
    }
    if data.get("assessment_revision", 1) >= 2:
        result["models"] += "\n\n" + table(("AI role", "Selected candidate", "Decision and tradeoffs", "Alternatives", "Next validation"),
            [(r["id"], r["route_selection"].get("selected_candidate_id") or "Unresolved",
              r["route_selection"]["rationale"] + " / " + r["route_selection"]["tradeoffs"],
              "; ".join(r["route_selection"]["alternatives"]), r["route_selection"]["next_validation"]) for r in ai])
        result["api-mapping"] += "\n\n" + table(("AI role / feature", "Affected files", "Design", "State and failures", "Behavior difference", "Implementation status", "Required tests"),
            [(r["id"] + " / " + g["feature"], "; ".join(g["affected_files"]),
              g["proposed_change"] + " / " + g["control_flow"], g["state"] + " / " + g["failure_handling"],
              g["behavior_difference"], g["implementation_status"], "; ".join(g["required_tests"])) for r in ai for g in r["gaps"]])
    provenance = data["provenance"]
    result["routes"] = (
        f'Coverage: {data["coverage"]["status"]}. Scope: {cell(data["coverage"]["scope"])}.\n\n'
        f'Omissions: {cell("; ".join(data["coverage"]["omissions"]) or "None declared")}.\n\n'
        f'Executed skill: {cell(provenance["plugin_name"])} {cell(provenance["plugin_version"])}; '
        f'{cell(provenance["skill_path"])}; SHA-256 {provenance["skill_sha256"]}.\n\n'
        + result["routes"]
    )
    return result


def deployment_routes(data):
    models = {m["id"]: m for m in data["models"]}
    rows = []
    for route in data["routes"]:
        if route["kind"] != "ai_call":
            continue
        model = models.get(route["model_ref"])
        rows.append(dict(
            route_id=route["id"], model_ref=route["model_ref"],
            **{key: model[key] if model else None for key in MODEL_FIELDS},
            verification=model["verification"] if model else "unresolved",
        ))
    export = {"contract": "azure-aws-deployment-routes-v1",
              "source_commit": data["source_commit"], "routes": rows}
    if data.get("assessment_revision", 1) >= 2:
        export["assessment_revision"] = data["assessment_revision"]
        ai_routes = {r["id"]: r for r in data["routes"] if r["kind"] == "ai_call"}
        for row in rows:
            source = ai_routes[row["route_id"]]
            row["selected_candidate_id"] = source["route_selection"].get("selected_candidate_id")
            row["gap_statuses"] = [{"id": g["id"], "status": g["implementation_status"]} for g in source["gaps"]]
    return export


def sections(report):
    positions = []
    for title in HEADINGS:
        matches = list(re.finditer(r"^## " + re.escape(title) + r"\s*$", report, re.M))
        require(len(matches) == 1, f"Missing/duplicate assessment section: {title}")
        positions.append(matches[0].start())
    require(positions == sorted(positions), "Assessment sections are out of order")
    return [(start, positions[i + 1] if i + 1 < len(positions) else len(report))
            for i, start in enumerate(positions)]


def render_report(report, data):
    for name, body in blocks(data).items():
        start, end = sections(report)[BLOCK_SECTIONS[name]]
        begin = f"<!-- assessment:{name}:begin -->"
        finish = f"<!-- assessment:{name}:end -->"
        block = f"{begin}\n{body}\n{finish}"
        pattern = re.escape(begin) + r".*?" + re.escape(finish)
        found = list(re.finditer(pattern, report, re.S))
        if found:
            require(len(found) == 1 and start <= found[0].start() < found[0].end() <= end,
                    f"Misplaced/duplicate generated block: {name}")
            match = found[0]
            report = report[:match.start()] + block + report[match.end():]
        else:
            require(begin not in report and finish not in report, f"Broken block: {name}")
            report = report[:end].rstrip() + "\n\n" + block + "\n\n" + report[end:]
    return report


def audit(root, package=False, render=False, historical=False):
    root = Path(root)
    data = load(root / "assessment-contract.json")
    # Validate content before writing generated artifacts.
    validate(root, data, historical=historical)
    report_path = root / "assessment.md"
    report = report_path.read_text(encoding="utf-8")
    expected = render_report(report, data)
    if data.get("assessment_revision", 1) >= 3:
        shared = load(root / "report-contract.json")
        outcomes = verify_report.validate(root, shared, assessment=data, historical=historical)
        expected = verify_report.render_report(expected, shared, outcomes)
    if render:
        report_path.write_text(expected, encoding="utf-8")
        report = expected
        if package:
            (root / "deployment").mkdir(exist_ok=True)
            (root / "deployment/ai-routes.json").write_text(
                json.dumps(deployment_routes(data), indent=2) + "\n", encoding="utf-8")
    require(report == expected, "Assessment tables missing/stale; run verify_assessment.py --render")
    for start, end in sections(report):
        content = re.sub(r"<!-- (?:assessment|report):.*?:begin -->.*?<!-- (?:assessment|report):.*?:end -->",
                         "", report[start:end], flags=re.S).split("\n", 1)[-1].strip()
        require(content and not re.fullmatch(r"\[[^\]]+\]\([^)]+\)[.]?", content),
                "Assessment section needs findings, not only a generated table/link")
    if package:
        validate(root, data, package=True, historical=historical)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--render", action="store_true", help="Update main-report tables and package AI route export")
    parser.add_argument("--package", action="store_true", help="Also check deployment/graph/ledger bindings")
    parser.add_argument("--historical", action="store_true", help="Reproduce historical shared report evidence only")
    args = parser.parse_args()
    data = audit(args.output, package=args.package, render=args.render, historical=args.historical)
    print(f'PASS: declared route coverage and report parity; coverage={data["coverage"]["status"]}.')
    print("Does not prove source discovery completeness, model availability or runtime behavior.")


if __name__ == "__main__":
    main()
