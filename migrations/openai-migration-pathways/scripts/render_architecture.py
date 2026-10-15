#!/usr/bin/env python3
"""Render a resolved migration graph to editable Draw.io and self-contained SVG.

Python standard library only. No cloud calls, downloads, or customer-code execution.
"""

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import textwrap
import xml.etree.ElementTree as ET


CONTRACT = "unified-cross-cloud-deployment-v1"
SCRIPT_DIR = Path(__file__).resolve().parent
ASSET_ROOT = SCRIPT_DIR / "assets" if (SCRIPT_DIR / "assets").is_dir() else SCRIPT_DIR.parent / "assets"
ASSETS = ASSET_ROOT / "cloud-icons"
STATES = {"observed", "inferred", "planned", "conditional", "blocked", "unknown"}
COLORS = {
    "azure": "#0078D4",
    "aws": "#B85C00",
    "migration": "#526576",
    "external": "#526576",
}
LINES = {
    "traffic": ("#334155", ""),
    "data": ("#007A78", "8 3"),
    "identity": ("#7654A3", "2 3"),
    "control": ("#667085", "8 3 2 3"),
    "mapping": ("#9CA3AF", "3 6"),
}
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
ICON_SIZE = 48
REFERENCE_ICON_SIZE = 64
ICON_X = 12
ICON_Y = 12
ICON_TEXT_GAP = 10

# Resolve common inventory names without letting a descriptive service_type
# override the placement constraints carried by a known service icon.
SERVICE_ALIASES = {
    "aws": {
        "s3": "aws.data.s3", "dynamodb": "aws.data.dynamodb",
        "bedrock": "aws.ai.bedrock", "bedrock-runtime": "aws.ai.bedrock",
        "bedrock-mantle": "aws.ai.bedrock", "sqs": "aws.integration.sqs",
        "cognito": "aws.identity.cognito", "kms": "aws.security.kms",
        "textract": "aws.ai.textract", "rekognition": "aws.ai.rekognition",
        "knowledge-base": "aws.ai.bedrock",
        "aws.ai.knowledge_base": "aws.ai.bedrock",
        "cloudwatch": "aws.observability.cloudwatch", "iam": "aws.identity.iam",
        "ec2": "aws.compute.ec2", "vpc": "aws.network.vpc",
        "ecs-fargate": "aws.compute.fargate",
        "application-load-balancer": "aws.network.alb",
        "nat-gateway": "aws.network.nat_gateway",
        "elasticache": "aws.data.elasticache",
        "opensearch-serverless": "aws.search.opensearch",
        "cloud-map": "aws.network.cloud_map",
        "private-link": "aws.network.private_link",
        "s3-gateway-endpoint": "aws.network.s3_gateway_endpoint",
    },
    "azure": {
        "storage-account": "azure.data.storage_account",
        "azure-openai": "azure.ai.azure_openai",
        "cosmosdb": "azure.data.cosmosdb", "azure-ai-search": "azure.ai.search",
        "private-endpoint": "azure.network.private_endpoint",
        "virtual-network": "azure.network.virtual_network",
        "virtual-machine": "azure.compute.virtual_machine",
        "managed-identity": "azure.identity.managed_identity",
        "monitor": "azure.observability.monitor",
        "application-group": "azure.compute.app_service",
        "foundry-agents": "azure.ai.foundry_agent",
        "redis": "azure.data.redis",
        "application-insights": "azure.observability.application_insights",
        "ai-services": "azure.ai.cognitive_services",
    },
}
REGIONAL_SERVICES = {
    "aws.data.s3", "aws.data.dynamodb", "aws.ai.bedrock", "aws.integration.sqs",
    "aws.identity.cognito", "aws.security.kms", "aws.ai.textract",
    "aws.ai.rekognition", "aws.ai.knowledge_base", "aws.observability.cloudwatch",
    "aws.identity.iam", "aws.search.opensearch", "azure.data.storage_account",
    "azure.ai.azure_openai", "azure.data.cosmosdb", "azure.ai.search",
    "azure.compute.app_service", "azure.ai.foundry_agent",
    "azure.data.redis", "azure.ai.cognitive_services",
    "azure.observability.application_insights",
}


