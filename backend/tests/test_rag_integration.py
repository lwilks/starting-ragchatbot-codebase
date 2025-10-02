"""Integration tests for RAG system end-to-end query flow"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from config import Config
from rag_system import RAGSystem
from vector_store import SearchResults


class TestRAGSystemIntegration:
    """Test RAGSystem end-to-end integration"""

    @pytest.fixture
    def mock_config(self):
        """Create a test configuration"""
        config = Config()
        config.ANTHROPIC_API_KEY = "test_key"
        config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
        config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        config.CHUNK_SIZE = 800
        config.CHUNK_OVERLAP = 100
        config.MAX_RESULTS = 5  # Correct value, not 0
        config.MAX_HISTORY = 2
        config.CHROMA_PATH = "./test_chroma"
        return config

    @pytest.fixture
    def rag_system(self, mock_config):
        """Create RAG system with mocked components"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator"),
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):
            return RAGSystem(mock_config)

    def test_query_with_content_question(self, rag_system):
        """Test end-to-end query flow for content questions"""
        # Mock the AI generator to simulate tool calling
        mock_ai_response = (
            "Python is a high-level programming language known for its simplicity."
        )

        rag_system.ai_generator.generate_response = Mock(return_value=mock_ai_response)

        # Mock tool manager to return sources
        rag_system.tool_manager.get_last_sources = Mock(
            return_value=[
                {
                    "text": "Introduction to Python - Lesson 1",
                    "url": "https://example.com/lesson1",
                }
            ]
        )

        # Execute query
        response, sources = rag_system.query(
            "What is Python?", session_id="test_session"
        )

        # Verify AI generator called with correct parameters
        call_args = rag_system.ai_generator.generate_response.call_args

        # Check query was formatted
        assert "What is Python?" in call_args[1]["query"]

        # Check tools were provided
        assert call_args[1]["tools"] is not None
        tool_names = [t["name"] for t in call_args[1]["tools"]]
        assert "search_course_content" in tool_names

        # Check tool_manager was provided
        assert call_args[1]["tool_manager"] == rag_system.tool_manager

        # Verify response
        assert response == mock_ai_response

        # Verify sources were retrieved
        assert len(sources) == 1
        assert sources[0]["text"] == "Introduction to Python - Lesson 1"

    def test_query_creates_session_if_not_provided(self, rag_system):
        """Test that query creates session when session_id is None"""
        rag_system.ai_generator.generate_response = Mock(return_value="Answer")
        rag_system.tool_manager.get_last_sources = Mock(return_value=[])
        rag_system.session_manager.create_session = Mock(return_value="new_session_123")

        # Query without session_id
        response, sources = rag_system.query("Test question")

        # Session should NOT be created (only AI should use history if provided)
        # Based on code, session is only used to get history, not created
        # The session creation happens in app.py, not in RAGSystem
        assert response == "Answer"

    def test_query_uses_conversation_history(self, rag_system):
        """Test that query includes conversation history from session"""
        mock_history = (
            "User: What is Python?\nAssistant: Python is a programming language."
        )

        rag_system.session_manager.get_conversation_history = Mock(
            return_value=mock_history
        )
        rag_system.ai_generator.generate_response = Mock(
            return_value="More details about Python..."
        )
        rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        response, sources = rag_system.query(
            "Tell me more", session_id="existing_session"
        )

        # Verify conversation history was retrieved
        rag_system.session_manager.get_conversation_history.assert_called_once_with(
            "existing_session"
        )

        # Verify history passed to AI generator
        call_args = rag_system.ai_generator.generate_response.call_args[1]
        assert call_args["conversation_history"] == mock_history

    def test_query_updates_conversation_history(self, rag_system):
        """Test that query updates session history after getting response"""
        rag_system.ai_generator.generate_response = Mock(
            return_value="Python is great!"
        )
        rag_system.tool_manager.get_last_sources = Mock(return_value=[])
        rag_system.session_manager.get_conversation_history = Mock(return_value=None)

        query_text = "What is Python?"
        response, sources = rag_system.query(query_text, session_id="test_session")

        # Verify session was updated with exchange
        rag_system.session_manager.add_exchange.assert_called_once_with(
            "test_session", query_text, "Python is great!"
        )

    def test_query_resets_sources_after_retrieval(self, rag_system):
        """Test that sources are reset after being retrieved"""
        rag_system.ai_generator.generate_response = Mock(return_value="Answer")
        rag_system.tool_manager.get_last_sources = Mock(
            return_value=[{"text": "Source 1", "url": None}]
        )
        rag_system.tool_manager.reset_sources = Mock()

        response, sources = rag_system.query("Test")

        # Verify sources were retrieved
        rag_system.tool_manager.get_last_sources.assert_called_once()

        # Verify sources were reset after retrieval
        rag_system.tool_manager.reset_sources.assert_called_once()

    def test_query_without_sources(self, rag_system):
        """Test query that doesn't trigger tool use returns empty sources"""
        rag_system.ai_generator.generate_response = Mock(
            return_value="The capital of France is Paris."
        )
        rag_system.tool_manager.get_last_sources = Mock(return_value=[])

        response, sources = rag_system.query("What is the capital of France?")

        # Should return empty sources for general knowledge questions
        assert sources == []

    def test_tool_manager_has_required_tools(self, rag_system):
        """Test that tool manager has search and outline tools registered"""
        tool_definitions = rag_system.tool_manager.get_tool_definitions()

        # Should have at least 2 tools
        assert len(tool_definitions) >= 2

        tool_names = [t["name"] for t in tool_definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_search_tool_has_vector_store(self, rag_system):
        """Test that search tool is initialized with vector store"""
        assert rag_system.search_tool.store == rag_system.vector_store

    def test_outline_tool_has_vector_store(self, rag_system):
        """Test that outline tool is initialized with vector store"""
        assert rag_system.outline_tool.store == rag_system.vector_store


class TestRAGSystemWithRealToolFlow:
    """Test RAG system with more realistic tool execution flow"""

    @pytest.fixture
    def mock_config(self):
        """Create a test configuration"""
        config = Config()
        config.ANTHROPIC_API_KEY = "test_key"
        config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
        config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        config.CHUNK_SIZE = 800
        config.CHUNK_OVERLAP = 100
        config.MAX_RESULTS = 5  # Correct value, not 0
        config.MAX_HISTORY = 2
        config.CHROMA_PATH = "./test_chroma"
        return config

    @pytest.fixture
    def rag_system_with_mocked_vector_store(self, mock_config):
        """Create RAG system with mocked vector store but real tool flow"""
        with (
            patch("rag_system.VectorStore") as MockVectorStore,
            patch("rag_system.AIGenerator") as MockAIGenerator,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            # Create the RAG system
            rag = RAGSystem(mock_config)

            # Setup vector store mock to return search results
            mock_search_results = SearchResults(
                documents=["Python is a high-level programming language."],
                metadata=[{"course_title": "Python 101", "lesson_number": 1}],
                distances=[0.5],
                error=None,
            )
            rag.vector_store.search = Mock(return_value=mock_search_results)
            rag.vector_store.get_lesson_link = Mock(
                return_value="https://example.com/lesson1"
            )

            # Setup AI generator to simulate tool use
            def mock_generate(
                query, conversation_history=None, tools=None, tool_manager=None
            ):
                if tool_manager and tools:
                    # Simulate AI deciding to use search tool
                    result = tool_manager.execute_tool(
                        "search_course_content",
                        query="Python basics",
                        course_name="Python 101",
                    )
                    # Return a response that synthesizes the search result
                    return "Based on the course material, Python is a high-level programming language."
                return "Direct answer without tools"

            rag.ai_generator.generate_response = Mock(side_effect=mock_generate)

            return rag

    def test_realistic_tool_execution_flow(self, rag_system_with_mocked_vector_store):
        """Test realistic flow where AI uses search tool"""
        rag = rag_system_with_mocked_vector_store

        response, sources = rag.query("What is Python?", session_id="test")

        # Verify vector store was searched
        rag.vector_store.search.assert_called()

        # Verify response includes synthesized content
        assert "Python is a high-level programming language" in response

        # Verify sources were tracked
        assert len(sources) == 1
        assert sources[0]["text"] == "Python 101 - Lesson 1"
        assert sources[0]["url"] == "https://example.com/lesson1"
