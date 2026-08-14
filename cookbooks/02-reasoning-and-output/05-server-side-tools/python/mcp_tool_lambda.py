"""MCP tool server, deployed as a Lambda function.

Bedrock calls this function directly: it discovers the tools with `tools/list` and runs
them with `tools/call`, both as JSON-RPC 2.0. No credentials reach this function —
Bedrock reuses the identity of the caller who invoked the model — and nothing here is
reachable from the internet.

The handler is deliberately small. What makes it interesting is where it can sit: attach
it to a VPC and it reaches a private inventory system Bedrock itself has no route to.
"""

import json

# Stands in for the private system this function exists to reach. In a real deployment
# this would be a database in a VPC, and the function would hold the connection.
ROOMS = {
    "MRS-LIS-01": {"property": "Marisol Lisboa", "type": "double", "available": 4,
                   "rate_eur": 185, "accessible": False},
    "MRS-LIS-02": {"property": "Marisol Lisboa", "type": "accessible twin",
                   "available": 1, "rate_eur": 210, "accessible": True},
    "MRS-LIS-03": {"property": "Marisol Lisboa", "type": "suite", "available": 0,
                   "rate_eur": 420, "accessible": False},
    "MRS-POR-01": {"property": "Marisol Porto", "type": "double", "available": 9,
                   "rate_eur": 140, "accessible": False},
    "MRS-POR-02": {"property": "Marisol Porto", "type": "accessible double",
                   "available": 2, "rate_eur": 165, "accessible": True},
}

TOOL_DEFINITIONS = [
    {
        "name": "search_rooms",
        "description": "Find available rooms at a property, optionally only accessible "
                       "rooms. Returns room codes, types, nightly rates in EUR and how "
                       "many are free.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "property_name": {
                    "type": "string",
                    "description": "Property name, e.g. 'Marisol Lisboa'",
                },
                "accessible_only": {
                    "type": "boolean",
                    "description": "Restrict to accessible rooms",
                },
            },
            "required": ["property_name"],
        },
    },
    {
        "name": "get_room",
        "description": "Availability and rate for one room code.",
        "inputSchema": {
            "type": "object",
            "properties": {"room_code": {"type": "string"}},
            "required": ["room_code"],
        },
    },
]


def search_rooms(property_name: str, accessible_only: bool = False) -> dict:
    matches = [
        {"room_code": code, **room}
        for code, room in ROOMS.items()
        if property_name.lower() in room["property"].lower()
        and room["available"] > 0
        and (not accessible_only or room["accessible"])
    ]
    return {"property": property_name, "rooms": matches}


def get_room(room_code: str) -> dict:
    room = ROOMS.get(room_code)
    if room is None:
        return {"error": f"unknown room code {room_code}"}
    return {"room_code": room_code, **room}


TOOL_FUNCTIONS = {"search_rooms": search_rooms, "get_room": get_room}


def result(request_id, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def lambda_handler(event, _context):
    """Handle one JSON-RPC request from Bedrock.

    Three methods matter: `initialize` announces the protocol, `tools/list` is how
    Bedrock discovers what is callable, and `tools/call` runs one. A tool result is
    returned as MCP content parts, which is why the payload is wrapped in `content`
    rather than returned bare.
    """
    if isinstance(event, str):
        event = json.loads(event)
    if "body" in event and isinstance(event["body"], str):
        event = json.loads(event["body"])

    method = event.get("method")
    request_id = event.get("id")

    if method == "initialize":
        return result(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "marisol-inventory", "version": "1.0.0"},
        })

    if method == "tools/list":
        return result(request_id, {"tools": TOOL_DEFINITIONS})

    if method == "tools/call":
        params = event.get("params", {})
        name = params.get("name")
        function = TOOL_FUNCTIONS.get(name)
        if function is None:
            return error(request_id, -32602, f"unknown tool: {name}")
        try:
            payload = function(**params.get("arguments", {}))
        except TypeError as bad_arguments:
            # Arguments are model-generated. Report the problem rather than crashing,
            # so the model can correct itself on the next turn.
            return result(request_id, {
                "content": [
                    {"type": "text", "text": f"invalid arguments: {bad_arguments}"},
                ],
                "isError": True,
            })
        return result(request_id, {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "isError": False,
        })

    if method in ("notifications/initialized", "ping"):
        return result(request_id, {})

    return error(request_id, -32601, f"method not found: {method}")
