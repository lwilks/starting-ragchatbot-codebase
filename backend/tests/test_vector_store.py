"""Tests for VectorStore with focus on MAX_RESULTS bug"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from vector_store import VectorStore, SearchResults


class TestVectorStoreMaxResults:
    """Test VectorStore MAX_RESULTS behavior - focuses on the critical bug"""

    @pytest.fixture
    def mock_chroma_client(self):
        """Create mock ChromaDB client"""
        with patch('vector_store.chromadb.PersistentClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            # Mock collections
            mock_catalog = Mock()
            mock_content = Mock()

            mock_instance.get_or_create_collection.side_effect = [
                mock_catalog,
                mock_content
            ]

            yield {
                'client': mock_instance,
                'catalog': mock_catalog,
                'content': mock_content
            }

    @pytest.fixture
    def vector_store_with_max_5(self, mock_chroma_client):
        """Create vector store with MAX_RESULTS=5 (correct value)"""
        with patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):
            store = VectorStore(
                chroma_path="./test_db",
                embedding_model="all-MiniLM-L6-v2",
                max_results=5
            )
            store.course_catalog = mock_chroma_client['catalog']
            store.course_content = mock_chroma_client['content']
            return store

    @pytest.fixture
    def vector_store_with_max_0(self, mock_chroma_client):
        """Create vector store with MAX_RESULTS=0 (bug scenario)"""
        with patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):
            store = VectorStore(
                chroma_path="./test_db",
                embedding_model="all-MiniLM-L6-v2",
                max_results=0  # THE BUG!
            )
            store.course_catalog = mock_chroma_client['catalog']
            store.course_content = mock_chroma_client['content']
            return store

    def test_search_with_max_results_5_returns_results(self, vector_store_with_max_5):
        """Test that search with MAX_RESULTS=5 returns results"""
        # Mock ChromaDB query response
        vector_store_with_max_5.course_content.query.return_value = {
            'documents': [['Result 1', 'Result 2', 'Result 3']],
            'metadatas': [[
                {'course_title': 'Python 101', 'lesson_number': 1},
                {'course_title': 'Python 101', 'lesson_number': 2},
                {'course_title': 'Python 101', 'lesson_number': 3}
            ]],
            'distances': [[0.5, 0.6, 0.7]]
        }

        results = vector_store_with_max_5.search(query="Python basics")

        # Verify ChromaDB was called with n_results=5
        vector_store_with_max_5.course_content.query.assert_called_once()
        call_args = vector_store_with_max_5.course_content.query.call_args[1]
        assert call_args['n_results'] == 5

        # Verify results returned
        assert len(results.documents) == 3
        assert results.documents[0] == 'Result 1'

    def test_search_with_max_results_0_returns_zero_results(self, vector_store_with_max_0):
        """Test THE BUG: search with MAX_RESULTS=0 returns empty results"""
        # Mock ChromaDB to return empty results (as it would with n_results=0)
        vector_store_with_max_0.course_content.query.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        results = vector_store_with_max_0.search(query="Python basics")

        # Verify ChromaDB was called with n_results=0 (THE BUG!)
        vector_store_with_max_0.course_content.query.assert_called_once()
        call_args = vector_store_with_max_0.course_content.query.call_args[1]
        assert call_args['n_results'] == 0  # This is the problem!

        # Verify empty results
        assert results.is_empty()
        assert len(results.documents) == 0

    def test_config_max_results_bug_scenario(self):
        """Test that config MAX_RESULTS is now fixed (should be 5, not 0)"""
        from config import Config

        test_config = Config()
        # The fix: MAX_RESULTS should be 5 in config.py:23
        assert test_config.MAX_RESULTS == 5, "MAX_RESULTS should be 5 (bug was 0)"

        # When RAGSystem uses this config, it creates VectorStore with max_results=5
        # This allows searches to return results
        with patch('vector_store.chromadb.PersistentClient'), \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

            fixed_store = VectorStore(
                chroma_path="./test",
                embedding_model="test",
                max_results=test_config.MAX_RESULTS  # 5!
            )

            assert fixed_store.max_results == 5
            # Searches will now request 5 results, fixing the issue


class TestVectorStoreSearch:
    """Test VectorStore search functionality"""

    @pytest.fixture
    def mock_vector_store(self):
        """Create vector store with mocked ChromaDB"""
        with patch('vector_store.chromadb.PersistentClient'), \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

            store = VectorStore(
                chroma_path="./test_db",
                embedding_model="test-model",
                max_results=5
            )

            # Mock the collections
            store.course_catalog = Mock()
            store.course_content = Mock()

            return store

    def test_search_without_filters(self, mock_vector_store):
        """Test basic search without course or lesson filters"""
        mock_vector_store.course_content.query.return_value = {
            'documents': [['Content about Python']],
            'metadatas': [[{'course_title': 'Python 101', 'lesson_number': 1}]],
            'distances': [[0.5]]
        }

        results = mock_vector_store.search(query="What is Python?")

        # Verify search parameters
        call_args = mock_vector_store.course_content.query.call_args[1]
        assert call_args['query_texts'] == ["What is Python?"]
        assert call_args['n_results'] == 5
        assert call_args['where'] is None  # No filter

        # Verify results
        assert not results.is_empty()
        assert len(results.documents) == 1

    def test_search_with_course_name_filter(self, mock_vector_store):
        """Test search with course name filter"""
        # Mock course resolution
        mock_vector_store.course_catalog.query.return_value = {
            'documents': [['Python 101']],
            'metadatas': [[{'title': 'Python 101'}]],
            'distances': [[0.1]]
        }

        # Mock content search
        mock_vector_store.course_content.query.return_value = {
            'documents': [['Filtered content']],
            'metadatas': [[{'course_title': 'Python 101', 'lesson_number': 1}]],
            'distances': [[0.3]]
        }

        results = mock_vector_store.search(
            query="decorators",
            course_name="Python"
        )

        # Verify course resolution was attempted
        mock_vector_store.course_catalog.query.assert_called_once()

        # Verify filter was applied
        call_args = mock_vector_store.course_content.query.call_args[1]
        assert call_args['where'] == {'course_title': 'Python 101'}

    def test_search_with_lesson_number_filter(self, mock_vector_store):
        """Test search with lesson number filter"""
        mock_vector_store.course_content.query.return_value = {
            'documents': [['Lesson 5 content']],
            'metadatas': [[{'course_title': 'Python 101', 'lesson_number': 5}]],
            'distances': [[0.2]]
        }

        results = mock_vector_store.search(
            query="loops",
            lesson_number=5
        )

        # Verify lesson filter
        call_args = mock_vector_store.course_content.query.call_args[1]
        assert call_args['where'] == {'lesson_number': 5}

    def test_search_with_both_filters(self, mock_vector_store):
        """Test search with both course and lesson filters"""
        # Mock course resolution
        mock_vector_store.course_catalog.query.return_value = {
            'documents': [['Advanced Python']],
            'metadatas': [[{'title': 'Advanced Python'}]],
            'distances': [[0.1]]
        }

        # Mock content search
        mock_vector_store.course_content.query.return_value = {
            'documents': [['Specific content']],
            'metadatas': [[{'course_title': 'Advanced Python', 'lesson_number': 3}]],
            'distances': [[0.25]]
        }

        results = mock_vector_store.search(
            query="async/await",
            course_name="Advanced",
            lesson_number=3
        )

        # Verify AND filter
        call_args = mock_vector_store.course_content.query.call_args[1]
        expected_filter = {
            '$and': [
                {'course_title': 'Advanced Python'},
                {'lesson_number': 3}
            ]
        }
        assert call_args['where'] == expected_filter

    def test_search_course_not_found(self, mock_vector_store):
        """Test search when course name doesn't match any course"""
        # Mock empty course resolution
        mock_vector_store.course_catalog.query.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        results = mock_vector_store.search(
            query="test",
            course_name="NonExistentCourse"
        )

        # Should return error
        assert results.error is not None
        assert "No course found matching 'NonExistentCourse'" in results.error

    def test_search_with_custom_limit(self, mock_vector_store):
        """Test search with custom result limit"""
        mock_vector_store.course_content.query.return_value = {
            'documents': [['Result 1', 'Result 2']],
            'metadatas': [[
                {'course_title': 'Test', 'lesson_number': 1},
                {'course_title': 'Test', 'lesson_number': 2}
            ]],
            'distances': [[0.5, 0.6]]
        }

        results = mock_vector_store.search(query="test", limit=3)

        # Verify custom limit used
        call_args = mock_vector_store.course_content.query.call_args[1]
        assert call_args['n_results'] == 3

    def test_search_handles_exception(self, mock_vector_store):
        """Test search handles ChromaDB exceptions"""
        mock_vector_store.course_content.query.side_effect = Exception("Database error")

        results = mock_vector_store.search(query="test")

        # Should return error result
        assert results.error is not None
        assert "Search error" in results.error