def service_names(node):
    aliases = SERVICE_ALIASES.get(node["cloud"], {})
    values = set()
    for field in ("service_type", "icon_key"):
        value = node.get(field)
        if value is None:
            continue
        require(isinstance(value, str) and value.strip(), f"Invalid {field}: {node['id']}")
        value = value.strip().lower().replace("_", "-") if "." not in value else value.strip().lower()
        if value.startswith(("aws.", "azure.")):
            require(value.split(".")[0] == node["cloud"], f"Wrong cloud service: {node['id']}")
        values.add(aliases.get(value, value))
    known = set(aliases.values())
    require(len(values & known) <= 1, f"Service and icon disagree: {node['id']}")
    return values


def boundary_class(node):
    value = node.get("boundary_type")
    if value is None:
        return None
    require(isinstance(value, str) and value.strip(), f"Invalid boundary type: {node['id']}")
    value = value.strip().lower().replace("_", "-")
    return {"virtual-private-cloud": "vpc", "virtual-network": "vnet",
            "public-subnet": "subnet", "private-subnet": "subnet", "data-subnet": "subnet"}.get(value, value)


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
    return json.loads(
        Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )


def numbers(values, count):
    return (
        isinstance(values, list)
        and len(values) == count
        and all(type(v) in (int, float) and math.isfinite(v) for v in values)
    )


def node_label(node):
    return node.get("display_label", node["label"])


def wrap(node, reference_style=False):
    if reference_style and node["kind"] == "service" and node.get("icon_key"):
        width = node["box"][2] - 16
    else:
        width = node["box"][2] - content_offset(node) - 12
    return textwrap.wrap(node_label(node), max(1, int(width / 7.2)))


def content_offset(node):
    return ICON_X + ICON_SIZE + ICON_TEXT_GAP if node.get("icon_key") else 12


def connection_box(node, reference_style=False):
    """Return the visible geometry that a connector should touch."""
    if reference_style and node["kind"] == "service" and node.get("icon_key"):
        x, y, width, _ = node["box"]
        size = REFERENCE_ICON_SIZE
        return [x + (width - size) / 2, y + 8, size, size]
    return node["box"]


def ancestors(node, nodes):
    result = []
    parent = node.get("parent")
    while parent:
        require(parent in nodes, f"Missing parent: {parent}")
        require(parent not in result and parent != node["id"], "Parent cycle")
        result.append(parent)
        parent = nodes[parent].get("parent")
    return result


def on_border(point, box):
    x, y = point
    left, top, width, height = box
    return (
        left <= x <= left + width
        and top <= y <= top + height
        and (x in (left, left + width) or y in (top, top + height))
    )


def crosses(a, b, box):
    x, y, width, height = box
    if a[0] == b[0]:
        return x < a[0] < x + width and max(min(a[1], b[1]), y) < min(
            max(a[1], b[1]), y + height
        )
    return y < a[1] < y + height and max(min(a[0], b[0]), x) < min(
        max(a[0], b[0]), x + width
    )


