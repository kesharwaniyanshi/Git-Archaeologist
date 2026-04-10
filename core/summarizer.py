"""
Summarizer - Generate AI summaries using Google Gemini API.
Converts raw code changes into natural language explanations of intent.
Supports both Gemini (primary) and Groq (fallback) backends.
"""

import os
from typing import Optional

from .diff_processor import extract_diff_summary, format_diff_for_llm


class CommitSummarizer:
    """
    Summarizes commits using Google Gemini's free API (1M token context).
    Falls back to Groq if Gemini is unavailable.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the summarizer. Tries Gemini first, falls back to Groq.

        Args:
            api_key: Optional API key override. If None, reads from env vars.
        """
        self.backend = None
        self._gemini_model = None
        self._groq_client = None
        self._groq_model = "llama-3.3-70b-versatile"

        # Try Gemini first
        gemini_key = api_key or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self._gemini_model = genai.GenerativeModel("gemini-2.5-flash")
                self.backend = "gemini"
                print("Summarizer backend: Gemini 2.5 Flash (1M context)")
            except Exception as exc:
                print(f"Gemini init failed: {exc}")

        # Fallback to Groq
        if not self.backend:
            groq_key = api_key or os.getenv("GROQ_API_KEY")
            if groq_key:
                try:
                    from groq import Groq
                    self._groq_client = Groq(api_key=groq_key)
                    self.backend = "groq"
                    print("Summarizer backend: Groq (fallback)")
                except Exception as exc:
                    print(f"Groq init failed: {exc}")

        if not self.backend:
            raise ValueError(
                "No LLM backend available. Set GEMINI_API_KEY or GROQ_API_KEY env var. "
                "Get a free Gemini key at https://aistudio.google.com/apikey"
            )

    def summarize_commit(self, commit: dict) -> dict:
        """
        Generate a summary for a single commit.

        Args:
            commit: Commit dict with hash, message, author, files_changed

        Returns:
            Dictionary with hash, message, summary, status, error
        """
        result = {
            "hash": commit["hash"],
            "message": commit["message"],
            "summary": None,
            "status": "error",
            "error": None,
        }

        try:
            diff_summary = extract_diff_summary(commit["files_changed"])
            prompt = self._build_prompt(commit, diff_summary)
            summary_text = self._call_llm(prompt, max_tokens=200)

            result["summary"] = summary_text
            result["status"] = "success"

        except Exception as e:
            # Fallback: use commit message as summary
            result["summary"] = commit["message"]
            result["status"] = "error"
            result["error"] = str(e)
            print(f"⚠️  Summarization failed for {commit['hash'][:8]}: {e}")

        return result

    def _build_prompt(self, commit: dict, diff_summary: dict) -> str:
        """Build a focused prompt for the LLM with context."""
        diff_context = format_diff_for_llm(commit, diff_summary)

        prompt = f"""You are analyzing a Git commit to explain why code was changed.

Commit Message: {commit['message']}

Author: {commit['author']}

{diff_context}

Based on the commit message and code changes shown above, provide a concise 1-2 sentence explanation of:
1. What problem this solves or what feature it adds
2. The impact or benefit

Be direct and technical. Avoid vague phrases."""

        return prompt

    def _call_llm(self, prompt: str, max_tokens: int = 200) -> str:
        """Call the active LLM backend with a single user prompt."""
        if self.backend == "gemini":
            return self._call_gemini(prompt, max_tokens)
        else:
            return self._call_groq_single(prompt, max_tokens)

    def _call_gemini(self, prompt: str, max_tokens: int = 200) -> str:
        """Call Gemini API."""
        try:
            response = self._gemini_model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": max_tokens,
                },
            )
            return response.text.strip()
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    def _call_groq_single(self, prompt: str, max_tokens: int = 200) -> str:
        """Call Groq API with a single user prompt."""
        try:
            message = self._groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self._groq_model,
                temperature=0.3,
                max_tokens=max_tokens,
            )
            return message.choices[0].message.content.strip()
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")

    def _call_groq_synthesis(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM with system+user roles for answer synthesis.
        This is the main method used by the RAG pipeline.
        Tries Gemini first, falls back to Groq on failure."""
        if self.backend == "gemini":
            try:
                return self._call_gemini_synthesis(system_prompt, user_prompt)
            except Exception as gemini_exc:
                print(f"Gemini synthesis failed, falling back to Groq: {gemini_exc}")
                # Fall through to Groq if available
                if not self._groq_client:
                    groq_key = os.getenv("GROQ_API_KEY")
                    if groq_key:
                        from groq import Groq
                        self._groq_client = Groq(api_key=groq_key)

        # Groq path (primary when backend=groq, fallback when gemini fails)
        if self._groq_client:
            try:
                message = self._groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self._groq_model,
                    temperature=0.4,
                    max_tokens=1500,
                )
                return message.choices[0].message.content.strip()
            except Exception as e:
                raise Exception(f"Groq API error: {str(e)}")

        raise Exception("No LLM backend available for synthesis")

    def _call_gemini_synthesis(self, system_prompt: str, user_prompt: str) -> str:
        """Call Gemini with system instruction + user prompt for synthesis."""
        try:
            import google.generativeai as genai
            # Use system instruction for the system prompt
            model = genai.GenerativeModel(
                "gemini-2.5-flash",
                system_instruction=system_prompt,
            )
            response = model.generate_content(
                user_prompt,
                generation_config={
                    "temperature": 0.4,
                    "max_output_tokens": 3000,
                },
            )
            return response.text.strip()
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    def summarize_commits_batch(self, commits: list[dict], max_commits: Optional[int] = None) -> list[dict]:
        """
        Summarize multiple commits.

        Args:
            commits: List of commit dicts from extract_commits()
            max_commits: Max number to process (for testing). None = all

        Returns:
            List of summary dicts with status info
        """
        summaries = []
        total = min(len(commits), max_commits) if max_commits else len(commits)

        for idx, commit in enumerate(commits[:total], 1):
            print(f"  [{idx}/{total}] Summarizing {commit['hash'][:8]} - {commit['message'][:50]}...")
            summary = self.summarize_commit(commit)
            summaries.append(summary)

        return summaries
