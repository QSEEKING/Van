"""
Tests for storage module - Full coverage tests
"""

import pytest

from core.config import Settings
from storage.database import Database, get_database
from storage.models import (
    Memory,
    MemoryType,
    Message,
    Session,
    SessionStatus,
    ToolCall,
    UserConfig,
)


class TestSessionStatus:
    """Test Session Status Enum"""

    def test_session_status_values(self):
        """Test status values"""
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.PAUSED.value == "paused"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.ARCHIVED.value == "archived"

    def test_session_status_from_string(self):
        """Test conversion from string"""
        assert SessionStatus("active") == SessionStatus.ACTIVE
        assert SessionStatus("paused") == SessionStatus.PAUSED
        assert SessionStatus("completed") == SessionStatus.COMPLETED

    def test_session_status_all_values(self):
        """Test all status values"""
        statuses = list(SessionStatus)
        assert len(statuses) == 4


class TestMemoryType:
    """Test Memory Type Enum"""

    def test_memory_type_values(self):
        """Test type values"""
        assert MemoryType.FACT.value == "fact"
        assert MemoryType.PREFERENCE.value == "preference"
        assert MemoryType.CONTEXT.value == "context"
        assert MemoryType.TASK.value == "task"
        assert MemoryType.ERROR.value == "error"
        assert MemoryType.SUMMARY.value == "summary"

    def test_memory_type_from_string(self):
        """Test conversion from string"""
        assert MemoryType("fact") == MemoryType.FACT
        assert MemoryType("preference") == MemoryType.PREFERENCE
        assert MemoryType("context") == MemoryType.CONTEXT

    def test_memory_type_all_values(self):
        """Test all type values"""
        types = list(MemoryType)
        assert len(types) == 6


class TestSessionModel:
    """Test Session Model"""

    def test_session_creation(self):
        """Test creating session"""
        session = Session(
            id="test-session-123",
            user_id="user-001",
            agent_id="agent-001",
            status=SessionStatus.ACTIVE,
        )
        assert session.id == "test-session-123"
        assert session.user_id == "user-001"
        assert session.agent_id == "agent-001"
        assert session.status == SessionStatus.ACTIVE

    def test_session_default_status(self):
        """Test default status"""
        session = Session(
            id="test-id",
            user_id="user-001",
            agent_id="agent-001",
        )
        # When created without status, it has the default
        # SQLAlchemy model default is applied at DB level, not Python level
        # So we just verify the column has a default
        assert Session.__table__.columns['status'].default.arg == SessionStatus.ACTIVE

    def test_session_with_title(self):
        """Test session with title"""
        session = Session(
            id="test-id",
            user_id="user-001",
            agent_id="agent-001",
            title="Test Session Title",
        )
        assert session.title == "Test Session Title"

    def test_session_repr(self):
        """Test session repr"""
        session = Session(
            id="test-id",
            user_id="user-001",
            agent_id="agent-001",
            status=SessionStatus.ACTIVE,
        )
        repr_str = repr(session)
        assert "Session" in repr_str
        assert "test-id" in repr_str

    def test_session_table_name(self):
        """Test table name"""
        assert Session.__tablename__ == "sessions"

    def test_session_columns(self):
        """Test session columns"""
        columns = Session.__table__.columns
        assert 'id' in columns.keys()
        assert 'user_id' in columns.keys()
        assert 'agent_id' in columns.keys()
        assert 'status' in columns.keys()


class TestMessageModel:
    """Test Message Model"""

    def test_message_creation(self):
        """Test creating message"""
        msg = Message(
            session_id="session-123",
            role="user",
            content="Hello, world!",
        )
        assert msg.session_id == "session-123"
        assert msg.role == "user"
        assert msg.content == "Hello, world!"

    def test_message_roles(self):
        """Test message roles"""
        roles = ["user", "assistant", "system"]
        for role in roles:
            msg = Message(session_id="s1", role=role, content="Test")
            assert msg.role == role

    def test_message_with_tokens(self):
        """Test message with token count"""
        msg = Message(
            session_id="session-123",
            role="user",
            content="Hello!",
            tokens=10,
        )
        assert msg.tokens == 10

    def test_message_with_tool_call(self):
        """Test message with tool call info"""
        msg = Message(
            session_id="session-123",
            role="assistant",
            content="Let me help you.",
            tool_call_id="call-123",
            tool_name="search",
        )
        assert msg.tool_call_id == "call-123"
        assert msg.tool_name == "search"

    def test_message_table_name(self):
        """Test table name"""
        assert Message.__tablename__ == "messages"

    def test_message_columns(self):
        """Test message columns"""
        columns = Message.__table__.columns
        assert 'session_id' in columns.keys()
        assert 'role' in columns.keys()
        assert 'content' in columns.keys()