def validate(graph):
    require(graph.get("contract") == CONTRACT, "Unsupported graph contract")
    presentation = graph.get("presentation", {})
    require(isinstance(presentation, dict) and set(presentation) <= {
                "compact_boundary_status", "show_evidence_status",
                "reference_style", "migration_lanes"},
            "Invalid presentation options")
    require(type(presentation.get("compact_boundary_status", False)) is bool,
            "Invalid compact boundary status")
    require(type(presentation.get("show_evidence_status", True)) is bool,
            "Invalid evidence status visibility")
    require(type(presentation.get("reference_style", False)) is bool,
            "Invalid reference style")
    require(type(presentation.get("migration_lanes", False)) is bool,
            "Invalid migration lanes option")
    width, height = graph["canvas"]["width"], graph["canvas"]["height"]
    require(
        numbers([width, height], 2) and width >= 800 and height >= 300, "Invalid canvas"
    )
    require(
        isinstance(graph.get("title"), str) and 0 < len(graph["title"]) <= 100,
        "Invalid title",
    )
    require(len(graph["title"]) * 12 < width - 48, "Title exceeds canvas")
    nodes = {}
    for node in graph["nodes"]:
        ident = node["id"]
        require(
            isinstance(ident, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", ident),
            "Invalid ID",
        )
        require(ident not in nodes, f"Duplicate node: {ident}")
        require(node["kind"] in ("boundary", "service"), f"Invalid kind: {ident}")
        require(
            node["status"] in STATES and node["cloud"] in COLORS,
            f"Invalid status/cloud: {ident}",
        )
        require(
            isinstance(node["label"], str) and node["label"].strip(),
            f"Missing label: {ident}",
        )
        require(
            node.get("display_label") is None
            or (isinstance(node["display_label"], str) and node["display_label"].strip()),
            f"Invalid display label: {ident}",
        )
        require(type(node.get("visible", True)) is bool, f"Invalid visibility: {ident}")
        require(
            isinstance(node.get("evidence"), list), f"Missing evidence list: {ident}"
        )
        require(
            node["status"] != "observed" or node["evidence"],
            f"Observed node needs evidence: {ident}",
        )
        if node.get("icon_key"):
            require(
                isinstance(node["icon_key"], str) and node["icon_key"].startswith(node["cloud"] + "."),
                f"Wrong cloud icon: {ident}",
            )
        if node["cloud"] == "aws":
            require(
                all(x not in node["label"].lower() for x in ("gpt-oss", "gpt oss", "daybreak", "gpt-5.6-cyber")),
                "GPT-OSS and Daybreak are not approved AWS target",
            )
        require(numbers(node.get("box"), 4), f"Invalid box: {ident}")
        x, y, w, h = node["box"]
        if node.get("visible", True):
            require(
                x >= 12 and y >= 64 and x + w <= width - 12 and y + h <= height - 64,
                f"Clipped node: {ident}",
            )
            require(w >= 160 and h >= 80, f"Node too small: {ident}")
            require(len(wrap(node, presentation.get("reference_style", False))) * 16 + 44 <= h,
                    f"Label needs taller box: {ident}")
        if node["kind"] == "boundary" and node.get("visible", True):
            require(
                len(node_label(node)) * 7.2 < w - 24, f"Boundary title too long: {ident}"
            )
            require(
                not node.get("icon_key"),
                "Place service icons on service nodes, not boundary labels",
            )
        nodes[ident] = node
    require(nodes, "Empty architecture")
    for node in nodes.values():
        lineage = ancestors(node, nodes)
        x, y, w, h = node["box"]
        if node.get("visible", True) and lineage:
            parent = nodes[lineage[0]]
            require(parent["kind"] == "boundary", "Only boundaries can contain nodes")
            require(parent.get("visible", True), "Visible node has hidden parent")
            require(
                parent["cloud"] == node["cloud"],
                f"Cross-cloud containment: {node['id']}",
            )
            px, py, pw, ph = parent["box"]
            require(
                x >= px + 12
                and y >= py + 36
                and x + w <= px + pw - 12
                and y + h <= py + ph - 12,
                f"Outside parent padding: {node['id']}",
            )
        if not node.get("visible", True):
            continue
        network = {boundary_class(nodes[p]) for p in lineage}
        services = service_names(node)
        if services & REGIONAL_SERVICES:
            require(
                not network.intersection({"vpc", "vnet", "subnet"}),
                f"Regional/PaaS service inside network: {node['id']}",
            )
        if services & {"aws.network.private_link", "azure.network.private_endpoint"}:
            require(
                "subnet" in network, f"Private endpoint outside subnet: {node['id']}"
            )
        if "aws.network.s3_gateway_endpoint" in services:
            require("vpc" in network and "subnet" not in network,
                    f"S3 gateway endpoint belongs at VPC route-table level: {node['id']}")
    ordered = sorted(
        (n for n in nodes.values() if n.get("visible", True)),
        key=lambda n: (len(ancestors(n, nodes)), n["id"]),
    )
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if a["id"] in ancestors(b, nodes) or b["id"] in ancestors(a, nodes):
                continue
            ax, ay, aw, ah = a["box"]
            bx, by, bw, bh = b["box"]
            require(
                not (
                    max(ax, bx) < min(ax + aw, bx + bw)
                    and max(ay, by) < min(ay + ah, by + bh)
                ),
                f"Overlapping nodes: {a['id']} / {b['id']}",
            )
    seen = set()
    for edge in graph["edges"]:
        ident = edge["id"]
        require(
            isinstance(ident, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", ident),
            "Invalid edge ID",
        )
        require(ident not in seen, f"Duplicate edge: {ident}")
        seen.add(ident)
        require(type(edge.get("visible", True)) is bool,
                f"Invalid edge visibility: {ident}")
        require(
            edge["source"] in nodes and edge["target"] in nodes,
            f"Unknown edge endpoint: {ident}",
        )
        require(edge["type"] in LINES, f"Invalid edge type: {ident}")
        require(
            isinstance(edge["label"], str) and len(edge["label"]) <= 60,
            f"Invalid edge label: {ident}",
        )
        if not edge.get("visible", True):
            continue
        require(
            nodes[edge["source"]].get("visible", True)
            and nodes[edge["target"]].get("visible", True),
            f"Edge endpoint is hidden: {ident}",
        )
        points = edge["points"]
        require(
            len(points) >= 2 and all(numbers(p, 2) for p in points),
            f"Missing edge route: {ident}",
        )
        require(
            all(12 <= p[0] <= width - 12 and 64 <= p[1] <= height - 64 for p in points),
            f"Clipped edge: {ident}",
        )
        require(
            on_border(points[0], connection_box(nodes[edge["source"]],
                                                presentation.get("reference_style", False)))
            and on_border(points[-1], connection_box(nodes[edge["target"]],
                                                     presentation.get("reference_style", False))),
            f"Detached edge: {ident}",
        )
        for a, b in zip(points, points[1:]):
            require(
                a != b and (a[0] == b[0] or a[1] == b[1]),
                f"Route must be orthogonal: {ident}",
            )
            for node in ordered:
                if node["kind"] != "boundary" and node["id"] not in (
                    edge["source"],
                    edge["target"],
                ):
                    require(
                        not crosses(a, b, node["box"]),
                        f"Edge crosses node: {ident} / {node['id']}",
                    )
        require(numbers(edge["label_at"], 2), f"Missing edge label position: {ident}")
        lx, ly = edge["label_at"]
        require(
            lx >= 12
            and ly >= 64
            and lx + len(edge["label"]) * 7.2 <= width - 12
            and ly + 16 <= height - 64,
            f"Clipped edge label: {ident}",
        )
    group_ids = set()
    for group in graph.get("groups", []):
        require(group["id"] not in group_ids, "Duplicate group ID")
        group_ids.add(group["id"])
        require(group["visible_node"] in nodes, "Group has no visible representation")
        require(nodes[group["visible_node"]].get("visible", True),
                "Group representation is hidden")
        members = group["members"]
        require(
            len({m["id"] for m in members}) == len(members), "Duplicate group member"
        )
        require(
            set(group["member_ids"]) == {m["id"] for m in members},
            "Group member ledger differs",
        )
        for member in members:
            protected = member["status"] in {"blocked", "unknown"} or member.get(
                "role"
            ) in {"ingress", "security", "identity", "data", "ai"}
            if protected:
                ident = member.get("visible_node", member["id"])
                require(
                    ident in nodes and ident != group["visible_node"],
                    f"Protected group member is hidden: {member['id']}",
                )
                require(
                    nodes[ident]["status"] == member["status"],
                    "Protected member status differs",
                )
    for route in graph.get("ai_routes", []):
        require(
            route["endpoint"] in ("bedrock-runtime", "bedrock-mantle"),
            "Unsupported AI endpoint",
        )
        require(
            all(x not in json.dumps(route).lower() for x in ("gpt-oss", "gpt oss", "daybreak", "gpt-5.6-cyber")),
            "GPT-OSS and Daybreak are not approved target route",
        )
        # An unresolved route may omit its URL. A supplied Responses URL must
        # match the declared endpoint and Region, not just look like AWS.
        if "base_url" in route and route.get("api", "responses") == "responses":
            region = route.get("region")
            require(isinstance(region, str) and re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region),
                    "Responses base URL requires a Region")
            expected = (
                f"https://bedrock-runtime.{region}.amazonaws.com/openai/v1"
                if route["endpoint"] == "bedrock-runtime"
                else f"https://bedrock-mantle.{region}.api.aws/openai/v1"
            )
            require(route["base_url"] == expected,
                    "Responses base URL does not match endpoint, Region and API path")
    return ordered


def icon_data(key):
    entries = {item["key"]: item for item in load(ASSETS / "manifest.json")}
    require(key in entries, f"Unknown icon: {key}")
    item = entries[key]
    path = ASSETS / item["file"]
    require(
        path.parent == ASSETS and not path.is_symlink(), "Invalid bundled icon path"
    )
    data = path.read_bytes()
    require(
        hashlib.sha256(data).hexdigest() == item["sanitized_sha256"],
        f"Icon checksum mismatch: {key}",
    )
    require(
        item["media_type"] in ("image/png", "image/svg+xml"), "Unsupported icon format"
    )
    if item["media_type"] == "image/svg+xml":
        require(
            b"<!DOCTYPE" not in data and b"<!ENTITY" not in data,
            "Active XML is not allowed",
        )
        for element in ET.fromstring(data).iter():
            require(
                element.tag.split("}")[-1]
                not in {
                    "script",
                    "foreignObject",
                    "style",
                    "a",
                    "image",
                    "animate",
                    "set",
                },
                "Active icon element",
            )
            for name, value in element.attrib.items():
                local = name.split("}")[-1].lower()
                require(not local.startswith("on"), "Icon event handler")
                require(
                    local != "href" or value.startswith("#"), "External icon reference"
                )
                for target in re.findall(r"url\((.*?)\)", value):
                    require(target.strip("'\" ").startswith("#"), "External icon URL")
    return item["media_type"], base64.b64encode(data).decode("ascii")


def sub(container, tag, **attrs):
    return ET.SubElement(
        container, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()}
    )


