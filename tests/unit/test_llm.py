"""
LLM适配器单元测试 - DEV-001
测试覆盖: BaseLLMProvider, Message, ToolDefinition, ToolUseBlock, Usage, ChatResponse, ChatChunk
         create_llm_provider工厂方法, AnthropicProvider, OpenAIProvider (使用Mock)
"""
from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from core.config import LLMProvider, Settings
from core.llm.adapter import create_llm_provider
from core.llm.base import (
    BaseLLMProvider,
    ChatChunk,
    ChatResponse,
    Message,
    ToolDefinition,
    ToolUseBlock,
    Usage,
)

# ─── 数据模型测试 ─────────────────────────────────────────────────────────────

class TestMessage:
    """测试 Message 数据模型"""

    def test_message_creation_basic(self):
        """测试基本消息创建"""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_call_id is None
        assert msg.name is None

    def test_message_with_tool_call_id(self):
        """测试带工具调用ID的消息"""
        msg = Message(
            role="tool",
            content="Tool result",
            tool_call_id="call_123"
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"

    def test_message_with_list_content(self):
        """测试列表内容（多模态）"""
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "image", "source": {"url": "http://example.com/image.png"}}
        ]
        msg = Message(role="user", content=content)
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2

    def test_message_serialization(self):
        """测试消息序列化"""
        msg = Message(role="assistant", content="Response", name="assistant")
        data = msg.model_dump()
        assert data["role"] == "assistant"
        assert data["content"] == "Response"
        assert data["name"] == "assistant"


class TestToolDefinition:
    """测试 ToolDefinition 数据模型"""

    def test_tool_definition_creation(self):
        """测试工具定义创建"""
        tool = ToolDefinition(
            name="execute_shell_command",
            description="Execute a shell command",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string"}
                },
                "required": ["command"]
            }
        )
        assert tool.name == "execute_shell_command"
        assert tool.description == "Execute a shell command"
        assert "command" in tool.input_schema["properties"]

    def test_tool_definition_serialization(self):
        """测试工具定义序列化"""
        tool = ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object"}
        )
        data = tool.model_dump()
        assert data["name"] == "read_file"
        assert "input_schema" in data


class TestToolUseBlock:
    """测试 ToolUseBlock 数据模型"""

    def test_tool_use_block_creation(self):
        """测试工具调用块创建"""
        block = ToolUseBlock(
            id="call_abc123",
            name="execute_shell_command",
            input={"command": "echo hello"}
        )
        assert block.id == "call_abc123"
        assert block.name == "execute_shell_command"
        assert block.input["command"] == "echo hello"

    def test_tool_use_block_with_complex_input(self):
        """测试复杂输入的工具调用块"""
        block = ToolUseBlock(
            id="call_xyz",
            name="write_file",
            input={
                "file_path": "/tmp/test.txt",
                "content": "Hello World",
                "encoding": "utf-8"
            }
        )
        assert block.input["file_path"] == "/tmp/test.txt"
        assert block.input["content"] == "Hello World"


class TestUsage:
    """测试 Usage 数据模型"""

    def test_usage_defaults(self):
        """测试默认值"""
        usage = Usage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_read_input_tokens == 0
        assert usage.cache_creation_input_tokens == 0

    def test_usage_total_tokens(self):
        """测试总token计算"""
        usage = Usage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_usage_with_cache(self):
        """测试带缓存的用量"""
        usage = Usage(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=80,
            cache_creation_input_tokens=20
        )
        assert usage.cache_read_input_tokens == 80
        assert usage.total_tokens == 150


