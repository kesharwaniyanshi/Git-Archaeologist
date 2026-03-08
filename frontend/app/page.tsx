'use client'

import { useState } from 'react'
import SearchInterface from '@/components/SearchInterface'
import ResultsView from '@/components/ResultsView'
import Header from '@/components/Header'

export default function Home() {
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <Header />
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <SearchInterface 
          onResults={setResults}
          onLoading={setLoading}
          onError={setError}
        />
        {loading && (
          <div className="mt-8 text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-400"></div>
            <p className="mt-4 text-gray-300">Analyzing repository...</p>
          </div>
        )}
        {error && (
          <div className="mt-8 bg-red-900/20 border border-red-500 rounded-lg p-4">
            <p className="text-red-300">{error}</p>
          </div>
        )}
        {results && !loading && <ResultsView results={results} />}
      </div>
    </main>
  )
}
