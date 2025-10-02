# RAG Chatbot Test Suite

Comprehensive test suite for the RAG chatbot system, covering search tools, AI generation, vector storage, and end-to-end integration.

## Quick Start

### Run All Tests
```bash
cd backend
uv run python -m pytest tests/ -v
```

### Run Specific Test Files
```bash
# Search tool tests
uv run python -m pytest tests/test_search_tool.py -v

# AI generator tests
uv run python -m pytest tests/test_ai_generator.py -v

# Integration tests
uv run python -m pytest tests/test_rag_integration.py -v

# Vector store tests
uv run python -m pytest tests/test_vector_store.py -v
```

### Run Specific Tests
```bash
# Test the MAX_RESULTS configuration
uv run python -m pytest tests/test_vector_store.py::TestVectorStoreMaxResults -v

# Test tool execution flow
uv run python -m pytest tests/test_ai_generator.py::TestAIGenerator::test_tool_execution_flow -v
```

## Test Coverage

### 51 Total Tests

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_search_tool.py` | 18 | CourseSearchTool, CourseOutlineTool, ToolManager |
| `test_ai_generator.py` | 9 | AI tool calling, message construction, system prompts |
| `test_rag_integration.py` | 10 | End-to-end query flow, session management |
| `test_vector_store.py` | 14 | Vector search, MAX_RESULTS config, filters |

## Test Files

### `test_search_tool.py`
Tests for the search and outline tools that the AI uses.

**Coverage:**
- Tool definition format for Anthropic API
- Query execution with filters
- Result formatting and source tracking
- Error handling

**Key Tests:**
- `test_execute_with_valid_query` - Validates search execution
- `test_format_results_multiple_documents` - Tests result formatting
- `test_get_last_sources` - Validates source tracking for UI

### `test_ai_generator.py`
Tests for AI generation and tool calling functionality.

**Coverage:**
- Anthropic API integration
- Tool calling flow
- Message history construction
- System prompt validation

**Key Tests:**
- `test_tool_execution_flow` - Complete tool use cycle
- `test_handle_tool_execution_builds_messages_correctly` - Message structure
- `test_no_tools_in_final_request` - API call structure

### `test_rag_integration.py`
End-to-end integration tests for the complete RAG system.

**Coverage:**
- Query orchestration
- Tool manager integration
- Session management
- Source tracking and reset

**Key Tests:**
- `test_query_with_content_question` - Full query flow
- `test_realistic_tool_execution_flow` - Real tool execution
- `test_query_uses_conversation_history` - Context handling

### `test_vector_store.py`
Tests for vector storage and search functionality.

**Coverage:**
- MAX_RESULTS configuration (bug detection)
- Search with filters
- Course name resolution
- Error handling

**Key Tests:**
- `test_config_max_results_bug_scenario` - Validates MAX_RESULTS=5
- `test_search_with_max_results_0_returns_zero_results` - Proves bug behavior
- `test_search_with_course_name_filter` - Filter validation

## Shared Fixtures

### `conftest.py`
Provides reusable fixtures across all test files:

- `sample_course` - Example course structure
- `sample_course_chunks` - Example chunked content
- `sample_search_results` - Mock search results
- `sample_anthropic_response` - Mock API responses
- `mock_tool_definitions` - Tool schemas

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
collected 51 items

tests/test_ai_generator.py::TestAIGenerator ✅ 9 passed
tests/test_rag_integration.py::TestRAGSystemIntegration ✅ 10 passed
tests/test_search_tool.py::TestCourseSearchTool ✅ 18 passed
tests/test_vector_store.py::TestVectorStoreMaxResults ✅ 14 passed

============================== 51 passed in 0.08s ===============================
```

## Bug Discovery

The test suite identified and validated the fix for a critical bug:

**Bug:** `config.py` had `MAX_RESULTS = 0`, causing all searches to return zero results.

**Fix:** Changed to `MAX_RESULTS = 5`

**Validation:** Test `test_config_max_results_bug_scenario` now confirms MAX_RESULTS=5

See [`TEST_FINDINGS.md`](./TEST_FINDINGS.md) for detailed analysis.

## Writing New Tests

### Example Test Structure

```python
import pytest
from unittest.mock import Mock

class TestNewFeature:
    """Test description"""

    @pytest.fixture
    def mock_component(self):
        """Create mock for testing"""
        return Mock()

    def test_feature_behavior(self, mock_component):
        """Test specific behavior"""
        # Arrange
        mock_component.method.return_value = "expected"

        # Act
        result = mock_component.method()

        # Assert
        assert result == "expected"
```

### Using Shared Fixtures

```python
def test_with_sample_data(sample_course, sample_search_results):
    """Use fixtures from conftest.py"""
    assert sample_course.title == "Introduction to Python Programming"
    assert len(sample_search_results.documents) == 2
```

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    cd backend
    uv run python -m pytest tests/ -v --cov
```

## Maintenance

### Adding New Tests
1. Identify component to test
2. Create test class in appropriate file
3. Write fixtures if needed
4. Add tests with descriptive names
5. Run tests to verify

### Test Naming Convention
- Test files: `test_<component>.py`
- Test classes: `Test<Component>`
- Test methods: `test_<behavior>_<scenario>`

### Updating Tests
When modifying system behavior:
1. Update affected tests
2. Run full test suite
3. Verify all 51 tests pass
4. Update documentation

## Dependencies

Required packages (installed via uv):
- `pytest` - Testing framework
- `pytest-mock` - Mocking utilities

Automatically included in project dependencies.
