# RAG Chatbot Query Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  FRONTEND                                    │
│                           (frontend/script.js)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                   User types: "What is lesson 1 about?"
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │  sendMessage() (L45)   │
                         │  - Disable input       │
                         │  - Show loading        │
                         └────────────────────────┘
                                      │
                                      │ POST /api/query
                                      │ { query: "...", session_id: "..." }
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI ENDPOINT                                │
│                              (backend/app.py)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                         ┌────────────────────────┐
                         │ /api/query (L56-74)    │
                         │ - Validate request     │
                         │ - Create session_id    │
                         │   if needed            │
                         └────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               RAG ORCHESTRATOR                               │
│                           (backend/rag_system.py)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                         ┌────────────────────────┐
                         │  query() (L102-140)    │
                         │  - Build prompt        │
                         │  - Get history         │
                         └────────────────────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │  SESSION MANAGER       │
                         │  Get conversation      │
                         │  history (last 2 turns)│
                         └────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               AI GENERATOR                                   │
│                          (backend/ai_generator.py)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │ generate_response() (L43-87)      │
                    │ - Build system prompt + history   │
                    │ - Add tool definitions            │
                    │ - Call Anthropic API              │
                    └─────────────────┬─────────────────┘
                                      │
                                      ▼
                         ╔════════════════════════╗
                         ║   ANTHROPIC CLAUDE     ║
                         ║   (1st API Call)       ║
                         ╚════════════════════════╝
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
        ┌───────────▼──────────┐          ┌────────────▼────────────┐
        │  stop_reason:        │          │  stop_reason:           │
        │  "end_turn"          │          │  "tool_use"             │
        │                      │          │                         │
        │  Return direct       │          │  Claude wants to search │
        │  answer              │          └────────────┬────────────┘
        └──────────────────────┘                       │
                    │                                  │
                    │                                  ▼
                    │                    ┌─────────────────────────────┐
                    │                    │ _handle_tool_execution()    │
                    │                    │ (L89-135)                   │
                    │                    │ - Extract tool_use blocks   │
                    │                    │ - Execute each tool         │
                    │                    └─────────────┬───────────────┘
                    │                                  │
                    │                                  ▼
                    │              ┌───────────────────────────────────┐
                    │              │      TOOL MANAGER                 │
                    │              │   (backend/search_tools.py)       │
                    │              │                                   │
                    │              │  execute_tool() (L135-140)        │
                    │              └───────────────┬───────────────────┘
                    │                              │
                    │                              ▼
                    │              ┌───────────────────────────────────┐
                    │              │   COURSE SEARCH TOOL              │
                    │              │   (backend/search_tools.py)       │
                    │              │                                   │
                    │              │   execute() (L52-86)              │
                    │              │   - query: "lesson 1"             │
                    │              │   - course_name: None             │
                    │              │   - lesson_number: None           │
                    │              └───────────────┬───────────────────┘
                    │                              │
                    │                              ▼
┌───────────────────┼──────────────────────────────────────────────────────────┐
│                   │              VECTOR STORE                                 │
│                   │          (backend/vector_store.py)                        │
└───────────────────┼──────────────────────────────────────────────────────────┘
                    │                              │
                    │              ┌───────────────▼───────────────────┐
                    │              │   search() (L61-100)              │
                    │              │                                   │
                    │              │   1. Resolve course_name?         │
                    │              │      → semantic search on catalog │
                    │              │                                   │
                    │              │   2. Build metadata filter        │
                    │              │      (course_title, lesson_number)│
                    │              │                                   │
                    │              │   3. Query course_content         │
                    │              │      with embeddings              │
                    │              └───────────────┬───────────────────┘
                    │                              │
                    │                              ▼
                    │              ┌───────────────────────────────────┐
                    │              │         CHROMADB                  │
                    │              │                                   │
                    │              │  Collections:                     │
                    │              │  • course_catalog (metadata)      │
                    │              │  • course_content (chunks)        │
                    │              │                                   │
                    │              │  Returns: top 5 relevant chunks   │
                    │              └───────────────┬───────────────────┘
                    │                              │
                    │                              │ SearchResults
                    │                              │ (documents, metadata)
                    │                              ▼
                    │              ┌───────────────────────────────────┐
                    │              │  _format_results() (L88-114)      │
                    │              │                                   │
                    │              │  Format as:                       │
                    │              │  "[Course - Lesson N]             │
                    │              │   {chunk content}"                │
                    │              │                                   │
                    │              │  Track sources in last_sources    │
                    │              └───────────────┬───────────────────┘
                    │                              │
                    │                              │ Formatted string
                    │                              │
                    │              ┌───────────────▼───────────────────┐
                    │              │  Tool results added to messages   │
                    │              └───────────────┬───────────────────┘
                    │                              │
                    │                              ▼
                    │              ╔═══════════════════════════════════╗
                    │              ║     ANTHROPIC CLAUDE              ║
                    │              ║     (2nd API Call)                ║
                    │              ║                                   ║
                    │              ║  Synthesize answer from           ║
                    │              ║  search results                   ║
                    │              ╚═══════════════┬═══════════════════╝
                    │                              │
                    │                              │ Final response
                    └──────────────────────────────┘
                                      │
                                      │ final_response.content[0].text
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BACK TO RAG SYSTEM                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                         ┌────────────▼───────────┐
                         │  Get sources from      │
                         │  tool_manager          │
                         │  (L130)                │
                         └────────────┬───────────┘
                                      │
                         ┌────────────▼───────────┐
                         │  Update session        │
                         │  history (L137)        │
                         └────────────┬───────────┘
                                      │
                                      │ return (response, sources)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BACK TO API ENDPOINT                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                         ┌────────────▼───────────┐
                         │  Build QueryResponse   │
                         │  {                     │
                         │    answer,             │
                         │    sources,            │
                         │    session_id          │
                         │  }                     │
                         └────────────┬───────────┘
                                      │
                                      │ JSON Response
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACK TO FRONTEND                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                         ┌────────────▼───────────┐
                         │  Parse response        │
                         │  (L76-85)              │
                         │                        │
                         │  - Store session_id    │
                         │  - Remove loading      │
                         └────────────┬───────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │  addMessage()          │
                         │  (L113-138)            │
                         │                        │
                         │  - Parse markdown      │
                         │  - Show answer         │
                         │  - Show sources        │
                         │    (collapsible)       │
                         └────────────────────────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │  User sees   │
                              │  response    │
                              └──────────────┘
```

## Key Decision Points

1. **Tool Use Decision** (Anthropic Claude 1st call)
   - General knowledge question → Direct answer (no search)
   - Course-specific question → Tool use (search required)

2. **Course Name Resolution** (Vector Store)
   - If course_name provided → Semantic search on catalog
   - Fuzzy matching: "MCP" finds "Introduction to MCP"

3. **Session Management**
   - First query: session_id = null → Backend creates new session
   - Subsequent queries: Frontend sends stored session_id

## Data Flow Summary

```
User Query
  → FastAPI validates
    → RAG System orchestrates
      → AI Generator calls Claude (1st)
        → If search needed:
          → Tool Manager routes to Search Tool
            → Vector Store queries ChromaDB
              → Returns relevant chunks
            → Format results + track sources
          → Claude synthesizes (2nd call)
        → Return answer + sources
      → Update session history
    → Return JSON response
  → Frontend displays with markdown
```