class TestMemoryModel:
    """Test Memory Model"""

    def test_memory_creation(self):
        """Test creating memory"""
        memory = Memory(
            user_id="user-001",
            memory_type=MemoryType.FACT,
            content="Important fact",
        )
        assert memory.user_id == "user-001"
        assert memory.memory_type == MemoryType.FACT
        assert memory.content == "Important fact"

    def test_memory_types(self):
        """Test memory types"""
        for mem_type in [MemoryType.FACT, MemoryType.PREFERENCE,
                         MemoryType.CONTEXT, MemoryType.TASK,
                         MemoryType.ERROR, MemoryType.SUMMARY]:
            memory = Memory(user_id="u1", memory_type=mem_type, content="Test")
            assert memory.memory_type == mem_type

    def test_memory_with_importance(self):
        """Test memory importance"""
        memory = Memory(
            user_id="user-001",
            memory_type=MemoryType.FACT,
            content="Critical info",
            importance=9,
        )
        assert memory.importance == 9

    def test_memory_default_importance(self):
        """Test default importance"""
        # SQLAlchemy model default is applied at DB level, not Python level
        # So we verify the column has a default
        assert Memory.__table__.columns['importance'].default.arg == 5

    def test_memory_with_keywords(self):
        """Test memory keywords"""
        memory = Memory(
            user_id="user-001",
            memory_type=MemoryType.FACT,
            content="Python fact",
            keywords="python,programming",
        )
        assert memory.keywords == "python,programming"

    def test_memory_table_name(self):
        """Test table name"""
        assert Memory.__tablename__ == "memories"

    def test_memory_columns(self):
        """Test memory columns"""
        columns = Memory.__table__.columns
        assert 'user_id' in columns.keys()
        assert 'content' in columns.keys()
        assert 'memory_type' in columns.keys()
        assert 'importance' in columns.keys()


class TestToolCallModel:
    """Test Tool Call Model"""

    def test_tool_call_creation(self):
        """Test creating tool call"""
        call = ToolCall(
            session_id="session-123",
            tool_name="read_file",
            params='{"file_path": "/app/test.py"}',
        )
        assert call.session_id == "session-123"
        assert call.tool_name == "read_file"

    def test_tool_call_with_result(self):
        """Test tool call with result"""
        call = ToolCall(
            session_id="session-123",
            tool_name="execute",
            params='{"command": "ls"}',
            result="file1.py\nfile2.py",
            success=True,
            duration_ms=100,
        )
        assert call.success is True
        assert call.result == "file1.py\nfile2.py"
        assert call.duration_ms == 100

    def test_tool_call_default_success(self):
        """Test default success status"""
        # SQLAlchemy model default is applied at DB level, not Python level
        # So we verify the column has a default
        assert ToolCall.__table__.columns['success'].default.arg == True

    def test_tool_call_table_name(self):
        """Test table name"""
        assert ToolCall.__tablename__ == "tool_calls"

    def test_tool_call_columns(self):
        """Test tool call columns"""
        columns = ToolCall.__table__.columns
        assert 'session_id' in columns.keys()
        assert 'tool_name' in columns.keys()
        assert 'params' in columns.keys()
        assert 'result' in columns.keys()
        assert 'success' in columns.keys()


