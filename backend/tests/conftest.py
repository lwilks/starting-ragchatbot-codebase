"""Shared pytest fixtures and configuration"""

import sys
from pathlib import Path

# Add backend directory to path so imports work
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from unittest.mock import MagicMock, Mock

from models import Course, CourseChunk, Lesson
from vector_store import SearchResults
from fastapi.testclient import TestClient


@pytest.fixture
def sample_course():
    """Create a sample course for testing"""
    return Course(
        title="Introduction to Python Programming",
        course_link="https://example.com/python-course",
        instructor="Jane Doe",
        lessons=[
            Lesson(
                lesson_number=1,
                title="Getting Started",
                lesson_link="https://example.com/python-course/lesson1",
            ),
            Lesson(
                lesson_number=2,
                title="Variables and Data Types",
                lesson_link="https://example.com/python-course/lesson2",
            ),
            Lesson(
                lesson_number=3,
                title="Control Flow",
                lesson_link="https://example.com/python-course/lesson3",
            ),
        ],
    )


@pytest.fixture
def sample_course_chunks():
    """Create sample course chunks for testing"""
    return [
        CourseChunk(
            content="Course Introduction to Python Programming Lesson 1 content: Python is a high-level programming language.",
            course_title="Introduction to Python Programming",
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="Python is known for its simple and readable syntax.",
            course_title="Introduction to Python Programming",
            lesson_number=1,
            chunk_index=1,
        ),
        CourseChunk(
            content="Course Introduction to Python Programming Lesson 2 content: Variables store data values.",
            course_title="Introduction to Python Programming",
            lesson_number=2,
            chunk_index=2,
        ),
    ]


@pytest.fixture
def sample_search_results():
    """Create sample search results for testing"""
    return SearchResults(
        documents=[
            "Python is a high-level programming language.",
            "Variables store data values.",
        ],
        metadata=[
            {
                "course_title": "Introduction to Python Programming",
                "lesson_number": 1,
                "chunk_index": 0,
            },
            {
                "course_title": "Introduction to Python Programming",
                "lesson_number": 2,
                "chunk_index": 2,
            },
        ],
        distances=[0.45, 0.52],
        error=None,
    )


@pytest.fixture
def sample_empty_results():
    """Create empty search results for testing"""
    return SearchResults(documents=[], metadata=[], distances=[], error=None)


@pytest.fixture
def sample_error_results():
    """Create error search results for testing"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error="No course found matching 'NonExistent Course'",
    )


@pytest.fixture
def mock_tool_definitions():
    """Sample tool definitions for testing"""
    return [
        {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content",
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work)",
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_course_outline",
            "description": "Get the complete outline of a course",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_name": {"type": "string", "description": "Course title"}
                },
                "required": ["course_name"],
            },
        },
    ]


@pytest.fixture
def sample_course_outline():
    """Sample course outline for testing"""
    return {
        "title": "Introduction to Python Programming",
        "course_link": "https://example.com/python-course",
        "instructor": "Jane Doe",
        "lessons": [
            {
                "lesson_number": 1,
                "lesson_title": "Getting Started",
                "lesson_link": "https://example.com/lesson1",
            },
            {
                "lesson_number": 2,
                "lesson_title": "Variables and Data Types",
                "lesson_link": "https://example.com/lesson2",
            },
            {
                "lesson_number": 3,
                "lesson_title": "Control Flow",
                "lesson_link": "https://example.com/lesson3",
            },
        ],
    }


@pytest.fixture
def sample_anthropic_response():
    """Sample Anthropic API response structure"""

    class MockTextBlock:
        def __init__(self, text):
            self.text = text
            self.type = "text"

    class MockToolUseBlock:
        def __init__(self, tool_id, name, input_data):
            self.id = tool_id
            self.name = name
            self.input = input_data
            self.type = "tool_use"

    class MockResponse:
        def __init__(self, content, stop_reason="end_turn"):
            self.content = content
            self.stop_reason = stop_reason

    return {
        "MockTextBlock": MockTextBlock,
        "MockToolUseBlock": MockToolUseBlock,
        "MockResponse": MockResponse,
    }


@pytest.fixture
def mock_rag_system():
    """Create a mock RAG system for API testing"""
    mock_system = MagicMock()
    mock_system.query.return_value = (
        "Python is a high-level programming language known for its simple syntax.",
        [{"course_title": "Introduction to Python Programming", "lesson_number": "1"}]
    )
    mock_system.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Introduction to Python Programming", "Advanced Python"]
    }
    mock_system.session_manager.create_session.return_value = "test-session-123"
    mock_system.session_manager.clear_session.return_value = None
    return mock_system


@pytest.fixture
def test_client(mock_rag_system):
    """Create a FastAPI test client with mocked RAG system"""
    from fastapi import FastAPI
    from pydantic import BaseModel
    from typing import List, Optional, Dict

    # Create a test app without static file mounting
    app = FastAPI(title="Course Materials RAG System - Test")

    # Pydantic models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Optional[str]]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # API endpoints using mock_rag_system
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        session_id = request.session_id or mock_rag_system.session_manager.create_session()
        answer, sources = mock_rag_system.query(request.query, session_id)
        return QueryResponse(answer=answer, sources=sources, session_id=session_id)

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        analytics = mock_rag_system.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"]
        )

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        mock_rag_system.session_manager.clear_session(session_id)
        return {"success": True}

    return TestClient(app)
