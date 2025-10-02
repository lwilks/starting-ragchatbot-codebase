"""Tests for CourseSearchTool and CourseOutlineTool"""

from unittest.mock import MagicMock, Mock

import pytest
from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test CourseSearchTool functionality"""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store"""
        return Mock()

    @pytest.fixture
    def search_tool(self, mock_vector_store):
        """Create CourseSearchTool with mock vector store"""
        return CourseSearchTool(mock_vector_store)

    def test_get_tool_definition(self, search_tool):
        """Test that tool definition is properly formatted for Anthropic API"""
        definition = search_tool.get_tool_definition()

        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"
        assert "query" in definition["input_schema"]["properties"]
        assert definition["input_schema"]["required"] == ["query"]

    def test_execute_with_valid_query(self, search_tool, mock_vector_store):
        """Test execute returns formatted results for valid query"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=["This is course content about Python"],
            metadata=[{"course_title": "Introduction to Python", "lesson_number": 1}],
            distances=[0.5],
            error=None,
        )
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson1"

        result = search_tool.execute(query="What is Python?")

        # Verify search was called correctly
        mock_vector_store.search.assert_called_once_with(
            query="What is Python?", course_name=None, lesson_number=None
        )

        # Verify result formatting
        assert "[Introduction to Python - Lesson 1]" in result
        assert "This is course content about Python" in result

        # Verify sources were tracked
        assert len(search_tool.last_sources) == 1
        assert (
            search_tool.last_sources[0]["text"] == "Introduction to Python - Lesson 1"
        )
        assert search_tool.last_sources[0]["url"] == "https://example.com/lesson1"

    def test_execute_with_course_filter(self, search_tool, mock_vector_store):
        """Test execute passes course_name filter to vector store"""
        mock_results = SearchResults(
            documents=["Filtered content"],
            metadata=[{"course_title": "Advanced Python", "lesson_number": 2}],
            distances=[0.3],
            error=None,
        )
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = None

        result = search_tool.execute(query="decorators", course_name="Advanced Python")

        mock_vector_store.search.assert_called_once_with(
            query="decorators", course_name="Advanced Python", lesson_number=None
        )
        assert "Filtered content" in result

    def test_execute_with_lesson_filter(self, search_tool, mock_vector_store):
        """Test execute passes lesson_number filter to vector store"""
        mock_results = SearchResults(
            documents=["Lesson specific content"],
            metadata=[{"course_title": "Python Basics", "lesson_number": 5}],
            distances=[0.2],
            error=None,
        )
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson5"

        result = search_tool.execute(query="loops", lesson_number=5)

        mock_vector_store.search.assert_called_once_with(
            query="loops", course_name=None, lesson_number=5
        )
        assert "Lesson specific content" in result

    def test_execute_handles_search_error(self, search_tool, mock_vector_store):
        """Test execute returns error message when search fails"""
        mock_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="No course found matching 'NonExistent'",
        )
        mock_vector_store.search.return_value = mock_results

        result = search_tool.execute(query="test", course_name="NonExistent")

        assert result == "No course found matching 'NonExistent'"

    def test_execute_handles_empty_results(self, search_tool, mock_vector_store):
        """Test execute returns appropriate message for empty results"""
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        mock_vector_store.search.return_value = mock_results

        result = search_tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_empty_results_with_filters(self, search_tool, mock_vector_store):
        """Test empty results message includes filter information"""
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        mock_vector_store.search.return_value = mock_results

        result = search_tool.execute(
            query="test", course_name="Python Course", lesson_number=3
        )

        assert "No relevant content found" in result
        assert "Python Course" in result
        assert "lesson 3" in result

    def test_format_results_multiple_documents(self, search_tool, mock_vector_store):
        """Test formatting multiple search results"""
        mock_results = SearchResults(
            documents=["First document content", "Second document content"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
            distances=[0.5, 0.6],
            error=None,
        )
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = None

        result = search_tool.execute(query="test")

        # Check both results are formatted
        assert "[Course A - Lesson 1]" in result
        assert "First document content" in result
        assert "[Course B - Lesson 2]" in result
        assert "Second document content" in result

        # Check sources tracked correctly
        assert len(search_tool.last_sources) == 2

    def test_sources_without_lesson_number(self, search_tool, mock_vector_store):
        """Test source formatting when lesson_number is None"""
        mock_results = SearchResults(
            documents=["Content without lesson"],
            metadata=[{"course_title": "General Course", "lesson_number": None}],
            distances=[0.4],
            error=None,
        )
        mock_vector_store.search.return_value = mock_results
        mock_vector_store.get_lesson_link.return_value = None

        result = search_tool.execute(query="test")

        # Should not include "Lesson" in header when lesson_number is None
        assert "[General Course]" in result
        assert "Content without lesson" in result

        # Source should not have lesson info
        assert search_tool.last_sources[0]["text"] == "General Course"
        assert search_tool.last_sources[0]["url"] is None


class TestCourseOutlineTool:
    """Test CourseOutlineTool functionality"""

    @pytest.fixture
    def mock_vector_store(self):
        return Mock()

    @pytest.fixture
    def outline_tool(self, mock_vector_store):
        return CourseOutlineTool(mock_vector_store)

    def test_get_tool_definition(self, outline_tool):
        """Test outline tool definition"""
        definition = outline_tool.get_tool_definition()

        assert definition["name"] == "get_course_outline"
        assert "description" in definition
        assert "course_name" in definition["input_schema"]["properties"]
        assert definition["input_schema"]["required"] == ["course_name"]

    def test_execute_returns_formatted_outline(self, outline_tool, mock_vector_store):
        """Test execute returns properly formatted course outline"""
        mock_vector_store._resolve_course_name.return_value = "Python 101"
        mock_vector_store.get_course_outline.return_value = {
            "title": "Python 101",
            "course_link": "https://example.com/python101",
            "instructor": "John Doe",
            "lessons": [
                {"lesson_number": 1, "lesson_title": "Introduction"},
                {"lesson_number": 2, "lesson_title": "Variables"},
            ],
        }

        result = outline_tool.execute(course_name="Python")

        assert "Course: Python 101" in result
        assert "Link: https://example.com/python101" in result
        assert "Instructor: John Doe" in result
        assert "1. Introduction" in result
        assert "2. Variables" in result

    def test_execute_course_not_found(self, outline_tool, mock_vector_store):
        """Test execute handles course not found"""
        mock_vector_store._resolve_course_name.return_value = None

        result = outline_tool.execute(course_name="NonExistent")

        assert "No course found matching 'NonExistent'" in result


class TestToolManager:
    """Test ToolManager functionality"""

    def test_register_tool(self):
        """Test registering a tool"""
        manager = ToolManager()
        mock_tool = Mock()
        mock_tool.get_tool_definition.return_value = {
            "name": "test_tool",
            "description": "A test tool",
        }

        manager.register_tool(mock_tool)

        assert "test_tool" in manager.tools

    def test_get_tool_definitions(self):
        """Test getting all tool definitions"""
        manager = ToolManager()

        mock_tool1 = Mock()
        mock_tool1.get_tool_definition.return_value = {"name": "tool1"}

        mock_tool2 = Mock()
        mock_tool2.get_tool_definition.return_value = {"name": "tool2"}

        manager.register_tool(mock_tool1)
        manager.register_tool(mock_tool2)

        definitions = manager.get_tool_definitions()

        assert len(definitions) == 2
        assert {"name": "tool1"} in definitions
        assert {"name": "tool2"} in definitions

    def test_execute_tool(self):
        """Test executing a registered tool"""
        manager = ToolManager()

        mock_tool = Mock()
        mock_tool.get_tool_definition.return_value = {"name": "search_tool"}
        mock_tool.execute.return_value = "Search results"

        manager.register_tool(mock_tool)

        result = manager.execute_tool("search_tool", query="test", course_name="Python")

        mock_tool.execute.assert_called_once_with(query="test", course_name="Python")
        assert result == "Search results"

    def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist"""
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool")

        assert "Tool 'nonexistent_tool' not found" in result

    def test_get_last_sources(self):
        """Test retrieving last sources from tools"""
        manager = ToolManager()

        mock_tool = Mock()
        mock_tool.get_tool_definition.return_value = {"name": "search_tool"}
        mock_tool.last_sources = [{"text": "Source 1", "url": "https://example.com/1"}]

        manager.register_tool(mock_tool)

        sources = manager.get_last_sources()

        assert len(sources) == 1
        assert sources[0]["text"] == "Source 1"

    def test_reset_sources(self):
        """Test resetting sources on all tools"""
        manager = ToolManager()

        mock_tool = Mock()
        mock_tool.get_tool_definition.return_value = {"name": "search_tool"}
        mock_tool.last_sources = [{"text": "Source 1"}]

        manager.register_tool(mock_tool)
        manager.reset_sources()

        assert mock_tool.last_sources == []
