"""
Summarizer - Generate AI summaries of commits using Groq API.
Converts raw code changes into natural language explanations of intent.
"""

import os
import json
from typing import Optional

try:
    from groq import Groq
except ImportError:
    raise ImportError("groq not installed. Run: pip install groq")

from .diff_processor import extract_diff_summary, format_diff_for_llm


class CommitSummarizer:
    """
    Summarizes commits using Groq's free API.
    Handles API errors gracefully with fallback strategies.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the summarizer with Groq API key.
        
        Args:
            api_key: Groq API key. If None, reads from GROQ_API_KEY env var.
        
        Raises:
            ValueError: If no API key is found
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "No Groq API key found. Set GROQ_API_KEY env var or pass api_key arg. "
                "Get a free key at https://console.groq.com"
            )
        
        self.client = Groq(api_key=self.api_key)
        # Using llama model (more capable, free tier available)
        self.model = "llama-3.3-70b-versatile"
    
    def summarize_commit(self, commit: dict) -> dict:
        """
        Generate a summary for a single commit.
        
        Args:
            commit: Commit dict from extract_commits() with:
                   - hash: commit SHA
                   - message: commit message
                   - author: committer name
                   - files_changed: list of modified files with diffs
        
        Returns:
            Dictionary with:
            - hash: original commit hash
            - message: original commit message
            - summary: AI-generated summary (1-2 sentences)
            - status: "success" or "error"
            - error: error message if status is "error"
        """
        result = {
            "hash": commit["hash"],
            "message": commit["message"],
            "summary": None,
            "status": "error",
            "error": None,
        }
        
        try:
            # Extract structured info from diffs
            diff_summary = extract_diff_summary(commit["files_changed"])
            
            # Build LLM prompt
            prompt = self._build_prompt(commit, diff_summary)
            
            # Call Groq API
            summary_text = self._call_groq(prompt)
            
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
        """
        Build a focused prompt for the LLM with context.
        
        Args:
            commit: Commit dictionary
            diff_summary: Structured diff information
        
        Returns:
            Formatted prompt string
        """
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
    
    def _call_groq(self, prompt: str) -> str:
        """
        Call Groq API and extract the summary.
        
        Args:
            prompt: The prompt to send to the LLM
        
        Returns:
            Generated summary text
        
        Raises:
            Exception: If API call fails
        """
        try:
            message = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                temperature=0.3,  # Lower temp = more focused, less creative (good for this task)
                max_tokens=200,   # Keep summaries short
            )
            
            summary = message.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")

    def _call_groq_synthesis(self, system_prompt: str, user_prompt: str) -> str:
        """Call Groq with system+user roles and higher token limit for answer synthesis."""
        try:
            message = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
                temperature=0.4,
                max_tokens=1000,
            )
            return message.choices[0].message.content.strip()
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")
    
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
