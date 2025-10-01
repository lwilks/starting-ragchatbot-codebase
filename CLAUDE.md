# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Retrieval-Augmented Generation (RAG) system for answering questions about course materials. Uses ChromaDB for vector storage, Anthropic's Claude API for AI generation, and FastAPI with a static frontend for the web interface.

## Commands

### Running the Application
```bash
# Start the development server from backend/
cd backend
uv run uvicorn app:app --reload --port 8000

# Or use the convenience script from root
./run.sh
```

The application serves:
- Web interface at `http://localhost:8000`
- API docs at `http://localhost:8000/docs`

### Dependencies
```bash
# Install dependencies
uv sync
```

## Architecture

### Core Components

The system follows a modular RAG architecture with clear separation of concerns:

**RAGSystem** (`backend/rag_system.py`) - Main orchestrator that coordinates:
- Document processing pipeline
- Vector storage operations
- AI response generation
- Tool-based search execution
- Session management

**Vector Storage** (`backend/vector_store.py`) - Two ChromaDB collections:
- `course_catalog`: Stores course metadata (titles, instructors, lessons) for fuzzy course name matching
- `course_content`: Stores chunked course content with metadata filters for semantic search

**Search Architecture** (`backend/search_tools.py`):
- Uses tool calling pattern (not direct retrieval)
- `CourseSearchTool` executes searches via `VectorStore.search()`
- AI decides when to search based on query type
- Tool manager tracks sources from searches for UI display

**AI Generation** (`backend/ai_generator.py`):
- Handles Anthropic API interactions with tool calling
- System prompt restricts to one search per query
- Executes tool calls and incorporates results into responses

### Data Models

**Course Structure** (`backend/models.py`):
- `Course`: title (unique ID), instructor, course_link, lessons[]
- `Lesson`: lesson_number, title, lesson_link
- `CourseChunk`: content, course_title, lesson_number, chunk_index

### Document Processing

**DocumentProcessor** (`backend/document_processor.py`):
- Expects specific format: Course Title, Course Link, Course Instructor as first 3 lines
- Parses "Lesson N: Title" markers with optional "Lesson Link:" on next line
- Chunks content by sentences with configurable size/overlap (config: 800/100 chars)
- Adds context prefix to chunks: "Course {title} Lesson {N} content: {chunk}"

### Configuration

**Config** (`backend/config.py`):
- `ANTHROPIC_MODEL`: claude-sonnet-4-20250514
- `EMBEDDING_MODEL`: all-MiniLM-L6-v2 (sentence-transformers)
- `CHUNK_SIZE`: 800 chars
- `CHUNK_OVERLAP`: 100 chars
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 conversation turns
- `CHROMA_PATH`: ./chroma_db

### API Endpoints

**POST /api/query**:
- Request: `{query: str, session_id?: str}`
- Response: `{answer: str, sources: List[str], session_id: str}`
- Creates session if not provided, maintains conversation history

**GET /api/courses**:
- Response: `{total_courses: int, course_titles: List[str]}`

**Startup**: Auto-loads documents from `../docs` directory on server start

## Key Implementation Details

### Search Flow
1. AI receives query with `search_course_content` tool available
2. If query needs course data, AI calls tool with query + optional filters
3. `CourseSearchTool.execute()` resolves fuzzy course names via catalog search
4. Vector search on `course_content` collection with metadata filters
5. Results formatted with course/lesson context, sources tracked
6. AI synthesizes response from search results

### Course Name Matching
- User provides partial name (e.g., "MCP", "Introduction")
- Vector search against `course_catalog` finds best match
- Exact course title used for filtering `course_content`

### Session Management
- Sessions track conversation history (last N turns)
- History included in AI system prompt for context
- Managed via `SessionManager` (`backend/session_manager.py`)