class TestChatResponse:
    """测试 ChatResponse 数据模型"""

    def test_chat_response_defaults(self):
        """测试默认值"""
        response = ChatResponse(content="Hello")
        assert response.content == "Hello"
        assert response.tool_uses == []
        assert response.finish_reason == "end_turn"
        assert response.model == ""

    def test_chat_response_with_tool_uses(self):
        """测试带工具调用的响应"""
        response = ChatResponse(
            content="",
            tool_uses=[
                ToolUseBlock(id="call_1", name="read_file", input={"file_path": "test.txt"})
            ],
            finish_reason="tool_use"
        )
        assert len(response.tool_uses) == 1
        assert response.finish_reason == "tool_use"

    def test_chat_response_serialization(self):
        """测试响应序列化"""
        response = ChatResponse(
            content="Done",
            usage=Usage(input_tokens=10, output_tokens=20),
            finish_reason="end_turn",
            model="claude-sonnet-4-20250514"
        )
        data = response.model_dump()
        assert data["content"] == "Done"
        assert data["model"] == "claude-sonnet-4-20250514"


class TestChatChunk:
    """测试 ChatChunk 数据模型"""

    def test_chat_chunk_defaults(self):
        """测试默认值"""
        chunk = ChatChunk()
        assert chunk.content == ""
        assert chunk.tool_use_delta is None
        assert chunk.finish_reason is None
        assert chunk.usage is None

    def test_chat_chunk_with_content(self):
        """测试带内容的块"""
        chunk = ChatChunk(content="Hello ", finish_reason=None)
        assert chunk.content == "Hello "

    def test_chat_chunk_with_usage(self):
        """测试带用量的块"""
        chunk = ChatChunk(
            content="",
            finish_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50)
        )
        assert chunk.usage is not None
        assert chunk.usage.input_tokens == 100


# ─── Mock LLM Provider ────────────────────────────────────────────────────────

class MockLLMProvider(BaseLLMProvider):
    """测试用 Mock LLM Provider"""

    def __init__(self, responses: list[ChatResponse] | None = None) -> None:
        super().__init__(model="mock-model")
        self._responses = responses or []
        self._call_count = 0

    def set_responses(self, responses: list[ChatResponse]) -> None:
        self._responses = responses
        self._call_count = 0

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> ChatResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = ChatResponse(content="Default response", finish_reason="end_turn")
        self._call_count += 1
        return resp

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        resp = await self.chat(messages, tools=tools, system=system)
        # 模拟流式输出
        words = resp.content.split()
        for i, word in enumerate(words):
            is_last = i == len(words) - 1
            yield ChatChunk(
                content=word + " ",
                finish_reason=resp.finish_reason if is_last else None
            )

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


# ─── BaseLLMProvider Tests ───────────────────────────────────────────────────

