# Unified deployment architecture

Deliver exactly one unified architecture as these three synchronized files:

- `architecture/architecture.json`: resource-level semantic graph and resolved layout.
- `architecture/migration-deployment-architecture.drawio`: uncompressed, editable Draw.io XML.
- `architecture/migration-deployment-architecture.svg`: self-contained report/viewing image.

Use the contract identifier `unified-cross-cloud-deployment-v1`. Do not claim compatibility with the experimental runtime's receipt or `AssessmentResultV3` contracts. This plugin has no custom runtime.

## Semantic source

Keep stable IDs based on resource identity or planned component identity, not labels or incidental ordering. In JSON record:

- Source commit, inventory timestamp/scope, known limitations, and canvas dimensions.
- Nodes with ID, cloud, service type, label, parent deployment boundary, status (`observed`, `inferred`, `planned`, `conditional`, `blocked`, `unknown`), evidence references, icon key, and absolute x/y/width/height.
- Boundaries with the same stable IDs and layout fields, explicit boundary type, and parent ID.
- Edges with ID, source/target IDs, relationship type, label, and resolved route points.
- Groups with their full member IDs, grouping rationale, and visible representation.
- AI routes with the requested policy, verified model identifier or unresolved status, endpoint, Region, and evidence.

Derive both renderings from these resolved coordinates and IDs. For Draw.io, convert absolute coordinates to parent-relative geometry when nesting. Preserve identical labels, topology, status, and routes. Do not independently improvise the two drawings.

### Bundled renderer

The helper is at `../../../scripts/render_architecture.py` relative to this reference. From the plugin root:

```bash
python3 -B scripts/render_architecture.py /absolute/path/graph.json --output /absolute/path/package/architecture
```

The output directory must not already exist. Keep the input graph outside that directory until rendering finishes. To revise a drawing, render into a new versioned directory, inspect it, then replace only the known generated artifacts as authorized. The helper never downloads assets or calls a cloud API.

Exact input shape:

```json
{
  "contract": "unified-cross-cloud-deployment-v1",
  "title": "Migration deployment architecture",
  "source_commit": "resolved repository commit",
  "canvas": {"width": 2400, "height": 1600},
  "nodes": [],
  "edges": [],
  "groups": [],
  "ai_routes": []
}
```

Populate `nodes` with both boundaries and services. Each has `id`, `label`, `kind` (`boundary` or `service`), `cloud` (`azure`, `aws`, `migration`, `external`), `status`, `parent` (ID or null), `box` (`[x,y,width,height]`), `icon_key` (bundled key or null), and `evidence` (list). Add `boundary_type` such as `vpc`, `vnet`, `subnet`, `account`, or `region`; use `service_type` matching a bundled icon key where applicable, even for neutral artwork. An optional non-empty `display_label` controls only the rendered label, allowing the semantic `label` to retain audit wording. Set `visible: false` only for a semantic finding that must remain addressable by the implementation ledger but does not represent deployment topology. Hidden nodes cannot own visible children, terminate diagram edges, or satisfy a visible group. Other metadata is preserved in JSON.

Edges have `id`, `source`, `target`, `type` (`traffic`, `data`, `identity`, `control`, `mapping`), `label`, `points` (orthogonal route coordinates), and `label_at` (top-left label coordinates). First/last points attach to source/target perimeters. Labels can be empty when the legend is sufficient. AI routes include `endpoint` with the exact supported service name and additional verification metadata.

Reserve 64px at the top/bottom of the canvas. Boxes need at least 160px width and 80px height; wrapped labels may need more. Children need 12px side/bottom padding and 36px header clearance. The helper checks overlapping boxes, parent cycles, detached/clipped/non-orthogonal routes, connectors crossing unrelated services, and common regional-service placement errors. It does not automatically route edges, infer cloud semantics, or prove that labels and edge intersections are visually clean: inspect the rendering.

For repeated workload groups, create a visible service node and retain complete member records in `groups`, identifying the visible node. The agent is responsible for preserving protected nodes and grouping meaning; the helper renders the resolved visible graph and does not perform estate aggregation.

