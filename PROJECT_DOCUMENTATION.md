# Git Archaeologist - Project Documentation

**A forensic RAG system that analyzes Git commit history and answers natural language questions about why code changed.**

> 📝 This document tracks the complete flow and architecture of Git Archaeologist as we build it step-by-step.

---

## **Project Overview**

### **What is Git Archaeologist?**

Git Archaeologist mines Git commit history and creates searchable, AI-understood summaries of *why* code changed. Instead of reading raw diffs, you ask: "Why did authentication fail last month?" and the system searches through all commits to find relevant changes and explain them.

### **Technology Stack**

| Component | Technology | Why |
|-----------|-----------|-----|
| **Git Mining** | PyDriller | Cleaner API than GitPython, handles diffs automatically |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Local, fast, free, 384 dimensions |
| **LLM** | Groq API (llama-3.3-70b) | Free tier available, fast inference |
| **Vector DB** | Supabase pgvector | PostgreSQL + vector search, free tier |
| **Backend API** | FastAPI | Async, modern, easy to extend |
| **Frontend** | Next.js | (Future step) |
| **Language** | Python 3.9+ | Primary scripting language |

### **System Constraints**

✅ **Completely free** - No paid APIs, no cloud costs  
✅ **Local-first** - Embeddings generated locally  
✅ **Scalable** - Handles 100K+ commits efficiently  
✅ **Portable** - Can be deployed anywhere (on-prem or cloud)

---

## **Project Structure**

```
Git Archaeologist/
├── analyzers/                 # Query-driven commit analysis
│   ├── query_analyzer.py      # QueryDrivenAnalyzer orchestrator
│   └── query_utils.py         # Utility functions
├── api/                       # FastAPI REST service
│   └── app.py                 # /health, /status, /index, /analyze endpoints
├── cli/                       # Command-line interfaces
│   └── main.py                # Demo CLI entrypoint
├── core/                      # Shared utilities
│   ├── commit_indexer.py      # Lightweight commit metadata extraction
│   ├── diff_processor.py      # Diff parsing and formatting
│   ├── embeddings.py          # EmbeddingEngine (sentence-transformers)
│   ├── retrieval.py           # Keyword-based candidate selection
│   ├── summarizer.py          # CommitSummarizer (Groq LLM)
│   └── vector_store.py        # LocalVectorStore (FAISS)
├── pipelines/                 # RAG retrieval pipeline
│   ├── rag_cli.py             # CLI entrypoint for RAG queries
│   ├── rag_models.py          # RetrievalResult, QueryMetadata dataclasses
│   ├── rag_pipeline.py        # RAGPipeline orchestration
│   └── rag_processing.py      # QueryFilter, ResultRanker helpers
├── frontend/                  # Next.js UI (Step 7)
├── requirements.txt           # Python dependencies
├── .env                       # Secret keys (git-ignored)
├── .env.example               # Template for .env
├── .gitignore                 # Standard Python ignores
├── smoke_test_api.py          # API validation test
│
└── .git_arch_sessions/        # Session persistence
    └── [session_id]/
        ├── faiss.index        # Vector store
        ├── metadata.json      # Commit metadata
        └── mappings.json      # Hash-position mappings
```

---

## **Build Phases Overview**

This project is built in **7 steps**, each building on the previous one:

| Step | Name | Status | Output |
|------|------|--------|--------|
| 1 | Git Commit Extraction | ✅ **DONE** | Lightweight indexing |
| 2 | AI Summarization | ✅ **DONE** | Groq LLM summaries |
| 3 | Embeddings Generation | ✅ **DONE** | sentence-transformers (local) |
| 4 | Vector Storage | ✅ **DONE** | FAISS (local) with session persistence |
| 5 | RAG Retrieval | ✅ **DONE** | RAGPipeline with synthesis |
| 6 | FastAPI Endpoint | ✅ **DONE** | REST API with /index, /analyze |
| 7 | Frontend | 🚧 **IN PROGRESS** | Next.js UI |

---

## **STEP 1: Git Commit Extraction** ✅

### **Goal**
Extract the last N commits from a local Git repository with complete information:
- Commit hash, message, author, timestamp
- Files modified (with change type: ADD/MODIFY/DELETE/RENAME)
- Full unified diff for each file

### **Why This Matters**
This is the **data foundation**. Without clean extracted data, everything downstream breaks.

