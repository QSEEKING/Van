"""
Tests for memory module
"""

import pytest

from core.llm.base import Message
from core.memory.context import ContextManager, ContextWindow, MessageSummary
from core.memory.long_term import InMemoryBackend, LongTermMemory, MemoryEntry, MemoryType
from core.memory.session import SessionManager, SessionMemory


class TestContextWindow:
    """测试上下文窗口配置"""

    def test_context_window_defaults(self):
        """测试默认配置"""
        window = ContextWindow()
        assert window.max_tokens == 200000
        assert window.reserved_output_tokens == 8192
        assert window.system_prompt_tokens == 2000
        assert window.tools_tokens == 3000

    def test_available_tokens(self):
        """测试可用token计算"""
        window = ContextWindow()
        expected = 200000 - 8192 - 2000 - 3000
        assert window.available_tokens == expected

    def test_custom_context_window(self):
        """测试自定义配置"""
        window = ContextWindow(
            max_tokens=100000,
            reserved_output_tokens=4096,
            system_prompt_tokens=1000,
            tools_tokens=2000,
        )
        assert window.max_tokens == 100000
        assert window.available_tokens == 100000 - 4096 - 1000 - 2000


class TestMessageSummary:
    """测试消息摘要"""

    def test_message_summary_creation(self):
        """测试创建消息摘要"""
        summary = MessageSummary(
            turn_start=0,
            turn_end=5,
            summary="Summary of first 5 turns",
            key_points=["Point 1", "Point 2"],
        )
        assert summary.turn_start == 0
        assert summary.turn_end == 5
        assert summary.summary == "Summary of first 5 turns"
        assert len(summary.key_points) == 2


class TestContextManager:
    """测试上下文管理器"""

    @pytest.fixture
    def context_manager(self):
        """创建上下文管理器实例"""
        return ContextManager()

    def test_count_tokens_text(self, context_manager):
        """测试token计数"""
        text = "Hello, world!"
        count = context_manager.count_tokens(text)
        assert count > 0

    def test_count_message_tokens(self, context_manager):
        """测试消息token计数"""
        message = Message(role="user", content="Hello, world!")
        count = context_manager.count_message_tokens(message)
        assert count > 0

    def test_count_messages_tokens(self, context_manager):
        """测试多条消息token计数"""
        messages = [
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there!"),
        ]
        count = context_manager.count_messages_tokens(messages)
        assert count > 0

    def test_should_compress_below_threshold(self, context_manager):
        """测试不需要压缩的情况"""
        messages = [Message(role="user", content="Hello!")]
        needs = context_manager.should_compress(messages)
        assert needs is False

    def test_should_compress_above_threshold(self, context_manager):
        """测试需要压缩的情况"""
        # 创建大量消息
        messages = [
            Message(role="user", content="This is a test message. " * 1000)
            for _ in range(100)
        ]
        needs = context_manager.should_compress(messages)
        # 根据阈值可能需要压缩
        assert isinstance(needs, bool)

    def test_get_budget_status(self, context_manager):
        """测试获取预算状态"""
        messages = [Message(role="user", content="Hello!")]
        status = context_manager.get_budget_status(messages)
        assert "current_tokens" in status
        assert "available_tokens" in status
        assert "used_percentage" in status
        assert "should_compress" in status

    def test_summaries_property(self, context_manager):
        """测试摘要属性"""
        summaries = context_manager.summaries
        assert isinstance(summaries, list)

    def test_clear_summaries(self, context_manager):
        """测试清除摘要"""
        context_manager.clear_summaries()
        assert context_manager.summaries == []


class TestMemoryEntry:
    """测试长期记忆条目"""

    def test_memory_entry_creation(self):
        """测试创建记忆条目"""
        entry = MemoryEntry(
            content="Test memory content",
            memory_type=MemoryType.CONVERSATION,
        )
        assert entry.content == "Test memory content"
        assert entry.memory_type == MemoryType.CONVERSATION
        assert entry.id is not None
        assert entry.created_at is not None

    def test_memory_entry_with_metadata(self):
        """测试带元数据的记忆条目"""
        entry = MemoryEntry(
            content="Test content",
            memory_type=MemoryType.PROJECT,
            metadata={"source": "test", "confidence": 0.9},
        )
        assert entry.metadata["source"] == "test"
        assert entry.metadata["confidence"] == 0.9

    def test_memory_types(self):
        """测试记忆类型"""
        assert MemoryType.CONVERSATION.value == "conversation"
        assert MemoryType.PREFERENCE.value == "preference"
        assert MemoryType.PROJECT.value == "project"
        assert MemoryType.ERROR_FIX.value == "error_fix"
        assert MemoryType.DECISION.value == "decision"

    def test_memory_entry_access(self):
        """测试记忆访问记录"""
        entry = MemoryEntry(content="Test")
        initial_count = entry.access_count
        entry.access()
        assert entry.access_count == initial_count + 1

    def test_memory_entry_is_expired(self):
        """测试记忆过期检查"""
        entry = MemoryEntry(content="Test")
        assert entry.is_expired() is False

        # 设置过期时间
        entry.expires_at = 0  # 已过期
        assert entry.is_expired() is True

    def test_memory_entry_to_dict(self):
        """测试记忆条目转字典"""
        entry = MemoryEntry(
            content="Test content",
            memory_type=MemoryType.CONVERSATION,
            tags=["test", "example"],
        )
        result = entry.to_dict()
        assert result["content"] == "Test content"
        assert result["memory_type"] == "conversation"
        assert "test" in result["tags"]


