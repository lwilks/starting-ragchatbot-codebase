import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Tool Usage:
- **search_course_content**: Use for questions about specific course content or detailed educational materials
- **get_course_outline**: Use for questions about course structure, lesson lists, or course outlines
- **Sequential tool calling**: You can make up to 2 sequential tool calls across separate rounds to gather information
  - First round: Initial search or data gathering based on the query
  - Second round (optional): Follow-up search based on first results, different filters, or additional context needed
  - Use sequential calls for comparisons, multi-part questions, or when information from different courses/lessons is needed
- **Strategic tool use**:
  - Use first call to get broad context or initial information
  - Use second call (if needed) to refine search, get specific details, or gather complementary information
  - Don't repeat identical searches - each call should add value
- Synthesize tool results into accurate, fact-based responses
- If tool yields no results, state this clearly without offering alternatives

Outline Query Requirements:
When responding to outline-related queries, you MUST include:
- Course title
- Course link
- Complete list of lessons with their numbers and titles

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Use search_course_content tool first, then answer
- **Course outline questions**: Use get_course_outline tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the outline"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional multi-round tool usage and conversation context.

        Supports up to 2 sequential tool calling rounds where Claude can:
        - Round 1: Make initial tool call(s) based on query
        - Round 2: Make additional tool call(s) based on results from Round 1

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize message history
        messages = [{"role": "user", "content": query}]

        # Sequential tool calling loop (max 2 rounds)
        MAX_ROUNDS = 2
        for round_num in range(1, MAX_ROUNDS + 1):
            # Make API call with tools
            response = self._make_api_call(messages, tools, system_content)

            # Termination: Natural completion (no tool use)
            if response.stop_reason != "tool_use":
                return response.content[0].text

            # Termination: No tool manager (shouldn't happen, but safe)
            if not tool_manager:
                return response.content[0].text

            # Process tool round - updates messages in place
            messages = self._process_tool_round(response, messages, tool_manager)

            # Check if any tool had an error
            if messages and messages[-1]["role"] == "user":
                for result in messages[-1].get("content", []):
                    if isinstance(result, dict) and result.get("is_error"):
                        # Termination: Tool execution error
                        # Make one final call to let Claude respond with error context
                        final_response = self._make_api_call(messages, None, system_content)
                        return final_response.content[0].text

            # Termination: Max rounds reached
            if round_num == MAX_ROUNDS:
                # Force final response without tools
                final_response = self._make_api_call(messages, None, system_content)
                return final_response.content[0].text

        # Should never reach here due to explicit max rounds check
        return "Error: Unexpected flow termination"
    
    def _make_api_call(self, messages: List[Dict], tools: Optional[List] = None,
                      system_content: str = ""):
        """
        Make API call to Claude with given messages and optional tools.

        Args:
            messages: Conversation message history
            tools: Optional tool definitions
            system_content: System prompt content

        Returns:
            Claude API response
        """
        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        return self.client.messages.create(**api_params)

    def _process_tool_round(self, response, messages: List[Dict], tool_manager) -> List[Dict]:
        """
        Process one round of tool execution and update message history.

        Args:
            response: API response containing tool_use blocks
            messages: Current message history
            tool_manager: Tool executor

        Returns:
            Updated message history with assistant response and tool results
        """
        # Add assistant's tool use response to messages
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        # Execute all tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    result = tool_manager.execute_tool(block.name, **block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
                except Exception as e:
                    # Handle tool execution errors gracefully
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error executing tool: {str(e)}",
                        "is_error": True
                    })

        # Add tool results to messages
        if tool_results:
            messages.append({
                "role": "user",
                "content": tool_results
            })

        return messages