### **Files Involved**
- **`core/commit_indexer.py`** - `index_commits_lightweight()` function
- **`analyzers/query_utils.py`** - `ingest_light()` helper

### **How It Works**

```python
def extract_commits(repo_path: str, max_commits: int = 20) -> list[dict]:
    """
    Uses PyDriller to traverse the Git repository in reverse chronological order.
    
    For each commit:
    1. Extract metadata: hash, message, author, date
    2. For each modified file:
       - Get filename, change type
       - Count additions/deletions
       - Capture full unified diff
    3. Skip binary files (images, archives, etc.)
    4. Return list of commit dicts
    """
```

### **Data Structure**

```json
{
  "hash": "d4217dbc782c2229e2b64cfe046f7e3f03fe026c",
  "message": "Initial commit: Add core extraction module",
  "author": "Yanshi Kesharwani",
  "author_email": "kesharwaniyanshi@gmail.com",
  "date": "2026-03-06T13:19:59+05:30",
  "files_changed": [
    {
      "filename": "main.py",
      "change_type": "ADD",
      "additions": 111,
      "deletions": 0,
      "diff": "@@ -0,0 +1,111 @@\n+\"\"\"...\n"
    }
  ]
}
```

### **Key Design Decisions**

| Decision | Why |
|----------|-----|
| Skip binary files | No readable diffs, waste storage |
| Full diff included | LLM needs actual code to understand change |
| ISO date format | Language-agnostic, sortable |
| Nested file structure | Preserves git → files → diffs relationship |

### **Testing**

Run query-driven analysis:
```bash
cd "/Users/yanshikesharwani/vscode/Git Archaeologist"
./.venv/bin/python -m analyzers.query_analyzer . --query "your question" --max 10
```

Run RAG pipeline:
```bash
./.venv/bin/python -m pipelines.rag_cli . --query "your question" --top-k 5
```

---

## **STEP 2: AI Summarization** ✅

### **Goal**
Transform raw diffs into concise, natural language summaries that explain *why* code changed.

**Input**: Commit + message + diffs  
**Output**: "Fixed race condition in JWT validation by adding mutex lock to prevent concurrent token refresh"

### **Why This Matters**
Instead of searching raw diffs (hard, imprecise), we search summaries (human-readable, searchable). This is what goes into embeddings.

### *core/diff_processor.py`** - Parse and format diffs
- **`core/summarizer.py`** - LLM orchestration (CommitSummarizer class)
- **`analyzers/query_analyzer.py`** - QueryDrivenAnalyzer orchestrator

### **How It Works**

#### **Phase 1: Diff Processing** (`core/
#### **Phase 1: Diff Processing** (`diff_processor.py`)

```python
def extract_diff_summary(files_changed: list[dict]) -> dict:
    """
    Extract structured context from raw diffs:
    1. Count total files, additions, deletions
    2. Identify "primary diff" (largest change for LLM focus)
    3. Extract imports/dependencies mentioned in diffs
    4. Truncate huge diffs to 50 lines (save tokens)
    
    Returns a dict with:
    - total_files: 3
    - total_additions: 115
    - total_deletions: 5
    - primary_diff: {filename, change_type, diff_excerpt}
    - imports_mentioned: ['db', 'auth', 'utils']
    """
```

**Why truncation?**
- Groq API has token limits
- Huge diffs waste tokens without adding value
- LLM can understand intent from first 50 lines + context

#### **Phase 2: LLM Summarization** (`core/summarizer.py`)

```python
class CommitSummarizer:
    def __init__(self, api_key):
        # Initialize Groq client with llama-3.3-70b model
        # Free tier available, fast responses
        
    def _build_prompt(self, commit: dict) -> str:
        """
        Construct a focused prompt:
        
        Commit Message: {original message}
        
        Files Changed: 3 files
        - main.py (MODIFY) +50 -10
        - config.py (ADD) +30
        - utils.py (MODIFY) +35
        
        Primary Change: main.py
        Diff (excerpt):
        ```
        - old_code()
        + new_code()
        ```
        
        Dependencies/Imports: db, auth, utils
        
        INSTRUCTION: Explain why this was done (1-2 sentences, be direct)
        """
        
    def summarize_commit(self, commit: dict) -> dict:
        """
        1. Build prompt (above)
        2. Call Groq: client.chat.completions.create(...)
        3. Extract response text
        4. Return: {hash, message, summary, status, error}
        """
```