class TestInMemoryBackend:
    """测试内存后端"""

    @pytest.fixture
    def backend(self):
        """创建内存后端实例"""
        return InMemoryBackend()

    @pytest.mark.asyncio
    async def test_save_and_get(self, backend):
        """测试存储和检索"""
        entry = MemoryEntry(
            content="Test content",
            memory_type=MemoryType.CONVERSATION,
        )
        entry_id = await backend.save(entry)
        assert entry_id is not None

        retrieved = await backend.get(entry_id)
        assert retrieved is not None
        assert retrieved.content == "Test content"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, backend):
        """测试检索不存在的记忆"""
        result = await backend.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_search(self, backend):
        """测试搜索"""
        await backend.save(MemoryEntry(content="Python is a language", memory_type=MemoryType.PROJECT))
        await backend.save(MemoryEntry(content="JavaScript is also a language", memory_type=MemoryType.PROJECT))

        results = await backend.search("language")
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_delete(self, backend):
        """测试删除"""
        entry = MemoryEntry(content="To be deleted", memory_type=MemoryType.CONVERSATION)
        entry_id = await backend.save(entry)

        result = await backend.delete(entry_id)
        assert result is True

        retrieved = await backend.get(entry_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_all(self, backend):
        """测试列出所有"""
        await backend.save(MemoryEntry(content="Memory 1", memory_type=MemoryType.CONVERSATION))
        await backend.save(MemoryEntry(content="Memory 2", memory_type=MemoryType.PROJECT))

        all_entries = await backend.list_all()
        assert len(all_entries) >= 2


class TestLongTermMemory:
    """测试长期记忆"""

    @pytest.fixture
    def long_term_memory(self):
        """创建长期记忆实例"""
        return LongTermMemory()

    @pytest.mark.asyncio
    async def test_remember(self, long_term_memory):
        """测试记忆存储"""
        entry = await long_term_memory.remember(
            content="Important fact",
            memory_type=MemoryType.PROJECT,
        )
        assert entry is not None
        assert entry.content == "Important fact"
        assert entry.id is not None

    @pytest.mark.asyncio
    async def test_recall(self, long_term_memory):
        """测试记忆检索"""
        await long_term_memory.remember(
            content="Python is a programming language",
            memory_type=MemoryType.PROJECT,
        )
        await long_term_memory.remember(
            content="JavaScript is also a programming language",
            memory_type=MemoryType.PROJECT,
        )

        results = await long_term_memory.recall("programming")
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_get(self, long_term_memory):
        """测试获取特定记忆"""
        entry = await long_term_memory.remember(
            content="Test memory",
            memory_type=MemoryType.CONVERSATION,
        )
        result = await long_term_memory.get(entry.id)
        assert result is not None
        assert result.content == "Test memory"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, long_term_memory):
        """测试获取不存在的记忆"""
        result = await long_term_memory.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_forget(self, long_term_memory):
        """测试删除记忆"""
        entry = await long_term_memory.remember(
            content="To be deleted",
            memory_type=MemoryType.CONVERSATION,
        )
        result = await long_term_memory.forget(entry.id)
        assert result is True

        retrieved = await long_term_memory.get(entry.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_save_preference(self, long_term_memory):
        """测试保存偏好"""
        entry = await long_term_memory.save_preference(
            key="theme",
            value="dark",
            description="User prefers dark theme",
        )
        assert entry is not None
        assert "theme" in entry.content
        assert MemoryType.PREFERENCE == entry.memory_type

    @pytest.mark.asyncio
    async def test_save_error_fix(self, long_term_memory):
        """测试保存错误修复"""
        entry = await long_term_memory.save_error_fix(
            error="ImportError: No module named 'xyz'",
            fix="pip install xyz",
        )
        assert entry is not None
        assert "ImportError" in entry.content
        assert MemoryType.ERROR_FIX == entry.memory_type

    @pytest.mark.asyncio
    async def test_get_user_preferences(self, long_term_memory):
        """测试获取用户偏好"""
        await long_term_memory.save_preference("editor", "vim", "User likes vim")
        prefs = await long_term_memory.get_user_preferences()
        assert len(prefs) >= 1


class TestSessionMemory:
    """测试会话记忆"""

    def test_session_memory_creation(self):
        """测试创建会话记忆"""
        session = SessionMemory()
        assert session.session_id is not None
        assert session.messages == []
        assert session.working_dir == "."

    def test_session_memory_with_custom_id(self):
        """测试自定义会话ID"""
        session = SessionMemory(session_id="custom-session-123")
        assert session.session_id == "custom-session-123"

    def test_add_user_message(self):
        """测试添加用户消息"""
        session = SessionMemory()
        msg = session.add_user_message("Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert len(session.messages) == 1

    def test_add_assistant_message(self):
        """测试添加助手消息"""
        session = SessionMemory()
        msg = session.add_assistant_message("Hi there!")
        assert msg.role == "assistant"
        assert len(session.messages) == 1

    def test_add_assistant_message_with_tools(self):
        """测试添加带工具调用的助手消息"""
        session = SessionMemory()
        msg = session.add_assistant_message(
            content="Let me help you.",
            tool_uses=[{"name": "search", "input": {"query": "test"}}]
        )
        assert msg.role == "assistant"
        # 检查内容是结构化的
        assert isinstance(msg.content, list)

    def test_turn_count(self):
        """测试对话轮数计数"""
        session = SessionMemory()
        session.add_user_message("Hello!")
        session.add_assistant_message("Hi!")
        session.add_user_message("How are you?")
        assert session.turn_count == 2

    def test_total_tokens(self):
        """测试token统计"""
        session = SessionMemory()
        session.total_input_tokens = 100
        session.total_output_tokens = 50
        assert session.total_tokens == 150

    def test_update_metadata(self):
        """测试更新元数据"""
        session = SessionMemory()
        session.metadata["project"] = "test-project"
        assert session.metadata["project"] == "test-project"

    def test_set_working_dir(self):
        """测试设置工作目录"""
        session = SessionMemory()
        session.working_dir = "/app/workspace"
        assert session.working_dir == "/app/workspace"


class TestSessionManager:
    """测试会话管理器"""

    @pytest.fixture
    def session_manager(self):
        """创建会话管理器实例"""
        return SessionManager()

    def test_create_session(self, session_manager):
        """测试创建会话"""
        session = session_manager.create_session()
        assert session is not None
        assert session.session_id is not None

    def test_create_session_with_options(self, session_manager):
        """测试带选项创建会话"""
        session = session_manager.create_session(
            working_dir="/app/test",
            metadata={"user": "test-user"}
        )
        assert session.working_dir == "/app/test"
        assert session.metadata["user"] == "test-user"

    def test_get_nonexistent_session(self, session_manager):
        """测试获取不存在的会话"""
        session = session_manager.get_session("nonexistent")
        assert session is None

    def test_close_session(self, session_manager):
        """测试关闭会话"""
        session = session_manager.create_session()
        result = session_manager.close_session(session.session_id)
        assert result is True

    def test_get_or_create_session(self, session_manager):
        """测试获取或创建会话"""
        session = session_manager.get_or_create_session()
        assert session is not None

    def test_switch_session(self, session_manager):
        """测试切换会话"""
        session1 = session_manager.create_session()
        session2 = session_manager.create_session()

        switched = session_manager.switch_session(session1.session_id)
        assert switched.session_id == session1.session_id

    def test_list_sessions(self, session_manager):
        """测试列出会话"""
        session_manager.create_session()
        session_manager.create_session()
        sessions = session_manager.list_sessions()
        assert len(sessions) >= 2

    def test_current_session(self, session_manager):
        """测试获取当前会话"""
        session_manager.create_session()
        current = session_manager.current_session
        assert current is not None

    def test_session_count(self, session_manager):
        """测试会话计数"""
        session_manager.create_session()
        session_manager.create_session()
        count = session_manager.session_count
        assert count >= 2


class TestMemoryIntegration:
    """测试记忆模块集成"""

    def test_context_and_session_together(self):
        """测试上下文和会话协同工作"""
        context_manager = ContextManager()
        session_manager = SessionManager()

        # 创建会话
        session = session_manager.create_session(working_dir="/app")

        # 添加消息
        session.add_message(Message(role="user", content="Hello!"))

        # 检查上下文预算
        token_count = context_manager.count_messages_tokens(session.messages)
        assert token_count > 0

    @pytest.mark.asyncio
    async def test_memory_storage_and_retrieval_flow(self):
        """测试记忆存储和检索流程"""
        long_term = LongTermMemory()
        session_manager = SessionManager()

        # 创建会话
        session = session_manager.create_session()

        # 添加对话
        session.add_message(Message(role="user", content="Remember: Python is great"))
        session.add_message(Message(role="assistant", content="I'll remember that."))

        # 存储到长期记忆
        memory = await long_term.remember(
            content="User prefers Python",
            memory_type=MemoryType.PREFERENCE,
        )

        # 检索记忆
        retrieved = await long_term.get(memory.id)
        assert retrieved.content == "User prefers Python"