def svg_text(parent, x, y, value, size=12, color="#243447", *, anchor=None,
             weight=None):
    attrs = dict(
        x=x,
        y=y,
        font_family="Arial, sans-serif",
        font_size=size,
        fill=color,
    )
    if anchor:
        attrs["text_anchor"] = anchor
    if weight:
        attrs["font_weight"] = weight
    element = sub(
        parent,
        f"{{{SVG}}}text",
        **attrs,
    )
    element.text = value


def reference_boundary_style(node):
    """Return restrained cloud-diagram styling for a deployment boundary."""
    kind = boundary_class(node)
    cloud = node["cloud"]
    header = {
        "azure": "#E6F2FB",
        "aws": "#FFF1DD",
        "migration": "#E9EEF3",
        "external": "#EEF2F6",
    }[cloud]
    stroke = COLORS[cloud]
    fill = "#FFFFFF"
    dash = ""
    stroke_width = 1.5
    if kind in {"tenant", "account"}:
        stroke = "#8A9AAA"
        header = "#F4F6F8"
        stroke_width = 2
    elif kind in {"subscription", "region"}:
        fill = "#FCFDFE"
    elif kind == "vpc":
        stroke = "#2E8B57"
        header = "#EAF6EC"
        fill = "#FBFEFB"
        stroke_width = 2
    elif kind == "vnet":
        fill = "#F7FBFF"
    elif kind == "availability-zone":
        stroke = "#7C8B99"
        header = "#F7F8FA"
        dash = "7 4"
    elif kind == "subnet":
        label = node_label(node).lower()
        if "public" in label:
            header, fill, stroke = "#FFF1DD", "#FFFBF5", "#D97706"
        elif "data" in label:
            header, fill, stroke = "#F1EAFE", "#FCFAFF", "#7654A3"
        else:
            header, fill, stroke = "#EAF4FB", "#F8FCFF", "#147EBA"
    elif kind in {"migration-capabilities", "service-group", "logical-group"}:
        fill = "#FBFCFD"
    return fill, stroke, header, dash, stroke_width


