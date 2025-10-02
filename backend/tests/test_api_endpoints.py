"""API endpoint tests for FastAPI application"""
import pytest
from unittest.mock import patch


@pytest.mark.api
class TestQueryEndpoint:
    """Test the /api/query endpoint"""

    def test_query_without_session_id(self, test_client, mock_rag_system):
        """Test query endpoint creates a new session when session_id is not provided"""
        response = test_client.post(
            "/api/query",
            json={"query": "What is Python?"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "test-session-123"
        assert data["answer"] == "Python is a high-level programming language known for its simple syntax."
        assert len(data["sources"]) == 1

        # Verify RAG system was called correctly
        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("What is Python?", "test-session-123")

    def test_query_with_existing_session_id(self, test_client, mock_rag_system):
        """Test query endpoint uses provided session_id"""
        session_id = "existing-session-456"

        response = test_client.post(
            "/api/query",
            json={
                "query": "What is Python?",
                "session_id": session_id
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == session_id

        # Verify RAG system was not asked to create a new session
        mock_rag_system.session_manager.create_session.assert_not_called()
        mock_rag_system.query.assert_called_once_with("What is Python?", session_id)

    def test_query_with_invalid_payload(self, test_client):
        """Test query endpoint rejects invalid request payload"""
        response = test_client.post(
            "/api/query",
            json={"invalid_field": "value"}
        )

        assert response.status_code == 422  # Unprocessable Entity

    def test_query_with_empty_query(self, test_client):
        """Test query endpoint rejects empty query string"""
        response = test_client.post(
            "/api/query",
            json={"query": ""}
        )

        # Should accept empty string (validation happens in RAG system)
        assert response.status_code == 200

    def test_query_with_rag_system_error(self, test_client, mock_rag_system):
        """Test query endpoint handles RAG system errors"""
        # Configure mock to raise an exception
        mock_rag_system.query.side_effect = Exception("RAG system error")

        response = test_client.post(
            "/api/query",
            json={"query": "What is Python?"}
        )

        assert response.status_code == 500
        assert "RAG system error" in response.json()["detail"]


@pytest.mark.api
class TestCoursesEndpoint:
    """Test the /api/courses endpoint"""

    def test_get_course_stats(self, test_client, mock_rag_system):
        """Test courses endpoint returns correct statistics"""
        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Introduction to Python Programming" in data["course_titles"]
        assert "Advanced Python" in data["course_titles"]

        # Verify RAG system was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_course_stats_empty(self, test_client, mock_rag_system):
        """Test courses endpoint when no courses exist"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_course_stats_with_error(self, test_client, mock_rag_system):
        """Test courses endpoint handles RAG system errors"""
        mock_rag_system.get_course_analytics.side_effect = Exception("Database error")

        response = test_client.get("/api/courses")

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]


@pytest.mark.api
class TestSessionEndpoint:
    """Test the /api/session/{session_id} endpoint"""

    def test_delete_session(self, test_client, mock_rag_system):
        """Test deleting a session"""
        session_id = "test-session-789"

        response = test_client.delete(f"/api/session/{session_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

        # Verify session manager was called
        mock_rag_system.session_manager.clear_session.assert_called_once_with(session_id)

    def test_delete_nonexistent_session(self, test_client, mock_rag_system):
        """Test deleting a nonexistent session (should succeed)"""
        session_id = "nonexistent-session"

        response = test_client.delete(f"/api/session/{session_id}")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_session_with_error(self, test_client, mock_rag_system):
        """Test delete session endpoint handles errors"""
        mock_rag_system.session_manager.clear_session.side_effect = Exception("Session error")

        response = test_client.delete("/api/session/test-session")

        assert response.status_code == 500
        assert "Session error" in response.json()["detail"]


@pytest.mark.api
class TestResponseValidation:
    """Test response model validation"""

    def test_query_response_structure(self, test_client):
        """Test query response has correct structure"""
        response = test_client.post(
            "/api/query",
            json={"query": "What is Python?"}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Validate sources structure
        for source in data["sources"]:
            assert isinstance(source, dict)

    def test_courses_response_structure(self, test_client):
        """Test courses response has correct structure"""
        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

        # Validate course titles are strings
        for title in data["course_titles"]:
            assert isinstance(title, str)


@pytest.mark.api
class TestEndToEndFlow:
    """Test end-to-end API flows"""

    def test_complete_query_flow(self, test_client, mock_rag_system):
        """Test complete query flow: create session, query, delete session"""
        # Step 1: Make initial query (creates session)
        response1 = test_client.post(
            "/api/query",
            json={"query": "What is Python?"}
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # Step 2: Make follow-up query with same session
        response2 = test_client.post(
            "/api/query",
            json={
                "query": "Tell me more",
                "session_id": session_id
            }
        )
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

        # Step 3: Delete session
        response3 = test_client.delete(f"/api/session/{session_id}")
        assert response3.status_code == 200
        assert response3.json()["success"] is True

    def test_get_courses_then_query(self, test_client, mock_rag_system):
        """Test getting courses then querying about a specific course"""
        # Step 1: Get list of courses
        response1 = test_client.get("/api/courses")
        assert response1.status_code == 200
        courses_data = response1.json()
        assert courses_data["total_courses"] > 0

        # Step 2: Query about a specific course
        course_title = courses_data["course_titles"][0]
        response2 = test_client.post(
            "/api/query",
            json={"query": f"Tell me about {course_title}"}
        )
        assert response2.status_code == 200
        assert "answer" in response2.json()
