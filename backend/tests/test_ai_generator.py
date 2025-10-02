"""Tests for AIGenerator tool calling functionality"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from ai_generator import AIGenerator


class TestAIGenerator:
    """Test AIGenerator functionality"""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client"""
        with patch("ai_generator.anthropic.Anthropic") as mock:
            yield mock

    @pytest.fixture
    def ai_generator(self, mock_anthropic_client):
        """Create AIGenerator with mock client"""
        return AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")

    def test_initialization(self, ai_generator):
        """Test AIGenerator initializes with correct parameters"""
        assert ai_generator.model == "claude-sonnet-4-20250514"
        assert ai_generator.base_params["model"] == "claude-sonnet-4-20250514"
        assert ai_generator.base_params["temperature"] == 0
        assert ai_generator.base_params["max_tokens"] == 800

    def test_generate_response_without_tools(self, ai_generator):
        """Test generating response without tool usage"""
        # Mock the API response
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [Mock(text="This is a direct answer")]

        ai_generator.client.messages.create = Mock(return_value=mock_response)

        result = ai_generator.generate_response(
            query="What is 2+2?", conversation_history=None, tools=None
        )

        # Verify correct API call
        call_args = ai_generator.client.messages.create.call_args[1]
        assert call_args["model"] == "claude-sonnet-4-20250514"
        assert call_args["messages"][0]["content"] == "What is 2+2?"
        assert "tools" not in call_args

        # Verify response
        assert result == "This is a direct answer"

    def test_generate_response_with_conversation_history(self, ai_generator):
        """Test response generation includes conversation history in system prompt"""
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [Mock(text="Response with context")]

        ai_generator.client.messages.create = Mock(return_value=mock_response)

        history = "User: Previous question\nAssistant: Previous answer"

        result = ai_generator.generate_response(
            query="Follow-up question", conversation_history=history, tools=None
        )

        # Verify history is in system prompt
        call_args = ai_generator.client.messages.create.call_args[1]
        assert "Previous conversation:" in call_args["system"]
        assert history in call_args["system"]

    def test_generate_response_with_tools(self, ai_generator):
        """Test that tools are properly passed to API"""
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [Mock(text="Answer using tools")]

        ai_generator.client.messages.create = Mock(return_value=mock_response)

        tools = [
            {
                "name": "search_course_content",
                "description": "Search for content",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        result = ai_generator.generate_response(query="Search question", tools=tools)

        # Verify tools passed correctly
        call_args = ai_generator.client.messages.create.call_args[1]
        assert call_args["tools"] == tools
        assert call_args["tool_choice"] == {"type": "auto"}

    def test_tool_execution_flow(self, ai_generator):
        """Test complete tool execution flow"""
        # First response with tool use
        initial_response = Mock()
        initial_response.stop_reason = "tool_use"
        tool_use_block = Mock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tool_123"
        tool_use_block.name = "search_course_content"
        tool_use_block.input = {"query": "Python basics", "course_name": "Python 101"}
        initial_response.content = [tool_use_block]

        # Final response after tool execution
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [
            Mock(text="Based on the search results, Python is...")
        ]

        ai_generator.client.messages.create = Mock(
            side_effect=[initial_response, final_response]
        )

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = (
            "[Course: Python 101]\nPython is a programming language..."
        )

        tools = [{"name": "search_course_content"}]

        result = ai_generator.generate_response(
            query="What is Python?", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="Python basics", course_name="Python 101"
        )

        # Verify two API calls were made (tool use + natural completion)
        assert ai_generator.client.messages.create.call_count == 2

        # Verify final response
        assert result == "Based on the search results, Python is..."

    def test_sequential_tool_calls_two_rounds(self, ai_generator):
        """Test that Claude can make sequential tool calls across 2 rounds"""
        # Round 1: Tool use without text
        round1_response = Mock()
        round1_response.stop_reason = "tool_use"
        round1_response.content = [
            Mock(
                type="tool_use",
                id="t1",
                name="search_course_content",
                input={"query": "MCP"},
            )
        ]

        # Round 2: Another tool use
        round2_response = Mock()
        round2_response.stop_reason = "tool_use"
        round2_response.content = [
            Mock(
                type="tool_use",
                id="t2",
                name="search_course_content",
                input={"query": "MCP", "lesson_number": 2},
            )
        ]

        # Round 3: Final response (tools removed)
        round3_response = Mock()
        round3_response.stop_reason = "end_turn"
        round3_response.content = [Mock(type="text", text="Lesson 2 covers...")]

        ai_generator.client.messages.create = Mock(
            side_effect=[round1_response, round2_response, round3_response]
        )

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Found MCP course",
            "Lesson 2: Model Context Protocol implementation",
        ]

        result = ai_generator.generate_response(
            query="What's in lesson 2 of MCP?",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Verify: 3 API calls (round1, round2, final)
        assert ai_generator.client.messages.create.call_count == 3

        # Verify: 2 tool executions
        assert mock_tool_manager.execute_tool.call_count == 2

        # Verify: Final response returned
        assert result == "Lesson 2 covers..."

        # Verify: Message chain built correctly
        final_call = ai_generator.client.messages.create.call_args_list[2][1]
        messages = final_call["messages"]
        assert len(messages) == 5  # user → asst → user → asst → user
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"  # tool results
        assert messages[3]["role"] == "assistant"
        assert messages[4]["role"] == "user"  # tool results

    def test_max_rounds_enforced(self, ai_generator):
        """Test that system enforces maximum of 2 tool-calling rounds"""
        # Simulate Claude wanting 3 rounds (should be prevented)
        round1 = Mock(
            stop_reason="tool_use",
            content=[
                Mock(
                    type="tool_use",
                    id="t1",
                    name="search_course_content",
                    input={"query": "test1"},
                )
            ],
        )
        round2 = Mock(
            stop_reason="tool_use",
            content=[
                Mock(
                    type="tool_use",
                    id="t2",
                    name="search_course_content",
                    input={"query": "test2"},
                )
            ],
        )
        # Round 3 should have no tools available - forced to respond
        round3 = Mock(
            stop_reason="end_turn", content=[Mock(type="text", text="Final answer")]
        )

        ai_generator.client.messages.create = Mock(side_effect=[round1, round2, round3])

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Result"

        result = ai_generator.generate_response(
            query="Complex query",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Verify: Exactly 3 API calls (2 tool rounds + 1 final)
        assert ai_generator.client.messages.create.call_count == 3

        # Verify: Third call has NO tools parameter
        third_call = ai_generator.client.messages.create.call_args_list[2][1]
        assert "tools" not in third_call
        assert "tool_choice" not in third_call

    def test_natural_completion_after_first_tool(self, ai_generator):
        """Test Claude makes 1 tool call, then returns text without needing second"""
        # Round 1: Tool use
        round1_response = Mock()
        round1_response.stop_reason = "tool_use"
        round1_response.content = [
            Mock(
                type="tool_use",
                id="t1",
                name="search_course_content",
                input={"query": "test"},
            )
        ]

        # Round 2: Natural completion (no more tools)
        round2_response = Mock()
        round2_response.stop_reason = "end_turn"
        round2_response.content = [Mock(type="text", text="Here is the answer")]

        ai_generator.client.messages.create = Mock(
            side_effect=[round1_response, round2_response]
        )

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        result = ai_generator.generate_response(
            query="Simple query",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Verify: Only 2 API calls (no unnecessary third call)
        assert ai_generator.client.messages.create.call_count == 2

        # Verify: Only 1 tool execution
        assert mock_tool_manager.execute_tool.call_count == 1

        # Verify: Result returned
        assert result == "Here is the answer"

    def test_tools_available_in_both_rounds(self, ai_generator):
        """Verify tools are passed to API in round 1 and round 2"""
        round1 = Mock(
            stop_reason="tool_use",
            content=[
                Mock(type="tool_use", id="t1", name="search_course_content", input={})
            ],
        )
        round2 = Mock(
            stop_reason="tool_use",
            content=[
                Mock(type="tool_use", id="t2", name="search_course_content", input={})
            ],
        )
        round3 = Mock(stop_reason="end_turn", content=[Mock(type="text", text="Done")])

        ai_generator.client.messages.create = Mock(side_effect=[round1, round2, round3])
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Result"

        tools = [{"name": "search_course_content"}]

        ai_generator.generate_response(
            query="Test", tools=tools, tool_manager=mock_tool_manager
        )

        # Verify: First API call includes tools
        first_call = ai_generator.client.messages.create.call_args_list[0][1]
        assert first_call["tools"] == tools
        assert first_call["tool_choice"] == {"type": "auto"}

        # Verify: Second API call includes tools
        second_call = ai_generator.client.messages.create.call_args_list[1][1]
        assert second_call["tools"] == tools
        assert second_call["tool_choice"] == {"type": "auto"}

        # Verify: Final call excludes tools
        third_call = ai_generator.client.messages.create.call_args_list[2][1]
        assert "tools" not in third_call
        assert "tool_choice" not in third_call

    def test_context_preserved_across_rounds(self, ai_generator):
        """Test that message context accumulates correctly across rounds"""
        round1 = Mock(
            stop_reason="tool_use",
            content=[
                Mock(
                    type="tool_use",
                    id="t1",
                    name="search_course_content",
                    input={"query": "search1"},
                )
            ],
        )
        round2 = Mock(
            stop_reason="end_turn", content=[Mock(type="text", text="Answer")]
        )

        ai_generator.client.messages.create = Mock(side_effect=[round1, round2])

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        ai_generator.generate_response(
            query="Test query",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Check round 2 messages include full chain
        round2_call = ai_generator.client.messages.create.call_args_list[1][1]
        messages = round2_call["messages"]

        assert len(messages) == 3
        assert messages[0]["content"] == "Test query"
        assert messages[1]["content"] == round1.content
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"

    def test_tool_execution_error_handling(self, ai_generator):
        """Test graceful handling of tool execution errors"""
        round1 = Mock(
            stop_reason="tool_use",
            content=[
                Mock(type="tool_use", id="t1", name="search_course_content", input={})
            ],
        )
        round2 = Mock(
            stop_reason="end_turn",
            content=[Mock(type="text", text="I encountered an error with the search")],
        )

        ai_generator.client.messages.create = Mock(side_effect=[round1, round2])

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception(
            "Database connection failed"
        )

        result = ai_generator.generate_response(
            query="Test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Verify: Error was handled (didn't crash)
        assert result == "I encountered an error with the search"

        # Verify: Error message was passed to Claude
        round2_call = ai_generator.client.messages.create.call_args_list[1][1]
        tool_result = round2_call["messages"][2]["content"][0]
        assert tool_result["is_error"] == True
        assert "Database connection failed" in tool_result["content"]

    def test_system_prompt_content(self, ai_generator):
        """Test that system prompt contains correct instructions"""
        assert "search_course_content" in AIGenerator.SYSTEM_PROMPT
        assert "get_course_outline" in AIGenerator.SYSTEM_PROMPT
        assert "Sequential tool calling" in AIGenerator.SYSTEM_PROMPT
        assert "up to 2 sequential tool calls" in AIGenerator.SYSTEM_PROMPT
        assert "Brief, Concise and focused" in AIGenerator.SYSTEM_PROMPT
