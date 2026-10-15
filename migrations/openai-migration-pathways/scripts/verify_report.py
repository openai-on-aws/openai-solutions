#!/usr/bin/env python3
"""Render and validate shared discovery/code report tables. No cloud or model calls."""
import argparse
import json
from pathlib import Path
import re
import evaluate_routes

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
SECTIONS = {"scope": 1, "routes": 2, "orchestrations": 4, "service_mappings": 5, "blockers": 7}
EVIDENCE_KINDS = {"user_description", "repository", "cloud_inventory", "official_documentation",
                  "assumption", "validation"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return (isinstance(value, list) and all(text(x) for x in value)
            and len(value) == len(set(value)))


def fields(obj, names, context):
    require(all(text(obj.get(k)) for k in names), context + ": missing substantive fields")


def local(root, name):
    require(text(name) and not Path(name).is_absolute() and ".." not in Path(name).parts,
            "Unsafe report artifact path")
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), "Missing/escaped report artifact: " + name)
    return path


def load(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "Duplicate JSON field: " + key)
            obj[key] = value
        return obj
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def index(items, name):
    require(isinstance(items, list), "Missing report collection: " + name)
    result = {}
    for item in items:
        require(isinstance(item, dict) and text(item.get("id")), name + ": missing ID")
        require(item["id"] not in result, name + ": duplicate ID")
        result[item["id"]] = item
    return result


def references(obj, field, valid, context, nonempty=False):
    values = obj.get(field)
    require(strings(values) and (values or not nonempty), context + ": missing " + field)
    require(set(values) <= set(valid), context + ": unknown " + field + " reference")
    return values


def evaluate(root, entry, historical):
    registry_path = local(root, entry.get("registry"))
    registry = load(registry_path)
    evaluate_routes.validate_registry(registry, registry_path.parent)
    requirements = load(local(root, entry.get("requirements")))
    saved = load(local(root, entry.get("evaluation")))
    actual = evaluate_routes.evaluate(registry, requirements, saved["evaluated_at"])
    require(saved == actual, "Edited or unreproducible route evaluation")
    if not historical:
        current = evaluate_routes.evaluate(registry, requirements)
        require(saved["evaluated_at"] <= current["evaluated_at"], "Future-dated route evaluation")
        require(current["results"] == actual["results"], "Stale route evidence; refresh or use historical replay")
    selected = entry.get("selected_candidate_id")
    require(selected is None or text(selected), "Invalid selected candidate")
    candidate = next((x for x in actual["results"] if x["route_id"] == selected), None)
    require(selected is None or candidate is not None, "Selected candidate missing from evaluation")
    status = candidate["status"] if candidate else (
        "NO" if actual["results"] and all(x["status"] == "NO" for x in actual["results"]) else "VERIFY")
    return {"status": status, "candidate": candidate, "summary": actual["summary"]}