class TestBaseLLMProvider:
    """测试 BaseLLMProvider 抽象类"""

    def test_provider_initialization(self):
        """测试Provider初始化"""
        provider = MockLLMProvider()
        assert provider.model == "mock-model"

    def test_provider_with_custom_model(self):
        """测试自定义模型"""
        provider = MockLLMProvider()
        provider.model = "custom-model"
        assert provider.model == "custom-model"

    def test_extra_kwargs_storage(self):
        """测试额外参数存储"""
        provider = MockLLMProvider()
        provider._extra["temperature"] = 0.7
        assert provider._extra["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_chat_basic(self):
        """测试基本聊天功能"""
        provider = MockLLMProvider([
            ChatResponse(content="Hello, I'm Claude.", finish_reason="end_turn")
        ])
        messages = [Message(role="user", content="Hi")]
        response = await provider.chat(messages)
        assert response.content == "Hello, I'm Claude."
        assert response.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_chat_with_tools(self):
        """测试带工具的聊天"""
        provider = MockLLMProvider([
            ChatResponse(
                content="",
                tool_uses=[ToolUseBlock(id="call_1", name="read_file", input={"file_path": "test.txt"})],
                finish_reason="tool_use"
            )
        ])
        messages = [Message(role="user", content="Read test.txt")]
        tools = [ToolDefinition(name="read_file", description="Read a file", input_schema={"type": "object"})]
        response = await provider.chat(messages, tools=tools)
        assert len(response.tool_uses) == 1
        assert response.tool_uses[0].name == "read_file"

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self):
        """测试带系统提示的聊天"""
        provider = MockLLMProvider([
            ChatResponse(content="I'm helpful.", finish_reason="end_turn")
        ])
        messages = [Message(role="user", content="Who are you?")]
        response = await provider.chat(messages, system="You are a helpful assistant.")
        assert response.content == "I'm helpful."

    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """测试流式聊天"""
        provider = MockLLMProvider([
            ChatResponse(content="Hello World", finish_reason="end_turn")
        ])
        messages = [Message(role="user", content="Hi")]
        chunks = []
        async for chunk in provider.chat_stream(messages):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert "Hello" in "".join(c.content for c in chunks)

    def test_count_tokens(self):
        """测试Token计数"""
        provider = MockLLMProvider()
        text = "Hello, this is a test message"
        tokens = provider.count_tokens(text)
        assert tokens > 0
        # Mock实现使用 len(text) // 4
        assert tokens == len(text) // 4

    @pytest.mark.asyncio
    async def test_multiple_responses(self):
        """测试多次调用"""
        provider = MockLLMProvider([
            ChatResponse(content="First", finish_reason="end_turn"),
            ChatResponse(content="Second", finish_reason="end_turn"),
        ])
        messages = [Message(role="user", content="Test")]

        resp1 = await provider.chat(messages)
        resp2 = await provider.chat(messages)

        assert resp1.content == "First"
        assert resp2.content == "Second"

    @pytest.mark.asyncio
    async def test_default_response_when_exhausted(self):
        """测试响应耗尽时的默认响应"""
        provider = MockLLMProvider([
            ChatResponse(content="Only one", finish_reason="end_turn"),
        ])
        messages = [Message(role="user", content="Test")]

        await provider.chat(messages)
        resp = await provider.chat(messages)

        assert resp.content == "Default response"


# ─── LLM Adapter Factory Tests ───────────────────────────────────────────────

class TestCreateLLMProvider:
    """测试 LLM Provider 工厂方法"""

    def test_create_anthropic_provider(self):
        """测试创建 Anthropic Provider"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("core.llm.adapter.get_settings") as mock_settings:
                mock_settings.return_value = Settings(
                    anthropic_api_key="test-key",
                    default_provider=LLMProvider.ANTHROPIC,
                    default_model="claude-sonnet-4-20250514"
                )
                # Patch延迟导入的类
                with patch("core.llm.anthropic.AnthropicProvider") as mock_provider_class:
                    mock_provider_class.return_value = MagicMock()
                    provider = create_llm_provider(provider=LLMProvider.ANTHROPIC)
                    mock_provider_class.assert_called_once()

    def test_create_openai_provider(self):
        """测试创建 OpenAI Provider"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("core.llm.adapter.get_settings") as mock_settings:
                mock_settings.return_value = Settings(
                    openai_api_key="test-key",
                    default_provider=LLMProvider.OPENAI
                )
                # Patch延迟导入的类
                with patch("core.llm.openai.OpenAIProvider") as mock_provider_class:
                    mock_provider_class.return_value = MagicMock()
                    provider = create_llm_provider(provider=LLMProvider.OPENAI)
                    mock_provider_class.assert_called_once()

    def test_create_provider_from_string(self):
        """测试从字符串创建 Provider"""
        with patch("core.llm.adapter.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                anthropic_api_key="test-key",
                default_provider=LLMProvider.ANTHROPIC
            )
            # Patch延迟导入的类
            with patch("core.llm.anthropic.AnthropicProvider") as mock_provider_class:
                mock_provider_class.return_value = MagicMock()
                provider = create_llm_provider(provider="anthropic")
                mock_provider_class.assert_called_once()

    def test_unsupported_provider_raises_error(self):
        """测试不支持的 Provider 抛出错误"""
        with patch("core.llm.adapter.get_settings") as mock_settings:
            # 创建一个有效的Settings对象
            mock_settings.return_value = Settings()
            with pytest.raises(ValueError, match="Unsupported LLM provider"):
                # 使用字符串来避免枚举验证错误
                with patch("core.llm.adapter.LLMProvider") as mock_enum:
                    mock_enum.side_effect = lambda x: x
                    create_llm_provider(provider="unsupported_provider")