Each group has `id`, `visible_node`, `member_ids`, `members` (objects with at least `id` and `status`), and `rationale`. For members with roles `ingress`, `security`, `identity`, `data`, or `ai`, or statuses `blocked`/`unknown`, keep a separate visible node and reference it through the member's `visible_node` (defaults to member ID). The helper rejects hidden protected members. Group membership records alone are not a visible blocker.

For the customer-facing deployment view, set `"presentation": {"compact_boundary_status": true, "show_evidence_status": false, "reference_style": true, "migration_lanes": true}`. This removes evidence-state words and state-driven red/dashed styling from SVG and Draw.io while retaining every node's status in JSON, SVG `data-status`, and Draw.io metadata. Reference style follows the AWS Architecture Center pattern: official service artwork is the primary visual, service names sit beneath it, and unnecessary card chrome is removed. Availability Zone boundaries remain dashed as a standard containment convention. Migration services directly inside a `migration-capabilities` boundary render as labeled connector lanes instead of empty service cards.

Reference style is an architecture-board layout, not a process flow. Use thin rectangular cloud boundaries with restrained header bands and a clear containment hierarchy. For AWS, prefer account → Region → regional managed-services rail plus VPC → Availability Zone → subnet tiers. For Azure, use tenant → subscription → discovered Region/resource group/network boundaries, with evidence-backed logical application or platform groupings when they clarify the deployment. Do not create a VNet, subnet, private endpoint, Region, or resource group merely to make the drawing symmetrical.

Keep regional Azure/AWS managed services in compact horizontal rails outside VNet/VPC containers. Use equal-size service slots, center the official icon, and place one short service name below it. Use a card only for an iconless capability or a service whose official artwork is not in the pinned subset. Render deployment boundaries first, relationships second, and service artwork last so connectors remain visible without obscuring icons.

In reference style, route the first and last point of a relationship to the visible 64px service-icon perimeter, not the wider transparent label tile. The renderer validates these icon anchors and preserves the same absolute attachment in Draw.io. Use centered top/bottom anchors for vertical flows and centered left/right anchors for horizontal flows; keep branch corridors aligned before changing direction.

An edge may set `"visible": false` when the relationship must remain in the semantic and implementation ledger but would duplicate or obscure a clearer customer-facing path. Hidden edges are never rendered. Use this only for secondary mapping, control, or repeated member relationships; runtime ingress, primary data movement, identity boundaries, and material cross-cloud dependencies remain visible.

Placement checks recognize common short service names as well as canonical keys (for example `s3` and `aws.data.s3`), and named public/private/data subnet tiers. A descriptive service type cannot override a known icon's placement rules. Known service/icon mismatches and canonical service keys from the wrong cloud are rejected. These checks cover defined service families, not every cloud deployment mode.

If the graph includes `implementation_revision`, set `patch_path` to the package-relative application patch and `patch_sha256` to its actual SHA-256. The package checker verifies that binding. Older records without `patch_path` use `deployment/application/agent-aws-runtime.patch`; stale digests fail verification. Do not carry a previous assessment's patch digest into a refreshed graph.

## Cloud placement

Use a landscape canvas with Azure current state on the left, coexistence/migration capabilities in the center, and AWS target deployment on the right. Consumers and delivery systems connect to the appropriate boundaries rather than forming a row of process steps.

Azure boundaries: tenant, subscription, Region/resource group where relevant, VNet, and subnets. PaaS resources are not automatically inside a VNet; their private endpoints are inside subnets. Represent actual service integration according to evidence. An unknown VNet is not a discovered VNet.

AWS boundaries: organization/account, Region, VPC, availability zones, and subnet tiers where the design actually calls for them. Regional managed services such as S3, DynamoDB, and Bedrock stay outside VPC containers; applicable endpoints are inside. Show workloads in their real deployment boundary. Multi-AZ placement is a target decision, not evidence of an existing deployment.

Represent multi-subnet resources accurately: an ALB may appear at the VPC level with explicit attachments to its AZ subnets; a Redis replication group spans member nodes in their data subnets. Keep local notebook and stdio execution outside cloud containers even when it calls cloud APIs. Do not group cloud-hosted services and local-only processes into one cloud deployment box.