### **Data Structure**

```json
{
  "hash": "d4217dbc782c2229e2b64cfe046f7e3f03fe026c",
  "message": "Initial commit: Add core extraction module",
  "summary": "This commit adds a core extraction module that enables extraction of commits from Git repositories with full diff information, solving the problem of manually retrieving and processing commit data. The impact is automated commit history analysis.",
  "status": "success",
  "error": null
}
```

### **Key Design Decisions**

| Decision | Why |
|----------|-----|
| Option 2: Diff + Related Context | Better than just diff alone, cheaper than full repo |
| Import extraction | Helps LLM understand dependencies without full repo context |
| Truncate large diffs | Save tokens, still preserve intent (first 50 lines usually contain the key change) |
| Error fallback to message | If API fails, use commit message as summary (graceful degradation) |
| Groq (free tier) | Open-source LLM access, no subscription, fast |
| Temperature 0.3 | Lower = more focused, less creative (good for technical summaries) |

### **Testing**

Run API server:
```bash
./.venv/bin/python -m uvicorn api.app:app --reload --port 8000
```

Health check:
```bash
python smoke_test_api.py
```

## **STEP 3: Embeddings Generation** ✅ (Local)

### **Goal**
Use local sentence-transformer embeddings to improve commit candidate selection for query-driven analysis.

### **What was implemented**
- Added `embeddings.py` with:
    - `EmbeddingEngine` (model: `all-MiniLM-L6-v2`)
    - commit semantic text builder
    - cosine similarity ranking utilities
- Updated `query_analyzer.py` to:
    - build embeddings during indexing
    - use hybrid retrieval (semantic + heuristic)
    - fall back gracefully to heuristic-only mode if embeddings are unavailable
    - add CLI flags: `--no-embeddings`, `--embedding-model`

### **Result**
Query-driven retrieval now prioritizes semantically relevant commits instead of relying only on keyword and recency heuristics.
./.venv/bin/python3 main.py
```

Output: `summaries_generated.json` with AI-generated explanations

---

## **Datacore/commit_indexer.py]
    ↓
Lightweight commit metadata
    ↓
[STEP 2: core/summarizer.py + core/diff_processor.py]
    ↓
AI-generated summaries
    ↓
[STEP 3: core/embeddings.py]
    ↓
Semantic vectors (384-dim)
    ↓
[STEP 4: core/vector_store.py]
    ↓
FAISS index + session persistence
    ↓
[STEP 5: pipelines/rag_pipeline.py + analyzers/query_analyzer.py]
    ↓
RAG retrieval + answer synthesis
    ↓
[STEP 6: api/app.py]
    ↓
FastAPI REST endpoints
    ↓
[STEP 7: frontend/ → Next.js UI
[STEP 5: NEXT → RAG Retrieval]
    ↓
[STEP 6: NEXT → FastAPI]
    ↓
[STEP 7: NEXT → Frontend]
```

---

## **Dependencies**

### **Currently Installed**

```
PyDriller==2.3        # Git mining
python-dotenv==1.0.0  # Environment variables
groq==1.0.0           # LLM API
```

### **To Be Added (Future Steps)**

```
sentence-transformers  # Embeddings (Step 3)
supabase==2.0.0       # Vector DB (Step 4)
fastapi==0.104.0      # API (Step 6)
uvicorn==0.24.0       # ASGI server (Step 6)
```

---

## **Environment Setup**

### **Required Files**

1. **`.env`** (git-ignored, contains secrets)
   ```
   GROQ_API_KEY=gsk_xxxxx  # From console.groq.com
   SUPABASE_URL=xxx        # From supabase.co (Step 4)
   SUPABASE_KEY=xxx        # From supabase.co (Step 4)
   ```

2. **`.env.example`** (git-tracked, shows template)
   ```
   GROQ_API_KEY=your_groq_api_key_here
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your_supabase_key_here
   ```

### **Virtual Environment**

```bash
# Create
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install
pip install -r requirements.txt

# Run
./.venv/bin/python3 main.py
```

---

## **Key Learnings So Far**

### **1. Diff Processing Strategy (Option 2)**

**Problem**: 
- Raw diffs alone miss context (what dependencies were touched?)
- Full repo context is too expensive (millions of lines)

**Solution**:
- Extract diffs + identify imports/dependencies
- Give LLM just the relevant context
- Let LLM do the logic understanding

