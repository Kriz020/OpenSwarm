"""Fix: preserve reasoning_content across DeepSeek conversation turns.

Root cause (SDK bug in chatcmpl_converter.py — flush_assistant_message):

  Two bugs in the inner closure:

  Bug 1 (else branch, line 444):
    When flush_assistant_message() is called and current_assistant_msg is None
    (i.e. before any assistant message has been built for this turn), the code
    clears pending_reasoning_content. This happens on every response_output_message
    (section 3) because flush_assistant_message() is called at the top of that
    block *before* building the new assistant dict. Result: reasoning_content is
    discarded before it can be attached to the message.

  Bug 2 (if branch, lines 437-440):
    When flushing a plain-text assistant message (no tool_calls), the code never
    attaches pending_reasoning_content to the message — it just clears it.
    Tool-call messages are handled correctly (lines 588-590), but plain-text ones
    are not.

Fix strategy:
  Completely replace Converter.items_to_messages with a fixed version.
  The only two changes vs the original are marked with # FIX comments inside
  flush_assistant_message().  Everything else is verbatim SDK code so that
  future SDK changes remain easy to diff against this file.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, Union, cast

from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionDeveloperMessageParam,
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from agents.models.chatcmpl_converter import Converter
from agents.exceptions import UserError


def _fixed_items_to_messages(
    cls,
    items: Any,
    model: str | None = None,
    preserve_thinking_blocks: bool = False,
    preserve_tool_output_all_content: bool = False,
) -> list[ChatCompletionMessageParam]:
    if isinstance(items, str):
        return [ChatCompletionUserMessageParam(role="user", content=items)]

    result: list[ChatCompletionMessageParam] = []
    current_assistant_msg: ChatCompletionAssistantMessageParam | None = None
    pending_thinking_blocks: list[dict[str, str]] | None = None
    pending_reasoning_content: str | None = None

    def flush_assistant_message() -> None:
        nonlocal current_assistant_msg, pending_reasoning_content
        if current_assistant_msg is not None:
            if not current_assistant_msg.get("tool_calls"):
                del current_assistant_msg["tool_calls"]
                # FIX: attach pending reasoning_content to plain-text assistant messages
                if pending_reasoning_content and "reasoning_content" not in current_assistant_msg:
                    current_assistant_msg["reasoning_content"] = pending_reasoning_content  # type: ignore[typeddict-unknown-key]
                pending_reasoning_content = None
            result.append(current_assistant_msg)
            current_assistant_msg = None
        # FIX: do NOT clear pending_reasoning_content when there is no current assistant
        # message — it will be consumed by the upcoming response_output_message (section 3).

    def ensure_assistant_message() -> ChatCompletionAssistantMessageParam:
        nonlocal current_assistant_msg, pending_thinking_blocks
        if current_assistant_msg is None:
            current_assistant_msg = ChatCompletionAssistantMessageParam(role="assistant")
            current_assistant_msg["content"] = None
            current_assistant_msg["tool_calls"] = []
        return current_assistant_msg

    for item in items:
        # 1) EasyInputMessage
        if easy_msg := cls.maybe_easy_input_message(item):
            role = easy_msg["role"]
            content = easy_msg["content"]
            if role == "user":
                flush_assistant_message()
                result.append({"role": "user", "content": cls.extract_all_content(content)})
            elif role == "system":
                flush_assistant_message()
                result.append({"role": "system", "content": cls.extract_text_content(content)})
            elif role == "developer":
                flush_assistant_message()
                result.append({"role": "developer", "content": cls.extract_text_content(content)})
            elif role == "assistant":
                flush_assistant_message()
                result.append({"role": "assistant", "content": cls.extract_text_content(content)})
            else:
                raise UserError(f"Unexpected role in easy_input_message: {role}")

        # 2) InputMessage
        elif in_msg := cls.maybe_input_message(item):
            role = in_msg["role"]
            content = in_msg["content"]
            flush_assistant_message()
            if role == "user":
                result.append({"role": "user", "content": cls.extract_all_content(content)})
            elif role == "system":
                result.append({"role": "system", "content": cls.extract_text_content(content)})
            elif role == "developer":
                result.append({"role": "developer", "content": cls.extract_text_content(content)})
            else:
                raise UserError(f"Unexpected role in input_message: {role}")

        # 3) response_output_message => assistant
        elif resp_msg := cls.maybe_response_output_message(item):
            flush_assistant_message()
            new_asst = ChatCompletionAssistantMessageParam(role="assistant")
            contents = resp_msg["content"]
            text_segments = []
            for c in contents:
                if c["type"] == "output_text":
                    text_segments.append(c["text"])
                elif c["type"] == "refusal":
                    new_asst["refusal"] = c["refusal"]
                elif c["type"] == "output_audio":
                    raise UserError(
                        f"Only audio IDs are supported for chat completions, but got: {c}"
                    )
                else:
                    raise UserError(
                        f"Unknown content type in ResponseOutputMessage: {c}"
                    )
            if text_segments:
                new_asst["content"] = "\n".join(text_segments)
            if pending_thinking_blocks:
                if "content" in new_asst and isinstance(new_asst["content"], str):
                    new_asst["content"] = [
                        ChatCompletionContentPartTextParam(text=new_asst["content"], type="text")
                    ]
                if "content" not in new_asst or new_asst["content"] is None:
                    new_asst["content"] = []
                new_asst["content"] = pending_thinking_blocks + new_asst["content"]  # type: ignore
                pending_thinking_blocks = None
            new_asst["tool_calls"] = []
            current_assistant_msg = new_asst

        # 4) file_search call
        elif file_search := cls.maybe_file_search_call(item):
            asst = ensure_assistant_message()
            tool_calls = list(asst.get("tool_calls", []))
            tool_calls.append(
                ChatCompletionMessageFunctionToolCallParam(
                    id=file_search["id"],
                    type="function",
                    function={
                        "name": "file_search_call",
                        "arguments": json.dumps(
                            {
                                "queries": file_search.get("queries", []),
                                "status": file_search.get("status"),
                            }
                        ),
                    },
                )
            )
            asst["tool_calls"] = tool_calls

        # 4b) function tool call
        elif func_call := cls.maybe_function_tool_call(item):
            asst = ensure_assistant_message()
            if pending_reasoning_content:
                asst["reasoning_content"] = pending_reasoning_content  # type: ignore[typeddict-unknown-key]
                pending_reasoning_content = None
            if pending_thinking_blocks:
                if "content" in asst and isinstance(asst["content"], str):
                    asst["content"] = [
                        ChatCompletionContentPartTextParam(text=asst["content"], type="text")
                    ]
                if "content" not in asst or asst["content"] is None:
                    asst["content"] = []
                asst["content"] = pending_thinking_blocks + asst["content"]  # type: ignore
                pending_thinking_blocks = None
            tool_calls = list(asst.get("tool_calls", []))
            arguments = func_call["arguments"] if func_call["arguments"] else "{}"
            new_tool_call = ChatCompletionMessageFunctionToolCallParam(
                id=func_call["call_id"],
                type="function",
                function={"name": func_call["name"], "arguments": arguments},
            )
            if "provider_data" in func_call:
                provider_fields = func_call["provider_data"]  # type: ignore[typeddict-item]
                if isinstance(provider_fields, dict):
                    if model and "gemini" in model.lower():
                        thought_sig = provider_fields.get("thought_signature")
                        if thought_sig:
                            new_tool_call["extra_content"] = {  # type: ignore[typeddict-unknown-key]
                                "google": {"thought_signature": thought_sig}
                            }
            tool_calls.append(new_tool_call)
            asst["tool_calls"] = tool_calls

        # 5) function call output => tool message
        elif func_output := cls.maybe_function_tool_call_output(item):
            flush_assistant_message()
            output_content = cast(Any, func_output["output"])
            if preserve_tool_output_all_content:
                tool_result_content = cls.extract_all_content(output_content)
            else:
                tool_result_content = cls.extract_text_content(output_content)  # type: ignore[assignment]
            result.append(
                ChatCompletionToolMessageParam(
                    role="tool",
                    tool_call_id=func_output["call_id"],
                    content=tool_result_content,  # type: ignore[typeddict-item]
                )
            )

        # 6) item reference => unsupported
        elif item_ref := cls.maybe_item_reference(item):
            raise UserError(
                f"Encountered an item_reference, which is not supported: {item_ref}"
            )

        # 7) reasoning message
        elif reasoning_item := cls.maybe_reasoning_message(item):
            content_items = reasoning_item.get("content", [])
            encrypted_content = reasoning_item.get("encrypted_content")
            item_provider_data: dict[str, Any] = reasoning_item.get("provider_data", {})  # type: ignore[assignment]
            item_model = item_provider_data.get("model", "")

            if (
                model
                and ("claude" in model.lower() or "anthropic" in model.lower())
                and content_items
                and preserve_thinking_blocks
                and (model == item_model or item_provider_data == {})
            ):
                signatures = encrypted_content.split("\n") if encrypted_content else []
                reconstructed_thinking_blocks = []
                for content_item in content_items:
                    if (
                        isinstance(content_item, dict)
                        and content_item.get("type") == "reasoning_text"
                    ):
                        thinking_block: dict[str, str] = {
                            "type": "thinking",
                            "thinking": content_item.get("text", ""),
                        }
                        if signatures:
                            thinking_block["signature"] = signatures.pop(0)
                        reconstructed_thinking_blocks.append(thinking_block)
                pending_thinking_blocks = reconstructed_thinking_blocks

            elif (
                model
                and "deepseek" in model.lower()
                and (
                    (item_model and "deepseek" in item_model.lower())
                    or item_provider_data == {}
                )
            ):
                summary_items = reasoning_item.get("summary", [])
                if summary_items:
                    reasoning_texts = [
                        si["text"]
                        for si in summary_items
                        if isinstance(si, dict) and si.get("text")
                    ]
                    if reasoning_texts:
                        pending_reasoning_content = "\n".join(reasoning_texts)

        # 8) compaction => unsupported
        elif isinstance(item, dict) and item.get("type") == "compaction":
            raise UserError(
                "Compaction items are not supported for chat completions. "
                "Please use the Responses API to handle compaction."
            )

        # 9) unrecognized
        else:
            raise UserError(f"Unhandled item type or structure: {item}")

    flush_assistant_message()
    return result


def apply_deepseek_reasoning_patch() -> None:
    Converter.items_to_messages = classmethod(_fixed_items_to_messages)  # type: ignore[assignment]
