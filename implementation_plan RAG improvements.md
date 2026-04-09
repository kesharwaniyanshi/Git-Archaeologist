# Implementation Plan: RAG Pipeline Quality Improvements

## What's Weak in the Current Pipeline

### 1. Evidence Starvation — synthesis prompt never sees raw diffs
The [synthesize_answer()](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py#124-170) method in [rag_pipeline.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py) builds evidence lines from **commit messages + 1-2 sentence LLM summaries only**. The actual code diffs (which are the most valuable forensic artifacts) are never passed to the final answer LLM call. This means the answer is essentially a summary-of-summaries, losing all code-level detail.

### 2. Excessive LLM Calls — one per candidate commit
[answer_question()](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/analyzers/query_analyzer.py#154-199) calls `summarizer.summarize_commit()` for **every candidate** (up to 20 commits). Each call hits Groq with a separate prompt. Most of these summaries are never used in the final answer (only top 5 survive). This wastes API quota and adds ~2-4 seconds per commit.

### 3. Rigid Bullet-Point Prompt Template
The synthesis prompt hardcodes a `1) 2) 3)` numbered structure and appends a mechanical "Confidence (deterministic)" footer. This forces every answer into the same unnatural format regardless of question type.

### 4. No Multi-Turn Context
[synthesize_answer()](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py#124-170) has zero awareness of previous questions. Each query is answered in complete isolation. Follow-up questions like "who else worked on that?" lose all prior context.

### 5. Heuristic Scoring Over-Weights Commit Messages
[candidate_commit_scores()](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/analyzers/query_utils.py#113-140) allocates 60% weight to [message_similarity](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/analyzers/query_utils.py#109-111) — a raw SequenceMatcher ratio between the query and commit message. This heavily penalizes commits with terse messages like "fix" or "wip" even when their diffs contain exactly what the user is asking about.

---

## Proposed Changes

### A. Feed Raw Diffs Into the Synthesis Prompt

#### [MODIFY] [rag_pipeline.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py)
- Add a `diff_snippets` field to [RetrievalResult](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_models.py#9-33) to carry truncated diff text through the pipeline
- Rewrite [synthesize_answer()](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py#124-170) to include actual code diffs (truncated to ~200 lines each) alongside the commit metadata
- Remove the mechanical numbered-list template; replace with a conversational system prompt

### B. Eliminate Per-Commit LLM Summarization During Retrieval

#### [MODIFY] [query_analyzer.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/analyzers/query_analyzer.py)
- Stop calling `summarizer.summarize_commit()` for every candidate
- Instead, pass raw diff data directly through to the final synthesis step
- Keep the summary cache as an **optional optimization** — if a cached summary exists, use it; otherwise skip the per-commit LLM call entirely
- This reduces LLM calls from ~20 per query down to **1** (just the final synthesis)

### C. Add Multi-Turn Conversation Support

#### [MODIFY] [rag_pipeline.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py)
- Accept an optional `conversation_history: List[Dict]` parameter in [synthesize_answer()](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py#124-170)
- Inject prior Q&A turns into the LLM prompt as context
- The history is passed in from the API layer, not stored inside the pipeline itself

### D. Rewrite the Synthesis Prompt for Conversational Quality

#### [MODIFY] [rag_pipeline.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_pipeline.py)
- New system prompt instructs the LLM to write naturally, cite specific commits inline, reference actual code when relevant, and avoid formulaic structure
- Increase `max_tokens` from 200 → 1000 for the synthesis call to allow substantive answers
- Remove the appended "Confidence (deterministic)" footer from the answer text — keep it as API metadata only

### E. Rebalance Heuristic Scoring

#### [MODIFY] [query_utils.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/analyzers/query_utils.py)
- Reduce message_similarity weight from 60% → 35%
- Increase filename_score weight from 30% → 40%
- Increase recency weight from 10% → 25%
- This ensures commits with poor messages but relevant file paths still surface

### F. Expand RetrievalResult to Carry Diffs

#### [MODIFY] [rag_models.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/pipelines/rag_models.py)
- Add `diff_snippets: Optional[str]` and `files_changed: Optional[List[str]]` fields

---

## Files NOT Modified
- [auth.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/api/routes/auth.py), [AuthModal.tsx](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/frontend/components/auth/AuthModal.tsx), [api.ts](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/frontend/lib/api.ts) — auth/frontend code is untouched per user request
- [diff_processor.py](file:///Users/yanshikesharwani/vscode/Git%20Archaeologist/core/diff_processor.py) — existing diff extraction logic is adequate; it's just not being *used* in the right place

## Verification Plan
- Test with a real repository link and compare answer quality before/after
- Verify LLM call count drops from ~20 to 1 per query
- Verify multi-turn follow-up questions reference prior context
- Check that answers include inline code references from diffs