### **2. Error Handling Pattern**

```python
try:
    summary = get_ai_summary()
except Exception as e:
    summary = commit_message  # Fallback
    status = "error"
```

Graceful degradation: If API fails, we still have *something* to search (original message).

### **3. Token Optimization**

LLM APIs charge by tokens. We optimize by:
- Truncating large diffs (first 50 lines usually contain intent)
- Removing boilerplate code from diffs
- Using lower temperature (0.3) = shorter responses

### **4. Data Structure Consistency**

All outputs follow same JSON structure:
```json
{
  "hash": "...",
  "status": "success|error",
  "data": {...}
}
```

Makes it easy to chain steps together.

---

## **Common Commands**

```bash
# Full pipeline
./.venv/bin/python3 main.py

# Check current summaries
cat summaries_generated.json | jq '.[] | {hash: .hash, summary: .summary}'

# Count commits processed
cat summaries_generated.json | jq 'length'

# See successful summaries only
cat summaries_generated.json | jq '.[] | select(.status=="success")'
```

---

## **Next Steps Timeline**

- **Step 3**: Generate embeddings (convert summaries → 384-dim vectors)
- **Step 4**: Store vectors in Supabase pgvector
- **Step 5**: Build RAG retrieval (semantic search + ranking)
- **Step 6**: Create FastAPI endpoints
- **Step 7**: Build Next.js frontend

---

## **Logs & Debugging**

### **Check extraction**
```bash
cat commits_extracted.json | jq '.[0] | keys'
# Shows: ["hash", "message", "author", "date", "files_changed"]
```

### **Check summaries**
```bash
cat summaries_generated.json | jq '.[0]'
# Shows: {hash, message, summary, status, error}
```

### **API key check**
```bash
source .env && echo $GROQ_API_KEY
# Should print your key (never commit this!)
```

---

## **STEP 3: Embeddings Generation** ✅ (Local, In-Memory)

### **Goal**
Use local sentence-transformers to convert commit metadata into semantic embeddings for improved candidate ranking.

### **What was implemented**
- **`embeddings.py`**: 
  - `EmbeddingEngine` wraps sentence-transformers (`all-MiniLM-L6-v2`)
  - `build_commit_semantic_text()`: converts commit metadata to text for embedding
  - `rank_commits_by_semantic()`: cosine similarity ranking
  - Graceful error handling if model unavailable

- **Integration in `query_analyzer.py`**:
  - Build embeddings during indexing
  - Use hybrid retrieval: semantic ranking (55% weight) + heuristic ranking (45% weight)
  - Auto-fallback to heuristic-only if embeddings unavailable

### **Usage**
```bash
# Index with embeddings (default)
python -m analyzers.query_analyzer . --max 200 --query "Why was auth changed?"

# Without embeddings (faster for small repos)
python -m analyzers.query_analyzer . --max 200 --query "..." --no-embeddings

# Custom embedding model
python -m analyzers.query_analyzer . --embedding-model "all-mpnet-base-v2"
```

---

## **STEP 4: Persistent Vector Storage** ✅ (Local FAISS)

### **Goal**
Persist embeddings and summaries to disk so repeated queries on the same repo don't require re-indexing.

### **What was implemented**
- **`vector_store.py`**:
  - `LocalVectorStore` class using FAISS for similarity search
  - JSON metadata for commit information
  - Methods: `add_embeddings()`, `search()`, `save()`, `load()`
  - Efficient binary FAISS index + JSON metadata snapshots

- **Session Management** in `query_analyzer.py`:
  - `save_session()`: saves index + embeddings + summaries cache to disk
  - `load_session()`: loads session from disk (skips re-indexing)
  - Default session location: `.git_arch_sessions/<session_name>/`

- **Persistence includes**:
  - FAISS index (`faiss.index`)
  - Commit metadata (`metadata.json`)
  - Index mappings (`mappings.json`)
  - Summary cache (`cache.json`)
  - Commit index (`index.json`)

### **Usage**
```bash
# First run: index and save session
python -m analyzers.query_analyzer . --max 200 --session-dir .sessions/my_repo --query "Why was binary detection improved?"
# Outputs: ✅ Indexed, 🧠 Built embeddings, 💾 Saved vector store

# Second run: load session (instant, no re-indexing)
python -m analyzers.query_analyzer . --session-dir .sessions/my_repo --load-session --query "Why was auth changed?"
# Outputs: 📂 Loaded session with 3 embeddings, ✅ Loaded vector store

# Create different sessions for different repos
python -m analyzers.query_analyzer ../other_repo --session-dir .sessions/other_repo --load-session
```