def validate(root, data, assessment=None, package=False, historical=False):
    root = Path(root)
    require(data.get("contract") == "migration-report-v1", "Unsupported shared report contract")
    mode = data.get("mode")
    require(mode in {"discovery", "code_assessment"}, "Invalid report mode")
    fields(data, ("scope", "limitations"), "report")
    if mode == "discovery":
        require(data.get("source_commit") is None, "Discovery must not invent a repository commit")
    else:
        if assessment is None:
            assessment = load(local(root, "assessment-contract.json"))
        require(assessment.get("assessment_revision", 1) >= 3, "Shared code reports require assessment revision 3")
        require(data.get("source_commit") == assessment.get("source_commit"), "Shared/source commit mismatch")
    collections = {name: index(data.get(name), name) for name in
                   ("evidence", "workloads", "routes", "blockers", "orchestrations", "service_mappings")}
    evidence, workloads, routes, blockers, orchestrations, mappings = (
        collections[x] for x in ("evidence", "workloads", "routes", "blockers", "orchestrations", "service_mappings"))
    require(evidence, "Save the supplied summary or other report evidence")
    reasons = data.get("empty_reasons", {})
    require(isinstance(reasons, dict), "Invalid empty_reasons")
    for name in ("workloads", "routes", "blockers", "orchestrations", "service_mappings"):
        if not collections[name]:
            require(text(reasons.get(name)), "Explain the empty report section: " + name)
    for ident, item in evidence.items():
        fields(item, ("description",), ident)
        require(item.get("kind") in EVIDENCE_KINDS, ident + ": invalid evidence kind")
        local(root, item.get("path"))
        require(mode != "discovery" or item["kind"] != "repository",
                "Discovery cannot claim repository inspection; use supplied-description evidence")
    def refs(item, name="evidence", nonempty=True):
        return references(item, name, evidence, item["id"], nonempty)
    for ident, item in workloads.items():
        fields(item, ("name", "description"), ident)
        require(item.get("scope_status") in {"confirmed", "conditional", "excluded"}, ident + ": invalid scope status")
        refs(item)
    outcomes = {}
    for ident, route in routes.items():
        fields(route, ("source_interface", "purpose", "rationale"), ident)
        require(route.get("workload_id") in workloads, ident + ": unknown workload")
        require(workloads[route["workload_id"]]["scope_status"] != "excluded", ident + ": route belongs to excluded workload")
        require(type(route.get("ai")) is bool, ident + ": ai must be boolean")
        refs(route)
        if route["ai"]:
            entry = route.get("evaluation")
            if entry is None:
                require(text(route.get("not_run_reason")), ident + ": AI route needs evaluation or an explicit reason")
                outcomes[ident] = {"status": "VERIFY", "candidate": None, "summary": {}}
            else:
                require(isinstance(entry, dict) and not text(route.get("not_run_reason")),
                        ident + ": contradictory evaluation disposition")
                outcomes[ident] = evaluate(root, entry, historical)
        else:
            require(route.get("evaluation") is None, ident + ": non-AI route cannot select a model")
            outcomes[ident] = {"status": "NOT_APPLICABLE", "candidate": None, "summary": {}}
    for ident, item in mappings.items():
        fields(item, ("source_service", "target_service", "rationale"), ident)
        references(item, "workload_ids", workloads, ident, True)
        references(item, "route_ids", routes, ident)
        references(item, "dependencies", mappings, ident)
        require(ident not in item["dependencies"], ident + ": self dependency")
        require(item.get("pattern") in {"rehost", "replatform", "refactor", "replace", "retain", "retire", "unresolved"},
                ident + ": invalid migration pattern")
        require(item.get("decision") in {"confirmed", "recommended", "conditional", "unresolved"}, ident + ": invalid service decision")
        require(item.get("source_evidence_state") in {"reported", "repository_inferred", "cloud_confirmed", "not_reported", "not_applicable"},
                ident + ": missing service evidence state")
        refs(item)
        require(strings(item.get("required_changes")) and item["required_changes"], ident + ": missing required changes")
        if item["source_evidence_state"] == "cloud_confirmed":
            require(any(evidence[e]["kind"] == "cloud_inventory" for e in item["evidence"]),
                    ident + ": deployed Azure service needs cloud inventory evidence")
        if item["source_evidence_state"] == "repository_inferred":
            require(mode == "code_assessment" and any(evidence[e]["kind"] == "repository" for e in item["evidence"]),
                    ident + ": repository inference needs repository evidence")
    for ident, item in blockers.items():
        fields(item, ("finding", "impact", "owner", "resolution"), ident)
        require(item.get("kind") in {"incompatibility", "missing_information", "implementation", "conflict"}, ident + ": invalid gap kind")
        require(item.get("priority") in {"high", "medium", "low"}, ident + ": invalid priority")
        require(item.get("status") in {"open", "deferred", "resolved"}, ident + ": invalid blocker status")
        references(item, "route_ids", routes, ident)
        references(item, "service_mapping_ids", mappings, ident)
        require(item["route_ids"] or item["service_mapping_ids"], ident + ": gap needs an affected route or service")
        require(strings(item.get("blocks")) and set(item["blocks"]) <= {"route_selection", "implementation", "validation", "cutover"},
                ident + ": invalid blocked stages")
        require(strings(item.get("required_tests")) and item["required_tests"], ident + ": missing acceptance tests")
        refs(item)
        if item["status"] == "resolved":
            refs(item, "resolution_evidence")
    for ident, item in orchestrations.items():
        fields(item, ("name", "state", "permissions", "failure_handling", "behavior_difference"), ident)
        require(item.get("origin") in {"existing", "proposed"}, ident + ": missing orchestration origin")
        require(item.get("acceptance") in {"proposed", "accepted", "rejected", "not_required"}, ident + ": invalid acceptance")
        require(item["origin"] == "existing" or item["acceptance"] != "not_required", ident + ": proposed redesign needs an acceptance disposition")
        require(item.get("implementation_status") in {"design_only", "implemented", "verified", "blocked"},
                ident + ": invalid implementation status")
        references(item, "route_ids", routes, ident)
        references(item, "service_mapping_ids", mappings, ident)
        references(item, "blocker_ids", blockers, ident)
        require(item["route_ids"] or item["service_mapping_ids"], ident + ": orchestration needs an affected route or service")
        for key in ("control_flow", "required_tests"):
            require(strings(item.get(key)) and item[key], ident + ": missing " + key)
        refs(item)
        if item["acceptance"] == "accepted":
            refs(item, "acceptance_evidence")
        if item["implementation_status"] in {"implemented", "verified"}:
            require(item["origin"] == "existing" or item["acceptance"] == "accepted",
                    ident + ": implementation of proposed redesign needs accepted design")
            require(strings(item.get("implementation_paths")) and item["implementation_paths"], ident + ": missing implementation paths")
            for path in item["implementation_paths"]:
                local(root, path)
        if item["implementation_status"] == "verified":
            refs(item, "validation_evidence")
    for ident, outcome in outcomes.items():
        if outcome["status"] in {"NO", "VERIFY"}:
            require(any(ident in b["route_ids"] and b["status"] != "resolved" for b in blockers.values()),
                    ident + ": blocked/unresolved route missing from central gap register")
        if outcome["status"] == "ORCHESTRATED":
            require(any(ident in o["route_ids"] and o["acceptance"] == "accepted"
                        and o["implementation_status"] != "blocked" for o in orchestrations.values()),
                    ident + ": ORCHESTRATED evaluation needs an accepted orchestration design")
    for item in index(data.get("source_artifacts", []), "source_artifacts").values():
        fields(item, ("origin", "revision", "inspected_scope", "omissions"), item["id"])
        refs(item)
        if item.get("sha256") is not None:
            require(re.fullmatch(r"[a-f0-9]{64}", item["sha256"]), "Invalid source artifact hash")
    if mode == "code_assessment":
        code_routes = {r["id"]: r for r in assessment["routes"]}
        require(set(code_routes) == set(routes), "Shared routes must cover every code-assessment route")
        compatibility = load(local(root, "compatibility/index.json")) if any(r["ai"] for r in routes.values()) else []
        entries = {x["ai_role_id"]: x for x in compatibility}
        gap_refs = set()
        orchestration_refs = set()
        for ident, route in code_routes.items():
            require(routes[ident]["ai"] == (route["kind"] == "ai_call"), "Shared AI classification differs")
            if not routes[ident]["ai"]:
                continue
            entry = routes[ident].get("evaluation")
            expected_entry = entries.get(ident, {})
            if entry:
                require(all(entry.get(k) == expected_entry.get(k) for k in ("registry", "requirements", "evaluation")),
                        "Shared compatibility artifacts differ from code assessment")
                require(entry.get("selected_candidate_id") == route["route_selection"].get("selected_candidate_id"),
                        "Shared selected candidate differs from code assessment")
            else:
                require(assessment["evidence_policy"] == "repository_only"
                        and routes[ident].get("not_run_reason") == expected_entry.get("not_run_reason"),
                        "Unevaluated code AI route needs the recorded repository-only exception")
            for gap in route["gaps"]:
                ref = ident + ":" + gap["id"]
                gap_refs.add(ref)
                if gap["kind"] == "orchestration":
                    orchestration_refs.add(ref)
        for collection, expected in [(blockers, gap_refs), (orchestrations, orchestration_refs)]:
            actual = set()
            for item in collection.values():
                links = item.get("assessment_gap_refs", [])
                require(strings(links) and set(links) <= gap_refs, "Unknown code gap reference")
                actual.update(links)
            require(expected <= actual, "Code gaps missing from shared gap/orchestration register")
        if package:
            canonical = {m["id"]: m for m in load(local(root, "service-mapping.json"))["entries"]}
            require(set(canonical) == set(mappings), "Shared/deployment service mapping IDs differ")
            for ident, item in canonical.items():
                require(all(mappings[ident].get(k) == item[k] for k in
                            ("source_service", "target_service", "pattern", "decision", "rationale", "required_changes")),
                        "Shared/deployment service mappings differ")
    return outcomes