def xml_bytes(root):
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def render(graph):
    ordered = validate(graph)
    by_id = {n["id"]: n for n in ordered}
    compact_status = graph.get("presentation", {}).get("compact_boundary_status", False)
    show_evidence_status = graph.get("presentation", {}).get("show_evidence_status", True)
    reference_style = graph.get("presentation", {}).get("reference_style", False)
    migration_lanes = graph.get("presentation", {}).get("migration_lanes", False)
    width, height = graph["canvas"]["width"], graph["canvas"]["height"]
    svg = ET.Element(
        f"{{{SVG}}}svg",
        {
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
            "role": "img",
        },
    )
    sub(svg, f"{{{SVG}}}title").text = graph["title"]
    sub(svg, f"{{{SVG}}}rect", width=width, height=height, fill="#FFFFFF")
    svg_text(svg, 24, 36, graph["title"], 22, "#172B3A", weight="bold")
    boundary_layer = sub(svg, f"{{{SVG}}}g", id="boundaries")
    edge_layer = sub(svg, f"{{{SVG}}}g", id="relationships")
    service_layer = sub(svg, f"{{{SVG}}}g", id="services")
    mx = ET.Element("mxfile", {"host": "app.diagrams.net", "compressed": "false"})
    diagram = sub(
        mx, "diagram", id="migration-deployment", name="Migration and deployment"
    )
    model = sub(
        diagram, "mxGraphModel", page="1", pageWidth=width, pageHeight=height, grid="0"
    )
    cells = sub(model, "root")
    sub(cells, "mxCell", id="0")
    sub(cells, "mxCell", id="1", parent="0")

    def mx_text(ident, parent, x, y, w, h, value, size=12, *, align="left",
                bold=False, color="#243447"):
        cell = sub(
            cells,
            "mxCell",
            id=ident,
            value=value,
            vertex="1",
            parent=parent,
            style=f"text;html=0;whiteSpace=wrap;align={align};verticalAlign=top;spacing=0;fontFamily=Arial;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};overflow=hidden;",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            {
                "x": str(x),
                "y": str(y),
                "width": str(w),
                "height": str(h),
                "as": "geometry",
            },
        )

    mx_text("title", "1", 24, 12, width - 48, 30, graph["title"], 22,
            bold=True, color="#172B3A")
    for node in ordered:
        x, y, w, h = node["box"]
        boundary = node["kind"] == "boundary"
        parent = node.get("parent")
        parent_node = by_id.get(parent)
        lane = bool(
            migration_lanes and reference_style and not boundary
            and node["cloud"] == "migration" and parent_node
            and boundary_class(parent_node) == "migration-capabilities"
        )
        if show_evidence_status:
            color = "#B42318" if node["status"] == "blocked" else COLORS[node["cloud"]]
            dash = "" if node["status"] == "observed" else "6 4"
        else:
            color = COLORS[node["cloud"]] if boundary else "#94A3B8"
            dash = "5 3" if boundary_class(node) == "availability-zone" else ""
        fill = (
            {
                "azure": "#F3F9FE",
                "aws": "#FFF8EF",
                "migration": "#F8FAFC",
                "external": "#F8FAFC",
            }[node["cloud"]]
            if boundary
            else "#FFFFFF"
        )
        header_fill = None
        stroke_width = 1.5
        if reference_style and boundary:
            fill, color, header_fill, dash, stroke_width = reference_boundary_style(node)
        group = sub(
            boundary_layer if boundary else service_layer,
            f"{{{SVG}}}g", id="n-" + node["id"], data_status=node["status"]
        )
        attrs = dict(
            x=x, y=y, width=w, height=h, rx=2 if reference_style else 4,
            fill=fill, stroke=color, stroke_width=stroke_width
        )
        if dash:
            attrs["stroke_dasharray"] = dash
        icon_tile = reference_style and not boundary and bool(node.get("icon_key"))
        if lane:
            sub(group, f"{{{SVG}}}line", x1=x + 8, y1=y + h / 2,
                x2=x + w - 8, y2=y + h / 2, stroke=color,
                stroke_width=1.5)
            sub(group, f"{{{SVG}}}circle", cx=x + 8, cy=y + h / 2,
                r=3, fill=color)
            sub(group, f"{{{SVG}}}circle", cx=x + w - 8, cy=y + h / 2,
                r=3, fill=color)
        elif not icon_tile:
            sub(group, f"{{{SVG}}}rect", **attrs)
        if reference_style and boundary:
            sub(group, f"{{{SVG}}}rect", x=x + stroke_width / 2,
                y=y + stroke_width / 2, width=w - stroke_width,
                height=32, fill=header_fill, stroke="none")
        px, py = by_id[parent]["box"][:2] if parent else (0, 0)
        cell = sub(
            cells,
            "mxCell",
            id="n-" + node["id"],
            value="",
            vertex="1",
            parent="n-" + parent if parent else "1",
            style=(
                "rounded=0;html=0;fillColor=none;strokeColor=none;"
                if icon_tile or lane else
                f"rounded={0 if reference_style else 1};arcSize=4;html=0;fillColor={fill};strokeColor={color};strokeWidth={stroke_width};dashed={int(bool(dash))};dashPattern={dash or '6 4'};container={int(boundary)};"
            ),
        )
        if compact_status or not show_evidence_status:
            cell.set("data-status", node["status"])
        ET.SubElement(
            cell,
            "mxGeometry",
            {
                "x": str(x - px),
                "y": str(y - py),
                "width": str(w),
                "height": str(h),
                "as": "geometry",
            },
        )
        if reference_style and boundary:
            header_cell = sub(
                cells, "mxCell", id="header-" + node["id"], value="", vertex="1",
                parent="n-" + node["id"],
                style=f"rounded=0;html=0;fillColor={header_fill};strokeColor=none;",
            )
            ET.SubElement(header_cell, "mxGeometry", {
                "x": "0", "y": "0", "width": str(w), "height": "32",
                "as": "geometry",
            })
        if lane:
            line_cell = sub(
                cells, "mxCell", id="lane-" + node["id"], value="", vertex="1",
                parent="n-" + node["id"],
                style=f"shape=line;html=0;strokeColor={color};strokeWidth=1.5;",
            )
            ET.SubElement(line_cell, "mxGeometry", {
                "x": "8", "y": str(h / 2), "width": str(w - 16), "height": "1",
                "as": "geometry",
            })
        offset = content_offset(node)
        if node.get("icon_key"):
            mime, data = icon_data(node["icon_key"])
            data_url = f"data:{mime};base64,{data}"
            icon_size = REFERENCE_ICON_SIZE if icon_tile else ICON_SIZE
            icon_x = (w - icon_size) / 2 if icon_tile else ICON_X
            icon_y = 8 if icon_tile else ICON_Y
            element = sub(
                group,
                f"{{{SVG}}}image",
                x=x + icon_x,
                y=y + icon_y,
                width=icon_size,
                height=icon_size,
                preserveAspectRatio="xMidYMid meet",
            )
            # SVG 2's unqualified href is supported by current browsers and
            # macOS viewers. The retired xlink form caused embedded artwork to
            # disappear in some report previews.
            element.set("href", data_url)
            image_cell = sub(
                cells,
                "mxCell",
                id="icon-" + node["id"],
                value="",
                vertex="1",
                parent="n-" + node["id"],
                style=f"shape=image;imageAspect=1;aspect=fixed;image={data_url};",
            )
            ET.SubElement(
                image_cell,
                "mxGeometry",
                {
                    "x": str(icon_x),
                    "y": str(icon_y),
                    "width": str(icon_size),
                    "height": str(icon_size),
                    "as": "geometry",
                },
            )
        lines = [node_label(node)] if boundary or lane else wrap(node, reference_style)
        for index, line in enumerate(lines):
            if lane:
                svg_text(group, x + w / 2, y + h / 2 - 10, line, 12,
                         "#243447", anchor="middle", weight="bold")
            elif icon_tile:
                svg_text(group, x + w / 2,
                         y + icon_y + icon_size + 18 + 17 * index, line, 13,
                         "#243447", anchor="middle")
            elif boundary and reference_style:
                svg_text(group, x + 12, y + 22, line, 13, color, weight="bold")
            else:
                svg_text(group, x + offset, y + 22 + 16 * index, line)
        mx_text(
            "label-" + node["id"],
            "n-" + node["id"],
            4 if icon_tile or lane else (12 if boundary and reference_style else offset),
            h / 2 - 28 if lane else (icon_y + icon_size + 6 if icon_tile else 10),
            w - 8 if icon_tile or lane else w - offset - 12,
            len(lines) * 16,
            "\n".join(lines),
            13 if icon_tile or (boundary and reference_style) else 12,
            align="center" if icon_tile or lane else "left",
            bold=(boundary and reference_style) or lane,
            color=color if boundary and reference_style else "#243447",
        )
        redundant_planned = (compact_status and boundary and node["status"] == "planned"
                             and parent and by_id[parent]["status"] == "planned")
        if show_evidence_status and boundary and not redundant_planned:
            status_x = x + w - len(node["status"]) * 6 - 12
            svg_text(group, status_x, y + h - 10, node["status"], 10, color)
            mx_text(
                "status-" + node["id"],
                "n-" + node["id"],
                status_x - x,
                h - 22,
                len(node["status"]) * 6,
                14,
                node["status"],
                10,
            )
        elif show_evidence_status and not boundary:
            svg_text(group, x + offset, y + h - 12, node["status"].upper(), 10, color)
            mx_text(
                "status-" + node["id"],
                "n-" + node["id"],
                offset,
                h - 24,
                w - offset - 12,
                14,
                node["status"].upper(),
                10,
            )
    for edge in sorted((edge for edge in graph["edges"]
                        if edge.get("visible", True)), key=lambda e: e["id"]):
        color, dash = LINES[edge["type"]]
        group = sub(
            edge_layer,
            f"{{{SVG}}}g",
            id="e-" + edge["id"],
            data_source=edge["source"],
            data_target=edge["target"],
            data_type=edge["type"],
        )
        attrs = {
            "points": " ".join(f"{x},{y}" for x, y in edge["points"]),
            "fill": "none",
            "stroke": color,
            "stroke_width": 1.5,
        }
        if dash:
            attrs["stroke_dasharray"] = dash
        sub(group, f"{{{SVG}}}polyline", **attrs)
        a, b = edge["points"][-2:]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        arrow = [
            b,
            [b[0] - 8 * ux + 3 * uy, b[1] - 8 * uy - 3 * ux],
            [b[0] - 8 * ux - 3 * uy, b[1] - 8 * uy + 3 * ux],
        ]
        sub(
            group,
            f"{{{SVG}}}polygon",
            points=" ".join(f"{x},{y}" for x, y in arrow),
            fill=color,
        )
        lx, ly = edge["label_at"]
        if edge["label"]:
            sub(
                group,
                f"{{{SVG}}}rect",
                x=lx - 2,
                y=ly,
                width=len(edge["label"]) * 7.2 + 4,
                height=16,
                fill="#FFFFFF",
            )
            svg_text(group, lx, ly + 12, edge["label"], 11, color)
        source, target = by_id[edge["source"]]["box"], by_id[edge["target"]]["box"]
        start, end = edge["points"][0], edge["points"][-1]
        anchors = f"exitX={(start[0] - source[0]) / source[2]};exitY={(start[1] - source[1]) / source[3]};entryX={(end[0] - target[0]) / target[2]};entryY={(end[1] - target[1]) / target[3]};"
        cell = sub(
            cells,
            "mxCell",
            id="e-" + edge["id"],
            value="",
            edge="1",
            parent="1",
            source="n-" + edge["source"],
            target="n-" + edge["target"],
            style=f"edgeStyle=none;html=0;endArrow=block;endSize=8;strokeColor={color};strokeWidth=1.5;dashed={int(bool(dash))};dashPattern={dash or '1'};exitPerimeter=0;entryPerimeter=0;{anchors}",
        )
        geometry = ET.SubElement(
            cell, "mxGeometry", {"relative": "1", "as": "geometry"}
        )
        points = ET.SubElement(geometry, "Array", {"as": "points"})
        for x, y in edge["points"][1:-1]:
            sub(points, "mxPoint", x=x, y=y)
        mx_text(
            "edge-label-" + edge["id"],
            "1",
            lx,
            ly,
            max(1, len(edge["label"]) * 7.2),
            16,
            edge["label"],
            11,
        )
    if show_evidence_status:
        legend = "Solid: observed | Dashed: inferred / planned / conditional / unknown (see labels)"
        svg_text(svg, 24, height - 38, legend, 11)
        mx_text("legend-status", "1", 24, height - 50, width - 48, 16, legend, 11)
    for index, (name, (color, dash)) in enumerate(LINES.items()):
        x = 24 + index * 150
        attrs = dict(
            x1=x,
            y1=height - 18,
            x2=x + 28,
            y2=height - 18,
            stroke=color,
            stroke_width=2,
        )
        if dash:
            attrs["stroke_dasharray"] = dash
        sub(svg, f"{{{SVG}}}line", **attrs)
        svg_text(svg, x + 34, height - 14, name, 11, color)
        line = sub(
            cells,
            "mxCell",
            id="legend-line-" + name,
            value="",
            edge="1",
            parent="1",
            style=f"endArrow=none;strokeColor={color};strokeWidth=2;dashed={int(bool(dash))};dashPattern={dash or '1'};",
        )
        geometry = ET.SubElement(
            line, "mxGeometry", {"relative": "1", "as": "geometry"}
        )
        ET.SubElement(
            geometry,
            "mxPoint",
            {"x": str(x), "y": str(height - 18), "as": "sourcePoint"},
        )
        ET.SubElement(
            geometry,
            "mxPoint",
            {"x": str(x + 28), "y": str(height - 18), "as": "targetPoint"},
        )
        mx_text("legend-" + name, "1", x + 34, height - 26, 110, 16, name, 11)
    return xml_bytes(svg), xml_bytes(mx)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument(
        "--output", type=Path, required=True, help="New output directory"
    )
    args = parser.parse_args()
    graph = load(args.graph)
    svg, drawio = render(graph)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "architecture.json").write_text(
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.output / "migration-deployment-architecture.svg").write_bytes(svg)
    (args.output / "migration-deployment-architecture.drawio").write_bytes(drawio)
    notices = args.output / "icon-notices"
    notices.mkdir()
    for name in ("manifest.json", "NOTICE.md", "AWS-LICENSE.txt"):
        shutil.copyfile(ASSETS / name, notices / name)
    print(f"Rendered one architecture in JSON, Draw.io and SVG: {args.output}")


if __name__ == "__main__":
    main()