### **Performance Benefits**
- **First indexing**: 5-30s for 100-500 commits (depends on diffs size)
- **Session load**: <1s (just loads from disk + Groq calls for new summaries)
- **Memory**: Embeddings + metadata only (~few MB for 100 commits)
- **Scalability**: Can handle 10K+ commits with FAISS (optimizes with IVF indexing if needed)

### **Future: Supabase/pgvector Migration**
To migrate from local FAISS to Supabase pgvector:
1. Create Supabase project (free tier: 500MB database)
2. Create pgvector extension and embeddings table
3. Extend `LocalVectorStore` to a `SupabaseVectorStore` class
4. Point `query_analyzer.py` to cloud storage instead of disk

---

## **Updated: 7 March 2026**

**Completed**: Steps 1-4 (Extraction, Summarization, Local Embeddings, Persistent Vector Store)  
**In Progress**: None  
**Next**: Complete (All Steps 1-7 Done! 🎉)

---

## **STEP 7: Frontend** ✅

### **Goal**
Build a modern, user-friendly web interface for Git Archaeologist using Next.js, TypeScript, and Tailwind CSS.

### **What Was Implemented**

#### **Technology Stack**
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first styling with dark mode
- **Axios** - API communication

#### **Project Structure**
```
frontend/
├── app/
│   ├── globals.css         # Tailwind styles
│   ├── layout.tsx          # Root layout with metadata
│   └── page.tsx            # Main page (search + results)
├── components/
│   ├── Header.tsx          # App header with branding
│   ├── SearchInterface.tsx # Query input form
│   └── ResultsView.tsx     # Display analysis results
├── lib/
│   └── api.ts              # API client (healthCheck, analyzeQuery, etc.)
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js          # Proxy /api/* → http://localhost:8000
└── .env.local              # Environment variables
```

### **Key Features**

#### **1. Search Interface**
- Repository path input
- Natural language query textarea
- Configurable parameters:
  - Top K results (1-20)
  - Max commits to analyze (10-10000)
- Responsive design with dark mode

#### **2. Results Display**
- **Synthesized Answer Section**:
  - AI-generated answer with confidence badge (High/Medium/Low)
  - Confidence score percentage
  - Clean, readable formatting

- **Metadata Panel**:
  - Total commits indexed
  - Candidates analyzed
  - Query execution time

- **Relevant Commits List**:
  - Commit hash (short)
  - Commit message
  - AI-generated summary
  - Visual relevance score bar
  - Status badges

#### **3. UI/UX Design**
- Modern dark theme with gradient backgrounds
- Smooth transitions and hover effects
- Loading spinner during analysis
- Error handling with user-friendly messages
- Fully responsive layout

### **API Integration**

The frontend communicates with the FastAPI backend at `http://localhost:8000`:

```typescript
// lib/api.ts
export async function analyzeQuery(data: AnalyzeRequest) {
  const response = await apiClient.post('/analyze', data)
  return response.data
}
```

Next.js config proxies `/api/*` to the backend for seamless integration.

### **Setup & Run**

#### **Install Dependencies**
```bash
cd frontend
npm install
```