class TestSearchResults:
    """Test SearchResults dataclass"""

    def test_from_chroma_with_results(self):
        """Test creating SearchResults from ChromaDB response"""
        chroma_results = {
            'documents': [['Doc 1', 'Doc 2']],
            'metadatas': [[{'key': 'val1'}, {'key': 'val2'}]],
            'distances': [[0.5, 0.6]]
        }

        results = SearchResults.from_chroma(chroma_results)

        assert results.documents == ['Doc 1', 'Doc 2']
        assert results.metadata == [{'key': 'val1'}, {'key': 'val2'}]
        assert results.distances == [0.5, 0.6]
        assert results.error is None

    def test_from_chroma_empty(self):
        """Test creating SearchResults from empty ChromaDB response"""
        chroma_results = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        results = SearchResults.from_chroma(chroma_results)

        assert results.is_empty()

    def test_empty_with_error(self):
        """Test creating empty results with error message"""
        results = SearchResults.empty("Course not found")

        assert results.is_empty()
        assert results.error == "Course not found"
        assert len(results.documents) == 0

    def test_is_empty(self):
        """Test is_empty method"""
        empty_results = SearchResults([], [], [], None)
        assert empty_results.is_empty()

        non_empty_results = SearchResults(['doc'], [{}], [0.5], None)
        assert not non_empty_results.is_empty()
