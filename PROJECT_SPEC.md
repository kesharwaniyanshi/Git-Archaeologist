# Git Archaeologist — Master Project Spec & Architecture Plan

## 1. Vision & One-Line Product Definition
**A free, conversational Git intelligence assistant that explains why code changed and what a developer contributed by reasoning over repository history and diffs.**

Git Archaeologist is a conversational AI system for Git repositories. Users can connect a GitHub account or provide a public repository URL, then ask natural-language questions about the repository’s code history, commit diffs, architectural changes, and developer contributions.

## 2. Core Goals & Design Principles
- **Chat Experience:** Work like ChatGPT / GitHub Copilot, but for Git history.
- **Deep Analysis:** Do not rely only on commit messages. Analyze the repository code structure, diffs, metadata, and full commit history together.
- **Conversation & Memory:** Support multi-turn chat, follow-up questions, and conversation memory. Persist chat history.
- **Efficiency:** Prefer incremental indexing and reusable stored summaries. Keep LLM calls minimal and cached.
- **Cost:** Stay **100% free** to build and run using free-tier or open-source tools only.
- **Engineering Quality:** Be production-quality: clean architecture, modular code, testable services, scalable design. 
- **Separation of Concerns:** Clearly separate auth, repo ingestion, indexing, retrieval, chat, and UI. Start simple, validate each phase, then expand.

## 3. Technology Stack Direction
- **Backend:** Python + FastAPI
- **Frontend:** Next.js
- **LLM:** Free-tier or open-source only (e.g., Groq API)
- **Embeddings:** `sentence-transformers` (local)
- **Vector Storage / Database:** PostgreSQL + pgvector
- **Auth:** Google/GitHub/email-password via a free auth layer
- **Background Work:** Free scheduler/worker approach

## 4. Must-Have Features
- Sign in / sign up (Google, GitHub, Email + Password)
- Public GitHub repo support for now (either attach via GitHub or paste URL)
- Repo ingestion and commit indexing
- Diff analysis and semantic summarization
- RAG-based question answering
- Multi-turn conversational chat with persisted history
- Contributor analysis: questions like “What did I contribute?” or “What changes did I make?”
- Support natural language questions based on codebase or commits like "Why was this change done?" or "What changes did I make related to some specific feature?"

## 5. Current Architecture Audit
### What Has Already Been Built
- **Backend Core**: FastAPI backend that extracts local commits, parses diffs, generates embeddings using `sentence-transformers`, searches using a local FAISS index, and retrieves context.
- **LLM Integration**: Uses Groq LLMs to summarize commits and synthesize concise natural-language answers based on similarities.
- **Frontend**: Next.js 14-based React interface with a basic dark theme and query-input capability, interacting directly via a REST API.
- **Session Layer**: File-based `.git_arch_sessions` infrastructure managing FAISS vectors and indexed commit mappings locally per session.

### What Is Working Well
- **End-to-End Pipeline**: The data flow logic (Extraction -> Embedding -> FAISS Storage -> Retrieval -> LLM generation) is actively working for proof-of-concept repositories.
- **Hybrid Retrieval Strategy**: Successfully weighs both semantic similarity and simple heuristic keyword matches to improve base LLM generation relevance.
- **Clean UI Groundwork**: Initial Tailwind CSS and TypeScript interface layout is highly functional and cleanly separates the query UI from the results mapping.

### What Needs Improvement (Code Quality Issues)
- **God Classes & Missing Abstractions**: Primary orchestrators like `QueryDrivenAnalyzer` handle too many responsibilities (managing sessions, FAISS, LLMs, caching, retrieval) instead of distinct service layers.
- **In-Memory/File System Mutability**: Relying heavily on local disk (`AnalyzerRegistry` and `.git_arch_sessions`) prevents horizontal scaling and risks race conditions.
- **Lack of Defensive Engineering & Logging**: Uses generic `Exception` catchers and raw `print()` statements rather than structured logging (`structlog`), severely limiting observability.
- **AI Context Fragmenting**: Summaries are processed in strict isolation, robbing the LLM of chronological cross-commit awareness.

### Security Vulnerabilities
- **Sensitive Key Exposure Risk**: `GROQ_API_KEY` is loaded in plaintext and exceptions are broadly cast, risking exposing keys in raw stack traces to users.
- **Unauthenticated Endpoints**: Fully accessible backends allowing Denial-of-Wallet attacks via unauthenticated Groq completion exhaustion.
- **Path Traversal Vulnerability**: Allowing absolute internal file directory loading via `/analyze` input without sandboxing.
- **Prompt Injection**: User queries are merged directly into prompts without protective formatting.