def cell(value):
    if isinstance(value, list):
        value = "; ".join(str(x) for x in value)
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\n", "<br>")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
                     + ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows])


def blocks(data, outcomes):
    reasons = data.get("empty_reasons", {})
    scope = f"Mode: {data['mode']}. Scope: {cell(data['scope'])}.\n\nLimitations: {cell(data['limitations'])}\n\n"
    scope += table(("Workload", "Scope status", "Description", "Evidence"),
                   [(w["id"] + " / " + w["name"], w["scope_status"], w["description"], w["evidence"]) for w in data["workloads"]]) if data["workloads"] else cell(reasons["workloads"])
    scope += "\n\n" + table(("Evidence ID", "Basis", "Description", "Saved artifact"),
                           [(e["id"], e["kind"], e["description"], e["path"]) for e in data["evidence"]])
    if data.get("source_artifacts"):
        scope += "\n\n" + table(("Source artifact", "Origin / revision", "Hash", "Inspected scope / omissions"),
                               [(a["id"], a["origin"] + " / " + a["revision"], a.get("sha256") or "Not established",
                                 a["inspected_scope"] + " / " + a["omissions"]) for a in data["source_artifacts"]])
    route_rows = []
    for r in data["routes"]:
        outcome = outcomes[r["id"]]
        c = outcome["candidate"]
        target = "No selected candidate"
        if c:
            x = c["route"]
            target = " / ".join(x[k] for k in ("model_name", "model_id", "endpoint", "api", "region", "processing_geography"))
            target += " / " + x["base_url"] + " / path " + x["inference_path"]
        if not r["ai"]:
            target = "Non-AI route; no Bedrock model"
        route_rows.append((r["id"] + " / " + r["workload_id"], r["source_interface"], target, outcome["status"],
                           r["rationale"], outcome["summary"], r["evidence"]))
    bodies = {
        "scope": scope,
        "routes": table(("Route / workload", "Source interface", "Selected target configuration", "Compatibility", "Rationale", "Candidate counts", "Evidence"), route_rows),
        "blockers": "### Central gap and blocker register\n\n" + table(
            ("ID / finding", "Affected routes / services", "Kind / priority / status", "Impact / blocked stages", "Owner / resolution", "Acceptance tests", "Evidence"),
            [(b["id"] + " / " + b["finding"], b["route_ids"] + b["service_mapping_ids"],
              b["kind"] + " / " + b["priority"] + " / " + b["status"], b["impact"] + " / " + ", ".join(b["blocks"]),
              b["owner"] + " / " + b["resolution"], b["required_tests"], b["evidence"]) for b in data["blockers"]]),
        "orchestrations": "### Existing and proposed orchestration\n\n" + table(
            ("ID / name", "Routes / services / gaps", "Control flow", "State / permissions", "Failures / behavior changes", "Origin / acceptance / implementation", "Required tests"),
            [(o["id"] + " / " + o["name"], o["route_ids"] + o["service_mapping_ids"] + o["blocker_ids"], o["control_flow"],
              o["state"] + " / " + o["permissions"], o["failure_handling"] + " / " + o["behavior_difference"],
              o["origin"] + " / " + o["acceptance"] + " / " + o["implementation_status"], o["required_tests"]) for o in data["orchestrations"]]),
        "service_mappings": table(
            ("ID / workloads / routes", "Azure source / evidence state", "AWS target", "Pattern / decision", "Rationale", "Changes / dependencies", "Evidence"),
            [(m["id"] + " / " + ", ".join(m["workload_ids"] + m["route_ids"]), m["source_service"] + " / " + m["source_evidence_state"],
              m["target_service"], m["pattern"] + " / " + m["decision"], m["rationale"], m["required_changes"] + m["dependencies"], m["evidence"]) for m in data["service_mappings"]]),
    }
    for name in ("routes", "blockers", "orchestrations", "service_mappings"):
        if not data[name]:
            bodies[name] = "No entries: " + cell(reasons[name])
    return bodies


