'use client'

interface Result {
  commit_hash: string
  message: string
  summary: string
  relevance_score: number
  status: string
}

interface ResultsViewProps {
  results: {
    answer?: string
    confidence?: string
    confidence_score?: number
    results?: Result[]
    metadata?: any
  }
}

export default function ResultsView({ results }: ResultsViewProps) {
  if (!results) return null

  const { answer, confidence, confidence_score, results: commits, metadata } = results

  return (
    <div className="mt-8 space-y-6">
      {/* Synthesized Answer */}
      {answer && (
        <div className="bg-gradient-to-br from-primary-900/30 to-primary-800/20 border border-primary-700/50 rounded-xl p-6 shadow-xl">
          <div className="flex items-start justify-between mb-3">
            <h2 className="text-xl font-semibold text-primary-300">📝 Answer</h2>
            {confidence && (
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                confidence === 'High' ? 'bg-green-900/50 text-green-300' :
                confidence === 'Medium' ? 'bg-yellow-900/50 text-yellow-300' :
                'bg-red-900/50 text-red-300'
              }`}>
                {confidence} Confidence {confidence_score ? `(${(confidence_score * 100).toFixed(0)}%)` : ''}
              </span>
            )}
          </div>
          <p className="text-gray-200 leading-relaxed whitespace-pre-wrap">{answer}</p>
        </div>
      )}

      {/* Metadata */}
      {metadata && (
        <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-4">
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Total Commits:</span>
              <span className="ml-2 text-gray-200 font-medium">{metadata.total_commits_indexed}</span>
            </div>
            <div>
              <span className="text-gray-400">Candidates:</span>
              <span className="ml-2 text-gray-200 font-medium">{metadata.candidates_analyzed}</span>
            </div>
            <div>
              <span className="text-gray-400">Time:</span>
              <span className="ml-2 text-gray-200 font-medium">{metadata.query_time_seconds?.toFixed(2)}s</span>
            </div>
          </div>
        </div>
      )}

      {/* Relevant Commits */}
      {commits && commits.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-300">🔎 Relevant Commits</h3>
          {commits.map((commit, idx) => (
            <div
              key={commit.commit_hash}
              className="bg-gray-800/50 border border-gray-700 rounded-lg p-5 hover:border-primary-700/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-primary-500">#{idx + 1}</span>
                  <code className="px-2 py-1 bg-gray-900/70 text-primary-400 text-xs rounded font-mono">
                    {commit.commit_hash.substring(0, 8)}
                  </code>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">Relevance</span>
                  <div className="flex items-center gap-1">
                    <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-primary-600 to-primary-400"
                        style={{ width: `${Math.min(commit.relevance_score * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-300 font-medium">
                      {(commit.relevance_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>

              <h4 className="text-gray-200 font-medium mb-2">{commit.message}</h4>
              
              {commit.summary && commit.summary !== commit.message && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-sm text-gray-400 mb-1">AI Summary:</p>
                  <p className="text-sm text-gray-300">{commit.summary}</p>
                </div>
              )}
              
              {commit.status && (
                <div className="mt-3 flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    commit.status === 'success' ? 'bg-green-900/30 text-green-400' :
                    'bg-gray-700 text-gray-400'
                  }`}>
                    {commit.status}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
