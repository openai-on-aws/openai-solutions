"""Application-owned JSON agents for Bedrock Responses; no hosted tools or cloud startup.

Requires aiohttp at request time. The caller supplies a current Bedrock bearer
token per request. Conversation state is process-local and never server-stored.
"""
import asyncio
import copy
from dataclasses import dataclass, field
import hashlib
import inspect
import json
import os
import re
from uuid import uuid4
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass(frozen=True)
class Route:
    policy: str
    region: str
    endpoint: str
    inference_scope: str

    def __post_init__(self):
        self._selected()

    def _selected(self):
        # Legacy aliases retain their 5.6 meaning; new configurations use exact slugs.
        policy = {"sol": "gpt-5.6-sol", "terra": "gpt-5.6-terra", "luna": "gpt-5.6-luna"}.get(self.policy, self.policy)
        catalog = json.loads(Path(__file__).with_name("approved-routes.json").read_text())
        matches = [r for r in catalog["routes"] if r["policy"] == policy
                   and r["endpoint"] == self.endpoint and r["inference_scope"] == self.inference_scope
                   and self.region in r["entry_regions"]]
        if len(matches) != 1:
            raise ValueError("No documented Responses route for this model/endpoint/Region/scope; assess an exact route first")
        return matches[0]

    @property
    def model(self):
        return self._selected()["model_id"]

    @property
    def base_url(self):
        return self._selected()["base_url_template"].format(region=self.region)


class ResponseError(RuntimeError):
    """Safe diagnostic without response payloads or credentials."""


class BedrockAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["BedrockAgentConfig"] = "BedrockAgentConfig"
    agent_name: str
    policy: str
    region: str
    endpoint: Literal["bedrock-runtime", "bedrock-mantle"]
    inference_scope: Literal["in-region", "us", "in", "global"]
    instructions: str = Field(min_length=1)
    max_output_tokens: int = Field(default=8192, ge=1, le=32768)
    max_history_bytes: int = Field(default=1_048_576, ge=1024, le=16_777_216)
    timeout_seconds: float = Field(default=120, gt=0, le=300)

    @model_validator(mode="after")
    def validate_route(self):
        Route(self.policy, self.region, self.endpoint, self.inference_scope)
        return self


def environment_token():
    """Secret-reference injection option; rotating an ECS secret needs task replacement."""
    return os.environ.get("BEDROCK_API_KEY", "")


class ResponsesTransport:
    def __init__(self, route, token_supplier=environment_token, *, timeout=120, max_bytes=2_097_152):
        if not 0 < timeout <= 300 or not 1024 <= max_bytes <= 16_777_216:
            raise ValueError("Invalid transport limits")
        self.route, self.token_supplier = route, token_supplier
        self.timeout, self.max_bytes = timeout, max_bytes

    async def __call__(self, payload):
        import aiohttp

        token = self.token_supplier()
        if inspect.isawaitable(token):
            token = await token
        if not isinstance(token, str) or not token.strip() or any(c in token for c in "\r\n"):
            raise ResponseError("A current Bedrock API key is required")
        # No proxy inheritance, redirects or retry of a potentially accepted request.
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout), trust_env=False) as client:
            async with client.post(self.route.base_url + "/responses", json=payload,
                                   headers={"Authorization": "Bearer " + token}, allow_redirects=False) as response:
                if response.status != 200:
                    raise ResponseError(f"Bedrock Responses returned HTTP {response.status}")
                chunks, size = [], 0
                async for chunk in response.content.iter_chunked(65536):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ResponseError("Bedrock response exceeds the configured size limit")
                    chunks.append(chunk)
                try:
                    result = json.loads(b"".join(chunks))
                except (ValueError, UnicodeError):
                    raise ResponseError("Bedrock returned invalid JSON") from None
                if not isinstance(result, dict):
                    raise ResponseError("Bedrock returned an invalid response object")
                return result