# ─── Anthropic Provider Tests (使用 Mock) ───────────────────────────────────

class TestAnthropicProvider:
    """测试 Anthropic Provider（使用 Mock）"""

    @pytest.mark.asyncio
    async def test_anthropic_chat_basic(self):
        """测试 Anthropic 基本聊天"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello from Claude")]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=20,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0
        )
        mock_response.stop_reason = "end_turn"
        mock_response.model = "claude-sonnet-4-20250514"
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            from core.llm.anthropic import AnthropicProvider
            provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

            messages = [Message(role="user", content="Hi")]
            response = await provider.chat(messages)

            assert response.content == "Hello from Claude"
            assert response.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_anthropic_chat_with_tools(self):
        """测试 Anthropic 工具调用"""
        mock_client = AsyncMock()
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool_123"
        mock_tool_block.name = "read_file"
        mock_tool_block.input = {"file_path": "test.txt"}

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=20,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0
        )
        mock_response.stop_reason = "tool_use"
        mock_response.model = "claude-sonnet-4-20250514"
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            from core.llm.anthropic import AnthropicProvider
            provider = AnthropicProvider(api_key="test-key")

            messages = [Message(role="user", content="Read test.txt")]
            tools = [ToolDefinition(
                name="read_file",
                description="Read a file",
                input_schema={"type": "object", "properties": {"file_path": {"type": "string"}}}
            )]
            response = await provider.chat(messages, tools=tools)

            assert len(response.tool_uses) == 1
            assert response.tool_uses[0].name == "read_file"
            assert response.finish_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_anthropic_count_tokens(self):
        """测试 Anthropic Token 计数"""
        with patch("anthropic.AsyncAnthropic"):
            from core.llm.anthropic import AnthropicProvider
            provider = AnthropicProvider(api_key="test-key")

            # 测试Token计数（使用估算或tiktoken）
            tokens = provider.count_tokens("Hello World")
            assert tokens > 0


# ─── OpenAI Provider Tests (使用 Mock) ───────────────────────────────────────

class TestOpenAIProvider:
    """测试 OpenAI Provider（使用 Mock）"""

    @pytest.mark.asyncio
    async def test_openai_chat_basic(self):
        """测试 OpenAI 基本聊天"""
        mock_client = AsyncMock()
        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="Hello from GPT")
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
        mock_response.model = "gpt-4o"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            from core.llm.openai import OpenAIProvider
            provider = OpenAIProvider(api_key="test-key")

            messages = [Message(role="user", content="Hi")]
            response = await provider.chat(messages)

            assert response.content == "Hello from GPT"

    @pytest.mark.asyncio
    async def test_openai_chat_with_tools(self):
        """测试 OpenAI 工具调用"""
        mock_client = AsyncMock()
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = '{"file_path": "test.txt"}'

        mock_message = MagicMock()
        mock_message.content = ""
        mock_message.tool_calls = [mock_tool_call]

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
        mock_response.model = "gpt-4o"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            from core.llm.openai import OpenAIProvider
            provider = OpenAIProvider(api_key="test-key")

            messages = [Message(role="user", content="Read test.txt")]
            tools = [ToolDefinition(
                name="read_file",
                description="Read a file",
                input_schema={"type": "object", "properties": {"file_path": {"type": "string"}}}
            )]
            response = await provider.chat(messages, tools=tools)

            assert len(response.tool_uses) == 1
            assert response.tool_uses[0].name == "read_file"

    @pytest.mark.asyncio
    async def test_openai_count_tokens(self):
        """测试 OpenAI Token 计数"""
        with patch("openai.AsyncOpenAI"):
            from core.llm.openai import OpenAIProvider
            provider = OpenAIProvider(api_key="test-key")

            tokens = provider.count_tokens("Hello World")
            assert tokens > 0


# ─── Message Conversion Tests ────────────────────────────────────────────────

class TestMessageConversion:
    """测试消息格式转换"""

    def test_anthropic_message_conversion(self):
        """测试 Anthropic 消息格式转换"""
        from core.llm.anthropic import _convert_messages

        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
            Message(role="tool", content="Result", tool_call_id="call_123")
        ]

        converted = _convert_messages(messages)

        assert len(converted) == 3
        assert converted[0]["role"] == "user"
        assert converted[0]["content"] == "Hello"
        assert converted[1]["role"] == "assistant"
        # tool消息应该被转换为user消息（Anthropic格式）
        assert converted[2]["role"] == "user"
        assert converted[2]["content"][0]["type"] == "tool_result"

    def test_openai_message_conversion(self):
        """测试 OpenAI 消息格式转换"""
        from core.llm.openai import _convert_messages

        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
            Message(role="tool", content="Result", tool_call_id="call_123")
        ]

        converted = _convert_messages(messages)

        assert len(converted) == 3
        assert converted[0]["role"] == "user"
        assert converted[2]["role"] == "tool"

    def test_tool_definition_conversion_anthropic(self):
        """测试 Anthropic 工具定义转换"""
        from core.llm.anthropic import _convert_tools

        tools = [
            ToolDefinition(
                name="read_file",
                description="Read a file",
                input_schema={"type": "object", "properties": {"file_path": {"type": "string"}}}
            )
        ]

        converted = _convert_tools(tools)

        assert len(converted) == 1
        assert converted[0]["name"] == "read_file"
        assert "input_schema" in converted[0]

    def test_tool_definition_conversion_openai(self):
        """测试 OpenAI 工具定义转换"""
        from core.llm.openai import _convert_tools

        tools = [
            ToolDefinition(
                name="write_file",
                description="Write a file",
                input_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "content": {"type": "string"}
                    }
                }
            )
        ]

        converted = _convert_tools(tools)

        assert len(converted) == 1
        assert converted[0]["type"] == "function"
        assert converted[0]["function"]["name"] == "write_file"


# ─── Integration Tests ───────────────────────────────────────────────────────

class TestLLMIntegration:
    """LLM 集成测试"""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """测试完整对话流程"""
        provider = MockLLMProvider([
            ChatResponse(content="I can help you with that.", finish_reason="end_turn"),
            ChatResponse(
                content="",
                tool_uses=[ToolUseBlock(id="call_1", name="read_file", input={"file_path": "test.txt"})],
                finish_reason="tool_use"
            ),
            ChatResponse(content="The file contains 'Hello World'", finish_reason="end_turn"),
        ])

        # 第一轮
        messages = [Message(role="user", content="Can you help me?")]
        response1 = await provider.chat(messages)
        assert "help" in response1.content.lower()

        # 第二轮（带工具调用）
        messages.append(Message(role="assistant", content=response1.content))
        messages.append(Message(role="user", content="Read test.txt"))
        response2 = await provider.chat(messages)
        assert len(response2.tool_uses) == 1

        # 第三轮（工具结果后继续）
        messages.append(Message(role="assistant", content="", tool_uses=response2.tool_uses))
        messages.append(Message(role="tool", content="File content", tool_call_id="call_1"))
        response3 = await provider.chat(messages)
        assert "Hello World" in response3.content

    @pytest.mark.asyncio
    async def test_streaming_aggregation(self):
        """测试流式响应聚合"""
        provider = MockLLMProvider([
            ChatResponse(content="This is a streaming test", finish_reason="end_turn")
        ])

        messages = [Message(role="user", content="Test streaming")]
        full_content = ""
        async for chunk in provider.chat_stream(messages):
            full_content += chunk.content

        assert "streaming" in full_content.lower()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """测试错误处理"""
        provider = MockLLMProvider()
        provider._responses = []  # 清空响应，测试默认行为

        messages = [Message(role="user", content="Test")]
        response = await provider.chat(messages)

        # 应该返回默认响应而不是抛出错误
        assert response.content == "Default response"