The center shows connectivity, transfer/replication, traffic routing, validation interfaces, rollback paths, and decommission controls as a narrow capability plane. Render abstract capabilities as short labeled horizontal connector lanes aligned to their cross-cloud routes, not empty cards. Draw a concrete migration product as an icon node only when the design actually selects it. Application porting and operational-readiness detail belong in the service mapping and migration plan unless they terminate a material architecture relationship. Do not draw numbered waves, chevrons, stage gates, or a generic linear flowchart.

Treat evidence state as assessment metadata, not deployment-diagram decoration. Keep `observed`, `inferred`, `planned`, `conditional`, `blocked`, and `unknown` in JSON and the report, but omit those words and their state-driven styling from the customer-facing drawing. Use separate line treatments for runtime traffic, data movement, identity, control, and Azure-to-AWS mapping, with a compact relationship legend. Keep mapping lines visually subordinate to deployment traffic. Color alone must not carry meaning.

## Icons

The plugin includes a limited pinned Azure/AWS subset at `../../../assets/cloud-icons/` relative to this reference. Read its `manifest.json` and `NOTICE.md`. Use the exact service key and verify the file's SHA-256 against `sanitized_sha256` before embedding. Copy the notice, manifest, and license into the output package when using the icons.

The lightweight subset covers the common services used by this workflow, including App Service, Foundry Agent Service, Azure OpenAI, Redis, Cosmos DB, Azure AI Search, Storage, Fargate, ALB, NAT Gateway, ElastiCache, DynamoDB, OpenSearch, Bedrock, S3, IAM, Cognito, KMS, Textract, Rekognition, Cloud Map, RDS, VPC endpoints, and the core network/observability icons. It is not a complete service catalog. Never substitute a visually similar icon—for example, do not use EC2 artwork for Fargate or S3 artwork for DynamoDB. For missing icons, use a clearly named neutral shape and record the deviation, or obtain the correct official asset with source/version/license metadata. Missing artwork must not block the assessment or hide a service.

Preserve artwork proportions, colors, and shapes and keep service names nearby. Embed assets as standards-compliant `data:` URIs using SVG 2 `href`; never leave remote icon URLs. Display service artwork at 64px in reference style so it remains legible when a landscape diagram is fitted to a laptop screen; the legacy card renderer uses 48px artwork. AWS assets in this subset are unchanged 64px PNGs; diagram geometry and text remain editable, but these icons are not vector artwork.

When verifying additional artwork or conventions, use the official sources:

- https://learn.microsoft.com/en-us/azure/architecture/icons/
- https://aws.amazon.com/architecture/icons/

## Layout and checks

Above 48 visible service nodes or 80 edges, group repeated resources by cloud, environment, deployment boundary, application component, and service type. Keep ingress, identity/security, data stores, AI endpoints, blockers, and unknowns individually visible. Keep all member details in JSON and the report. Increase canvas size when protected nodes cannot fit; do not hide required details merely to meet a threshold.

Use aligned columns, equal service slots, boundary padding, short official service names, and shared orthogonal routing corridors. Align branch points before changing direction; route multi-AZ traffic through the gap between Availability Zones where possible; and keep long cross-cloud runs in the whitespace between cloud boundaries or between major horizontal bands. Follow progressive disclosure: the unified drawing shows deployment topology and material dependencies; readiness findings, alternative services, detailed requirements, and implementation gaps belong in JSON and the report. Avoid perimeter-hugging detours, crossings through unrelated shapes, overlapping labels, clipped content, and service nodes straddling deployment boundaries. Remove redundant edge labels when line style and endpoints already make the relationship clear. Use `display_label` when the audit label contains evidence wording that does not belong in the drawing.

Validate JSON IDs/references/parent cycles, node containment, visible group membership, and Draw.io/SVG semantic parity. XML must parse. Escape labels as text. SVG must contain no scripts, event handlers, foreignObject, external references, or remote fonts; allow only embedded verified raster/SVG image data and local fragment references. Draw.io must not contain active HTML, scripts, or external image links. Inspect a rendered preview when a viewer is available; otherwise explicitly state that visual review was not performed. Parsing alone is not proof of a clean layout.