@dataclass
class BedrockThread:
    # IDs identify local state only. They cannot reopen a Foundry/Bedrock thread.
    id: str = field(default_factory=lambda: "local-" + uuid4().hex, init=False)
    _items: list = field(default_factory=list, init=False, repr=False)
    _binding: str | None = field(default=None, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _uncertain_tool_effects: bool = field(default=False, init=False, repr=False)
    _tool_receipts: list = field(default_factory=list, init=False, repr=False)

    @property
    def tool_receipts(self):
        """Local reconciliation metadata only; never arguments, results or secrets."""
        return tuple(dict(receipt) for receipt in self._tool_receipts)


@dataclass(frozen=True)
class Message:
    content: str


@dataclass(frozen=True)
class AgentResponse:
    content: Message
    thread: BedrockThread


class BedrockJsonAgent:
    """No-tool text agent with local validation and at most one JSON repair call.

    Do not use for an agent requiring search, functions, Code Interpreter,
    attachments or streaming. Its caller must preserve conversation ownership.
    """
    def __init__(self, configuration, response_model, *, transport=None):
        self.configuration = configuration.model_copy(deep=True)
        self.route = Route(configuration.policy, configuration.region, configuration.endpoint, configuration.inference_scope)
        self.response_model = response_model
        self.transport = transport or ResponsesTransport(self.route)
        schema = json.dumps(response_model.model_json_schema(), sort_keys=True)
        self.instructions = configuration.instructions + "\nReturn only JSON matching this schema:\n" + schema
        self._binding = hashlib.sha256((configuration.model_dump_json() + schema).encode()).hexdigest()

    @staticmethod
    def create_thread():
        return BedrockThread()

    def _bounded(self, items):
        if len(json.dumps(items, ensure_ascii=False).encode()) > self.configuration.max_history_bytes:
            raise ResponseError("Conversation history exceeds its configured limit; it was not truncated")

    @staticmethod
    def _text(response):
        if response.get("status") != "completed" or response.get("error"):
            raise ResponseError("Bedrock response did not complete")
        output = response.get("output")
        if not isinstance(output, list) or not output:
            raise ResponseError("Bedrock response has no output")
        text = []
        for item in output:
            if not isinstance(item, dict):
                raise ResponseError("Invalid output item")
            if item.get("type") == "reasoning":
                continue
            if item.get("type") != "message" or item.get("role") != "assistant":
                raise ResponseError("A no-tool JSON agent received an unsupported output item")
            content = item.get("content")
            if not isinstance(content, list):
                raise ResponseError("Invalid message content")
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "output_text" or not isinstance(part.get("text"), str):
                    raise ResponseError("Refused or unsupported response content")
                text.append(part["text"])
        if not text:
            raise ResponseError("Bedrock response contains no text")
        return "".join(text)

    async def invoke_with_runtime_config(self, messages, thread, runtime_config=None, kernel=None, arguments=None):
        if not isinstance(messages, str) or not messages.strip() or not isinstance(thread, BedrockThread):
            raise ValueError("Text input and an application-owned BedrockThread are required")
        if arguments is not None:
            raise ValueError("Kernel tools/arguments are not supported by this JSON agent")
        if runtime_config is not None and runtime_config.model_dump() != self.configuration.model_dump():
            raise ValueError("Create a new agent/thread for changed runtime configuration")
        async with thread._lock:
            if thread._binding not in {None, self._binding}:
                raise ValueError("Thread belongs to a different agent configuration")
            items = copy.deepcopy(thread._items) + [{"role": "user", "content": messages}]
            # A total deadline includes authentication, both model calls and repair.
            async with asyncio.timeout(self.configuration.timeout_seconds):
                for attempt in range(2):
                    self._bounded(items)
                    response = await self.transport({"model": self.route.model, "input": copy.deepcopy(items),
                        "instructions": self.instructions, "max_output_tokens": self.configuration.max_output_tokens,
                        "store": False, "stream": False, "background": False,
                        "include": ["reasoning.encrypted_content"]})
                    text = self._text(response)
                    items.extend(copy.deepcopy(response["output"]))
                    self._bounded(items)
                    try:
                        value = self.response_model.model_validate_json(text)
                    except (TypeError, ValueError):
                        if attempt:
                            raise ResponseError("Response failed schema validation after one repair") from None
                        items.append({"role": "user", "content": "The JSON did not match the required schema. Return corrected JSON only; do not add facts."})
                        continue
                    # Commit only successful, validated history. Errors/cancellation
                    # leave local state unchanged; no automatic transport retry.
                    thread._items = items
                    thread._binding = self._binding
                    return AgentResponse(Message(value.model_dump_json()), thread)


@dataclass(frozen=True)
class ToolBinding:
    """A caller-authorized tool, not a function looked up from model-supplied code.

    The async handler receives a validated argument model and call ID. Bind
    authentication, resource scope and any approval checks in that handler.
    Mutating handlers must implement their own durable idempotency if needed.
    """
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: object
    mutating: bool = True

    def __post_init__(self):
        if not isinstance(self.name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.name):
            raise ValueError("Invalid registered tool name")
        if not isinstance(self.description, str) or not 1 <= len(self.description) <= 1024:
            raise ValueError("A bounded tool description is required")
        if not isinstance(self.arguments_model, type) or not issubclass(self.arguments_model, BaseModel):
            raise ValueError("Tool arguments require a Pydantic model")
        if self.arguments_model.model_config.get("extra") != "forbid":
            raise ValueError("Tool arguments must forbid extra fields")
        if not inspect.iscoroutinefunction(self.handler) or type(self.mutating) is not bool:
            raise ValueError("Tools require an async handler and explicit effect classification")


class BedrockToolAgent(BedrockJsonAgent):
    """Client-side function loop with bounded calls and local JSON output validation.

    Tools run sequentially. A failed turn after any mutating tool was admitted
    retires the thread: effects may have happened even when history did not commit.
    This does not roll back external actions or provide cross-process exactly-once.
    """
    def __init__(self, configuration, response_model, tools, *, transport=None,
                 max_tool_calls=8, max_model_calls=6, max_tool_output_bytes=65536):
        super().__init__(configuration, response_model, transport=transport)
        if (type(max_tool_calls) is not int or not 1 <= max_tool_calls <= 32
                or type(max_model_calls) is not int or not 2 <= max_model_calls <= 16
                or type(max_tool_output_bytes) is not int or not 1024 <= max_tool_output_bytes <= 1_048_576):
            raise ValueError("Invalid tool-loop limits")
        if not isinstance(tools, (tuple, list)) or not 1 <= len(tools) <= 32:
            raise ValueError("Register between one and 32 tools explicitly")
        if any(not isinstance(tool, ToolBinding) for tool in tools):
            raise ValueError("Only explicit ToolBinding instances are accepted")
        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("Duplicate tool name")
        self._definitions = [{"type": "function", "name": tool.name, "description": tool.description,
                              "parameters": tool.arguments_model.model_json_schema(), "strict": False}
                             for tool in tools]
        self.max_tool_calls, self.max_model_calls = max_tool_calls, max_model_calls
        self.max_tool_output_bytes = max_tool_output_bytes
        # Callable closures may own different users/resources despite identical
        # schemas. A tool thread belongs to this specific bound agent instance.
        self._binding += ":tools:" + uuid4().hex

    @staticmethod
    def _unique_arguments(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate tool argument")
            result[key] = value
        return result

    def _calls(self, response, seen):
        if not isinstance(response, dict) or response.get("status") != "completed" or response.get("error"):
            raise ResponseError("Bedrock tool response did not complete")
        output = response.get("output")
        if not isinstance(output, list) or not output:
            raise ResponseError("Bedrock tool response has no output")
        calls, text_items, batch_ids = [], [], set()
        for item in output:
            if not isinstance(item, dict):
                raise ResponseError("Invalid tool response item")
            if item.get("type") in {"reasoning", "message"}:
                text_items.append(item)
                continue
            if item.get("type") != "function_call" or item.get("status", "completed") != "completed":
                raise ResponseError("Unsupported or incomplete tool response item")
            name, call_id, arguments = item.get("name"), item.get("call_id"), item.get("arguments")
            if (not isinstance(name, str) or name not in self._tools
                    or not isinstance(call_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call_id)
                    or call_id in seen or call_id in batch_ids):
                raise ResponseError("Unknown tool or invalid/repeated call ID")
            if not isinstance(arguments, str) or len(arguments.encode()) > 32768:
                raise ResponseError("Invalid or oversized tool arguments")
            tool = self._tools[name]
            try:
                json.loads(arguments, object_pairs_hook=self._unique_arguments)
                value = tool.arguments_model.model_validate_json(arguments, strict=True)
            except (TypeError, ValueError, RecursionError):
                raise ResponseError("Tool arguments failed validation") from None
            calls.append((tool, call_id, value))
            batch_ids.add(call_id)
        # A refusal or malformed message in a mixed response cancels the whole
        # batch before any handler starts. Reasoning-only output is not final.
        if any(item.get("type") == "message" for item in text_items) or not calls:
            self._text({"status": "completed", "output": text_items})
        return calls

    async def invoke_with_runtime_config(self, messages, thread, runtime_config=None, kernel=None, arguments=None):
        if not isinstance(messages, str) or not messages.strip() or not isinstance(thread, BedrockThread):
            raise ValueError("Text input and an application-owned BedrockThread are required")
        if arguments is not None or kernel is not None:
            raise ValueError("Register tools explicitly; implicit kernel tool discovery is not supported")
        if runtime_config is not None and runtime_config.model_dump() != self.configuration.model_dump():
            raise ValueError("Create a new agent/thread for changed runtime configuration")
        async with thread._lock:
            if thread._binding not in {None, self._binding}:
                raise ValueError("Thread belongs to different tool bindings")
            if thread._uncertain_tool_effects:
                raise ResponseError("Tool effects require reconciliation; this thread cannot be retried")
            thread._binding = self._binding
            items = copy.deepcopy(thread._items) + [{"role": "user", "content": messages}]
            seen = {item["call_id"] for item in items if item.get("type") == "function_call"}
            used, repair, effect_admitted = 0, False, False
            try:
                async with asyncio.timeout(self.configuration.timeout_seconds):
                    for model_call in range(self.max_model_calls):
                        self._bounded(items)
                        tools_enabled = not repair and used < self.max_tool_calls and model_call < self.max_model_calls - 1
                        response = await self.transport({"model": self.route.model, "input": copy.deepcopy(items),
                            "instructions": self.instructions, "max_output_tokens": self.configuration.max_output_tokens,
                            "store": False, "stream": False, "background": False, "include": ["reasoning.encrypted_content"],
                            "tools": copy.deepcopy(self._definitions), "tool_choice": "auto" if tools_enabled else "none",
                            "parallel_tool_calls": False})
                        calls = self._calls(response, seen)
                        if calls and (not tools_enabled or used + len(calls) > self.max_tool_calls):
                            raise ResponseError("Tool-call budget exceeded or tool call received during finalization")
                        items.extend(copy.deepcopy(response["output"]))
                        self._bounded(items)
                        if calls:
                            for tool, call_id, value in calls:
                                effect_admitted = effect_admitted or tool.mutating
                                receipt = {"name": tool.name, "call_id": call_id, "mutating": tool.mutating, "status": "admitted"}
                                thread._tool_receipts.append(receipt)
                                try:
                                    result = await tool.handler(value, call_id)
                                    receipt["status"] = "completed"
                                    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
                                except asyncio.CancelledError:
                                    receipt["status"] = "uncertain" if tool.mutating else "cancelled"
                                    raise
                                except Exception:
                                    if receipt["status"] != "completed":
                                        receipt["status"] = "uncertain" if tool.mutating else "failed"
                                    raise ResponseError("Registered tool failed; no automatic retry") from None
                                if len(encoded.encode()) > self.max_tool_output_bytes:
                                    raise ResponseError("Tool output exceeds its configured limit")
                                items.append({"type": "function_call_output", "call_id": call_id, "output": encoded})
                                self._bounded(items)
                                seen.add(call_id)
                                used += 1
                            continue
                        try:
                            value = self.response_model.model_validate_json(self._text(response))
                        except (TypeError, ValueError):
                            if repair:
                                raise ResponseError("Response failed schema validation after one repair") from None
                            repair = True
                            items.append({"role": "user", "content": "Return corrected JSON matching the required schema. Do not call tools or add facts."})
                            continue
                        thread._items = items
                        return AgentResponse(Message(value.model_dump_json()), thread)
                    raise ResponseError("Model-call budget exhausted before a valid final response")
            except BaseException:
                if effect_admitted:
                    thread._uncertain_tool_effects = True
                raise