### Performance Limitations
- **Sequential API Bottleneck**: Generating summaries for Top-k commits inside singular `for` loops scales linearly, turning into massive API roundtrip blockages (5-30s latencies).
- **Synchronous Event Loop Locking**: Slow computations block the FastAPI `async` handlers, halting concurrent capabilities.
- **Full Traversals**: Reading vast Git histories from scratch every reload; absence of incremental index refreshes.

### Critical Missing Components
- **Auth Layer & Persistence**: Missing integration with an identity provider (OAuth) and a persistent SQL database to manage users securely.
- **Continuous Conversation Context**: Complete absence of retained Chat Sessions/Histories (like OpenAI threads), breaking follow-up capabilities.
- **Contributor Extraction**: Missing complex relationship logic to map Git authors statistically with repository/module expertise.

## 6. Proposed Data Model (PostgreSQL)
*Reasoning: While the master spec correctly identified the core tables, a production app relying heavily on LLM constraints and rapid UX needs caching and job statuses. I have expanded the required schema below to accommodate these architectural realities.*

- `users` (OAuth identity, email, dates)
- `repositories` (GitHub URLs, clone status, total commits)
- `commits` (Hashes, messages, timestamps, cached diff summaries)
- `commit_embeddings` (pgvector column for 384-dim arrays linking to commits)
- `chat_sessions` (User + Repo pairing to group messages chronologically)
- `chat_messages` (Strict 'user'/'assistant' roles + cited commit arrays)
- `query_cache` (Hashes of semantic queries linked to answers to save LLM costs)
- `rate_limits` (Endpoint hits mapped to users to prevent LLM/API exhaustion)
- `repo_membership` (For linking private/org repo access auths if needed later on)

## 7. Step-by-Step Implementation Roadmap (Build Order)

*Reasoning: Taking your 10 foundational phases, I have populated them with the precise concrete technical milestones we identified during the audit.*

1. **Phase 1: Audit codebase and map what already exists (Complete)**
   - Performed architecture audit and created this PROJECT_SPEC.md.

2. **Phase 2: Define target architecture, identify gaps, and refactor**
   - Shift to a Service/Controller MVC architecture for FastAPI.
   - Isolate Pydantic request/response models.
   - Implement structured logging (`structlog`) and standardized error handling middlewares.

3. **Phase 3: Add authentication**
   - Set up NextAuth in the Next.js frontend (GitHub + Local Login).
   - Secure FastAPI endpoints via JWT token verification middleware.

4. **Phase 4: Add repository linking for public repos**
   - Support passing GitHub public repo URLs instead of local absolute paths.
   - Integrate a backend task queue (e.g., Celery or FastAPI BackgroundTasks) for background code fetching without freezing the API.

5. **Phase 5: Persist repo metadata and commits in PostgreSQL**
   - Provision PostgreSQL (with pgvector).
   - Use SQLAlchemy and Alembic for migrations on `Users`, `Repositories`, and `Commits` tables.
   - Entirely deprecate/remove the local `.git_arch_sessions` infrastructure.

6. **Phase 6: Index diffs and code context**
   - Move from FAISS to `commit_embeddings` in pgvector.
   - Expand the data ingested during embeddings to include chunked code diffs natively (not just commit subject lines).

7. **Phase 7: Improve retrieval quality and prompt quality**
   - Upgrade Groq prompts to support chain-of-thought and markdown code citations.
   - Introduce parallel (`asyncio.gather`) LLM summarizations to fix latency blockages.

8. **Phase 8: Add chat session persistence and follow-up context**
   - Scaffold the `chat_sessions` and `chat_messages` tables.
   - Update the Next.js UI to load past sessions and append conversation history to LLM prompts.

9. **Phase 9: Add contributor analysis**
   - Introduce new query intent classifications (e.g. "Who wrote...", "Who understands...").
   - Add pipeline analytics to count author-specific line adjustments chronologically.

10. **Phase 10: Clean up, maintainability, and production hardening**
    - Apply Redis-based rate limiting on endpoints.
    - Path-sanitization hardening against Traversal / Injection.
    - Set up Dockerfiles and simple CI/CD pipelines for deployment.

## 8. Working Rules for Future Prompts
- First explain what you understand from the codebase.
- Then explain what must change.
- Then propose the minimal next implementation step.
- Ask for approval before making large structural changes.
- Keep the implementation incremental.
- Avoid rewriting unrelated parts.
- When code is changed, explain the reason and the impact.