class TestUserConfigModel:
    """Test User Config Model"""

    def test_user_config_creation(self):
        """Test creating user config"""
        config = UserConfig(
            user_id="user-001",
            config_key="theme",
            config_value="dark",
        )
        assert config.user_id == "user-001"
        assert config.config_key == "theme"
        assert config.config_value == "dark"

    def test_user_config_table_name(self):
        """Test table name"""
        assert UserConfig.__tablename__ == "user_configs"

    def test_user_config_columns(self):
        """Test user config columns"""
        columns = UserConfig.__table__.columns
        assert 'user_id' in columns.keys()
        assert 'config_key' in columns.keys()
        assert 'config_value' in columns.keys()


class TestDatabase:
    """Test Database Manager"""

    @pytest.fixture
    def settings(self):
        """Create test settings"""
        return Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            debug=True,
        )

    @pytest.fixture
    def database(self, settings):
        """Create database instance"""
        return Database(settings=settings)

    def test_database_creation(self, settings):
        """Test creating database instance"""
        db = Database(settings=settings)
        assert db.settings == settings

    def test_database_default_settings(self):
        """Test default settings"""
        db = Database()
        assert db.settings is not None

    def test_database_not_initialized_error(self, database):
        """Test accessing engine before init"""
        with pytest.raises(RuntimeError, match="not initialized"):
            database.engine

    def test_database_not_initialized_session_factory(self, database):
        """Test accessing session factory before init"""
        with pytest.raises(RuntimeError, match="not initialized"):
            database.session_factory

    def test_get_engine_config_sqlite(self, database):
        """Test SQLite engine config"""
        config = database._get_engine_config()
        assert "poolclass" in config
        assert "connect_args" in config

    def test_get_engine_config_postgresql(self):
        """Test PostgreSQL engine config"""
        pg_settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            debug=False,
        )
        db = Database(settings=pg_settings)
        config = db._get_engine_config()
        assert "pool_size" in config
        assert "pool_pre_ping" in config

    @pytest.mark.asyncio
    async def test_database_init(self, database):
        """Test database initialization"""
        await database.init()
        assert database._engine is not None
        assert database._session_factory is not None

    @pytest.mark.asyncio
    async def test_database_init_twice_warning(self, database):
        """Test double initialization"""
        await database.init()
        # Second init should not error, just warn
        await database.init()
        assert database._engine is not None

    @pytest.mark.asyncio
    async def test_create_tables(self, database):
        """Test creating tables"""
        await database.init()
        # Tables should be created
        assert database._engine is not None

    @pytest.mark.asyncio
    async def test_session_generator(self, database):
        """Test session generator"""
        await database.init()
        async with database.session() as session:
            assert session is not None

    @pytest.mark.asyncio
    async def test_close(self, database):
        """Test closing database"""
        await database.init()
        await database.close()
        # Engine should be cleaned up

    @pytest.mark.asyncio
    async def test_drop_tables(self, database):
        """Test dropping tables"""
        await database.init()
        await database.drop_tables()

    @pytest.mark.asyncio
    async def test_execute_raw(self, database):
        """Test executing raw SQL"""
        await database.init()
        result = await database.execute_raw("SELECT 1")
        assert result is not None


