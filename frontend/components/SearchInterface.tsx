'use client'

import { useState } from 'react'
import { analyzeQuery } from '@/lib/api'

interface SearchInterfaceProps {
  onResults: (results: any) => void
  onLoading: (loading: boolean) => void
  onError: (error: string | null) => void
}

export default function SearchInterface({ onResults, onLoading, onError }: SearchInterfaceProps) {
  const [query, setQuery] = useState('')
  const [repoPath, setRepoPath] = useState('/Users/yanshikesharwani/vscode/Git Archaeologist')
  const [topK, setTopK] = useState(5)
  const [maxCommits, setMaxCommits] = useState(500)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) {
      onError('Please enter a question')
      return
    }

    onLoading(true)
    onError(null)
    onResults(null)

    try {
      const data = await analyzeQuery({
        repo_path: repoPath,
        query: query,
        top_k: topK,
        max_commits: maxCommits,
      })
      onResults(data)
    } catch (err: any) {
      onError(err.message || 'Failed to analyze repository')
    } finally {
      onLoading(false)
    }
  }

  return (
    <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 shadow-2xl border border-gray-700">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Repository Path
          </label>
          <input
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            className="w-full px-4 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="/path/to/your/repo"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Your Question
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            className="w-full px-4 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
            placeholder="Why was authentication changed? What caused the performance improvement?"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Top Results
            </label>
            <input
              type="number"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value))}
              min={1}
              max={20}
              className="w-full px-4 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Max Commits
            </label>
            <input
              type="number"
              value={maxCommits}
              onChange={(e) => setMaxCommits(parseInt(e.target.value))}
              min={10}
              max={10000}
              className="w-full px-4 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        <button
          type="submit"
          className="w-full bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white font-semibold py-3 px-6 rounded-lg transition-all duration-200 shadow-lg hover:shadow-primary-500/50"
        >
          🔍 Analyze Repository
        </button>
      </form>
    </div>
  )
}
