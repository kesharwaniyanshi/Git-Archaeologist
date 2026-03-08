# Git Archaeologist

A forensic RAG system that analyzes Git commit history and answers natural language questions about why code changed.

## 🚀 Quick Start (Full Stack)

### Prerequisites
- Python 3.9+
- Node.js 18+
- Git repository to analyze

### 1. Backend Setup

```bash
# Install Python dependencies
./.venv/bin/pip install -r requirements.txt

# Create .env file with your Groq API key
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=your_key_here

# Start FastAPI server
./.venv/bin/python -m uvicorn api.app:app --reload --port 8000
```

### 2. Frontend Setup

```bash
# Install frontend dependencies
cd frontend
npm install

# Start Next.js dev server
npm run dev
```

### 3. Open Browser

Navigate to [http://localhost:3000](http://localhost:3000) and start analyzing!

## 📁 Project Structure

```text
/
├── analyzers/     # Query-driven commit analysis
├── api/           # FastAPI REST service
├── pipelines/     # RAG retrieval + synthesis pipeline
├── core/          # Shared utilities (summarizer, embeddings, vector store)
├── cli/           # CLI entrypoints
└── frontend/      # Next.js web UI
```

## 🎯 Features

- 🔍 **Natural Language Queries**: Ask questions like "Why was authentication changed?"
- 🧠 **AI-Powered**: Uses Groq LLM for commit summarization
- 📊 **Semantic Search**: sentence-transformers for embeddings
- ⚡ **Fast Retrieval**: FAISS vector store with session persistence
- 🎨 **Modern UI**: Next.js + TypeScript + Tailwind CSS
- 🔄 **REST API**: FastAPI backend with full documentation

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.9, FastAPI |
| **Git Mining** | PyDriller |
| **LLM** | Groq API (llama-3.3-70b) |
| **Embeddings** | sentence-transformers |
| **Vector DB** | FAISS (local) |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS |

## 📖 Usage

### Web UI (Recommended)

1. Start backend: `./.venv/bin/python -m uvicorn api.app:app --reload --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open [http://localhost:3000](http://localhost:3000)
4. Enter your repo path and ask questions!

### CLI Usage

**RAG Pipeline**:
```bash
./.venv/bin/python -m pipelines.rag_cli . --query "Why was auth changed?" --top-k 5
```

**Query Analyzer**:
```bash
./.venv/bin/python -m analyzers.query_analyzer . --query "bug fixes" --max 100
```

### API Endpoints

### API Endpoints

**Health Check**:
```bash
curl http://127.0.0.1:8000/health
```
**Index Repository**:

```bash
curl -X POST http://127.0.0.1:8000/index \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/path/to/your/repo",
    "max_commits": 500,
    "use_embeddings": true
  }'
```

**Analyze Query**:
```

**Analyze Query**:

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/path/to/your/repo",
    "query": "Why was binary detection improved?",
    "top_k": 5,
    "show_evidence": true
  }'
```

## 🧪 Testing

**API Health Check**:
```bash
./.venv/bin/python smoke_test_api.py
```

**Frontend Build**:
```bash
cd frontend && npm run build
```

## 📚 Documentation

See [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md) for a complete technical walkthrough of all 7 build phases.

## 🔒 Environment Setup

Create `.env` file in project root:
```
GROQ_API_KEY=your_groq_api_key_here
```

Get your free Groq API key at [console.groq.com](https://console.groq.com)

## 🎨 Screenshots

### Web Interface
- Clean, modern dark theme
- Natural language query input
- Visual relevance scoring
- AI-generated summaries with confidence levels
- Real-time analysis results

## 🚧 Future Enhancements

- [ ] Authentication (GitHub OAuth)
- [ ] Timeline visualization
- [ ] WebSocket real-time updates
- [ ] Multi-repo management
- [ ] Query history
- [ ] Export results (JSON, CSV, PDF)
- [ ] Mobile app

## 📄 License

MIT

## 👤 Author

Yanshi Kesharwanibash
"/Users/yanshikesharwani/vscode/Git Archaeologist/.venv/bin/python" smoke_test_api.py
```