#### **Environment Variables**
Create `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### **Development Mode**
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

#### **Production Build**
```bash
cd frontend
npm run build
npm start
```

### **Full Stack Workflow**

1. **Start Backend API** (Terminal 1):
   ```bash
   cd "/Users/yanshikesharwani/vscode/Git Archaeologist"
   ./.venv/bin/python -m uvicorn api.app:app --reload --port 8000
   ```

2. **Start Frontend Dev Server** (Terminal 2):
   ```bash
   cd frontend
   npm run dev
   ```

3. **Open Browser**:
   - Navigate to [http://localhost:3000](http://localhost:3000)
   - Enter your repository path
   - Ask a question
   - View results!

### **Design Decisions**

| Decision | Why |
|----------|-----|
| Next.js 14 (App Router) | Modern React patterns, server components, built-in optimization |
| TypeScript | Type safety, better IDE support, fewer runtime errors |
| Tailwind CSS | Rapid styling, consistent design system, dark mode support |
| Client-side rendering | Better for interactive query interface, no SSR needed |
| Axios over fetch | Interceptors, better error handling, concise API |
| Dark theme | Easier on eyes for developers, modern aesthetic |

### **Future Enhancements**
- 🔐 Authentication (GitHub OAuth)
- 📊 Commit timeline visualization
- 🔄 Real-time status updates via WebSockets
- 📁 Multiple repository management
- 💾 Query history
- 📤 Export results (JSON, CSV, PDF)
- 🎨 Theme customization
- 📱 Mobile app (React Native)

---

## **Cloud Database Decision Guide (March 2026)**

This section compares cloud PostgreSQL options for the current architecture:
- FastAPI backend
- SQLAlchemy + psycopg
- pgvector for embeddings
- Persistent repositories/commits/chat/summaries in PostgreSQL

### **Decision Criteria**

| Criteria | Why it matters for this project |
|----------|----------------------------------|
| PostgreSQL compatibility | Existing code already uses SQLAlchemy + psycopg |
| pgvector support | Required for embedding similarity search |
| Dev speed | We are iterating quickly across migration phases |
| Operational overhead | Small team; managed service is preferred |
| Cost predictability | Early-stage product, needs low fixed cost |
| Production path | Should scale from prototype to staging/production |

### **Cloud Options Compared**

| Option | Best Fit | pgvector | Ops Overhead | Cost Shape | Key Tradeoff |
|--------|----------|----------|--------------|------------|---------------|
| Neon Postgres | Fast product teams, branch-style workflows | Strong support | Low | Low-medium | Fewer low-level infra knobs |
| Supabase Postgres | App + DB platform users | Strong support | Low | Low-medium | More platform opinionation |
| AWS RDS/Aurora Postgres | Enterprise AWS-native teams | Version-dependent | Medium-high | Medium-high | More setup and tuning effort |
| Google Cloud SQL Postgres | GCP-native teams | Version-dependent | Medium | Medium | Less developer-friendly branching |
| Azure Database for PostgreSQL | Azure-native teams | Tier/version-dependent | Medium | Medium | Extension support varies by plan |

### **Recommendation for Git Archaeologist**

Use **Neon Postgres** as the primary cloud database for the current stage.

**Why Neon is the best fit now:**
1. Works directly with current `postgresql+psycopg` connection pattern.
2. Good pgvector support for current embedding architecture.
3. Low operational overhead while still production-capable.
4. Fast path from local prototype to shared staging.
5. Keeps migration velocity high for remaining phases.

**Strong alternative:**
- **Supabase Postgres**, if you want a more integrated dashboard-centric platform.

### **Cloud Adoption (Minimal Path)**

1. Create a managed PostgreSQL instance (Neon recommended).
2. Copy connection string and set `.env` values:

```env
VECTOR_BACKEND=pgvector
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

3. Start backend and run one `/analyze` call to trigger table creation.
4. Verify persistence behavior across restart.

### **Verification Checklist**

After first successful query, verify tables:
1. `repositories`
2. `commits`
3. `commit_embeddings`
4. `commit_summaries`
5. `chat_sessions`
6. `chat_messages`

Behavior to validate:
1. Re-running similar questions reduces LLM calls over time (summary reuse).
2. Chat follow-up queries keep the same `chat_session_id` in a UI session.
3. Commit index and embeddings reload from DB after backend restart.

### **Local vs Cloud Usage Strategy**

Use both, with clear purpose:
1. **Cloud Postgres**: primary for shared/staging-like testing and durability.
2. **Local Postgres**: fallback for offline development and fast debugging.

### **Migration Safety Notes**

1. Keep dev/staging/prod DB URLs separate.
2. Never commit real credentials.
3. URL-encode password if it contains special characters.
4. Prefer pooled connection URLs in managed environments.
5. Confirm `vector` extension availability in selected provider/tier.

---

## **Updated: 8 March 2026**

**Completed**: Steps 1-7 (Full Stack Implementation Complete! 🎉)  
- ✅ Git Commit Extraction
- ✅ AI Summarization (Groq LLM)
- ✅ Embeddings Generation (sentence-transformers)
- ✅ Vector Storage (FAISS with session persistence)
- ✅ RAG Retrieval Pipeline
- ✅ FastAPI Backend
- ✅ Next.js Frontend

**Status**: Production-ready prototype  
**Next Steps**: Testing, deployment, feature enhancements