def sections(report):
    starts = []
    for title in HEADINGS:
        matches = list(re.finditer(r"^## " + re.escape(title) + r"\s*$", report, re.M))
        require(len(matches) == 1, "Missing/duplicate report section: " + title)
        starts.append(matches[0].start())
    require(starts == sorted(starts), "Shared report sections are out of order")
    return [(start, starts[i + 1] if i + 1 < len(starts) else len(report)) for i, start in enumerate(starts)]


def render_report(report, data, outcomes):
    for name, body in blocks(data, outcomes).items():
        start, end = sections(report)[SECTIONS[name]]
        begin, finish = f"<!-- report:{name}:begin -->", f"<!-- report:{name}:end -->"
        replacement = begin + "\n" + body + "\n" + finish
        matches = list(re.finditer(re.escape(begin) + r".*?" + re.escape(finish), report, re.S))
        if matches:
            m = matches[0]
            require(len(matches) == 1 and start <= m.start() < m.end() <= end, "Misplaced/duplicate shared table")
            report = report[:m.start()] + replacement + report[m.end():]
        else:
            require(begin not in report and finish not in report, "Broken shared table markers")
            report = report[:end].rstrip() + "\n\n" + replacement + "\n\n" + report[end:]
    return report


def audit(root, render=False, historical=False):
    root = Path(root)
    data = load(local(root, "report-contract.json"))
    outcomes = validate(root, data, historical=historical)
    path = local(root, "assessment.md")
    report = path.read_text(encoding="utf-8")
    expected = render_report(report, data, outcomes)
    for start, end in sections(expected):
        content = re.sub(r"<!-- (?:report|assessment):.*?:begin -->.*?<!-- (?:report|assessment):.*?:end -->",
                         "", expected[start:end], flags=re.S).split("\n", 1)[-1].strip()
        require(content and not re.fullmatch(r"\[[^\]]+\]\([^)]+\)[.]?", content),
                "Report sections need findings or a substantive not-applicable explanation")
    if render:
        path.write_text(expected, encoding="utf-8")
    require(render or report == expected, "Shared report tables missing/stale; render from report-contract.json")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--historical", action="store_true", help="Replay saved dates; does not establish current support")
    args = parser.parse_args()
    audit(args.directory, args.render, args.historical)
    print("PASS: shared report sections, cross-references, gap coverage and saved evaluations.")
    print("Does not establish source completeness, genuine approvals, account access or runtime behavior.")