class TestDatabaseIntegration:
    """Test Database Integration"""

    @pytest.fixture
    async def setup_db(self):
        """Setup test database"""
        settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
        db = Database(settings=settings)
        await db.init()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_create_and_query_session(self, setup_db):
        """Test creating and querying session"""
        db = setup_db
        async with db.session() as session:
            new_session = Session(
                id="test-123",
                user_id="user-001",
                agent_id="agent-001",
                status=SessionStatus.ACTIVE,
            )
            session.add(new_session)
            await session.commit()

            # Query
            from sqlalchemy import select
            result = await session.execute(
                select(Session).where(Session.id == "test-123")
            )
            retrieved = result.scalar_one()
            assert retrieved.id == "test-123"
            assert retrieved.status == SessionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_message(self, setup_db):
        """Test creating message"""
        db = setup_db
        async with db.session() as session:
            # First create session
            test_session = Session(
                id="msg-test-123",
                user_id="user-001",
                agent_id="agent-001",
            )
            session.add(test_session)
            await session.commit()

            # Create message
            msg = Message(
                session_id="msg-test-123",
                role="user",
                content="Hello!",
            )
            session.add(msg)
            await session.commit()

            # Verify
            from sqlalchemy import select
            result = await session.execute(
                select(Message).where(Message.session_id == "msg-test-123")
            )
            messages = result.scalars().all()
            assert len(messages) == 1
            assert messages[0].content == "Hello!"

    @pytest.mark.asyncio
    async def test_create_memory(self, setup_db):
        """Test creating memory"""
        db = setup_db
        async with db.session() as session:
            # Create memory
            memory = Memory(
                user_id="user-001",
                memory_type=MemoryType.FACT,
                content="Important fact",
                importance=8,
            )
            session.add(memory)
            await session.commit()

            # Verify
            from sqlalchemy import select
            result = await session.execute(
                select(Memory).where(Memory.user_id == "user-001")
            )
            memories = result.scalars().all()
            assert len(memories) == 1
            assert memories[0].importance == 8

    @pytest.mark.asyncio
    async def test_create_tool_call(self, setup_db):
        """Test creating tool call"""
        db = setup_db
        async with db.session() as session:
            # Create session
            test_session = Session(
                id="tool-test-123",
                user_id="user-001",
                agent_id="agent-001",
            )
            session.add(test_session)
            await session.commit()

            # Create tool call - params must be JSON string
            tool_call = ToolCall(
                session_id="tool-test-123",
                tool_name="read_file",
                params='{"file_path": "/test.py"}',
            )
            session.add(tool_call)
            await session.commit()

            # Verify
            from sqlalchemy import select
            result = await session.execute(
                select(ToolCall).where(ToolCall.session_id == "tool-test-123")
            )
            calls = result.scalars().all()
            assert len(calls) == 1
            assert calls[0].tool_name == "read_file"

    @pytest.mark.asyncio
    async def test_create_user_config(self, setup_db):
        """Test creating user config"""
        db = setup_db
        async with db.session() as session:
            config = UserConfig(
                user_id="user-001",
                config_key="theme",
                config_value="dark",
            )
            session.add(config)
            await session.commit()

            # Verify
            from sqlalchemy import select
            result = await session.execute(
                select(UserConfig).where(UserConfig.user_id == "user-001")
            )
            configs = result.scalars().all()
            assert len(configs) == 1
            assert configs[0].config_value == "dark"

    @pytest.mark.asyncio
    async def test_update_session_status(self, setup_db):
        """Test updating session status"""
        db = setup_db
        async with db.session() as session:
            # Create session
            test_session = Session(
                id="status-test",
                user_id="user-001",
                agent_id="agent-001",
                status=SessionStatus.ACTIVE,
            )
            session.add(test_session)
            await session.commit()

            # Update status
            test_session.status = SessionStatus.COMPLETED
            await session.commit()

            # Verify
            from sqlalchemy import select
            result = await session.execute(
                select(Session).where(Session.id == "status-test")
            )
            retrieved = result.scalar_one()
            assert retrieved.status == SessionStatus.COMPLETED


class TestGlobalDatabaseFunctions:
    """Test Global Database Functions"""

    def test_get_database_returns_database(self):
        """Test get_database returns instance"""
        db = get_database()
        assert isinstance(db, Database)

    @pytest.mark.asyncio
    async def test_init_database(self):
        """Test init_database"""
        settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
        db = Database(settings=settings)
        await db.init()
        assert db._engine is not None
        await db.close()

    @pytest.mark.asyncio
    async def test_close_database(self):
        """Test close_database"""
        settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
        db = Database(settings=settings)
        await db.init()
        await db.close()


class TestModelIndexes:
    """Test Model Indexes"""

    def test_session_has_indexes(self):
        """Test session indexes"""
        assert hasattr(Session, '__table_args__')

    def test_message_has_indexes(self):
        """Test message indexes"""
        assert hasattr(Message, '__table_args__')

    def test_memory_has_indexes(self):
        """Test memory indexes"""
        assert hasattr(Memory, '__table_args__')

    def test_tool_call_has_indexes(self):
        """Test tool call indexes"""
        assert hasattr(ToolCall, '__table_args__')

    def test_user_config_has_indexes(self):
        """Test user config indexes"""
        assert hasattr(UserConfig, '__table_args__')
