import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { groupInsightsBySection } from '../lib/insightSections'
import type { InsightsResponse, InsightSummary } from '../lib/types'

const SEVERITY_STYLES: Record<string, string> = {
  high: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  low: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  info: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
}

function severityStyle(severity: string) {
  return SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.info
}

export function Insights() {
  const [insights, setInsights] = useState<InsightSummary[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dismissingId, setDismissingId] = useState<string | null>(null)

  const loadInsights = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiFetch<InsightsResponse>('/api/insights')
      setInsights(response.insights)
    } catch {
      setError('Could not load insights. Is the API running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadInsights()
  }, [loadInsights])

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const response = await apiFetch<InsightsResponse>('/api/insights/generate', {
        method: 'POST',
      })
      setInsights(response.insights)
    } catch {
      setError('Could not generate insights. Try again.')
    } finally {
      setGenerating(false)
    }
  }

  const handleDismiss = async (id: string) => {
    setDismissingId(id)
    try {
      await apiFetch(`/api/insights/${id}/dismiss`, { method: 'POST' })
      setInsights((current) => current?.filter((insight) => insight.id !== id) ?? current)
    } catch {
      setError('Could not dismiss that insight. Try again.')
    } finally {
      setDismissingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <button
          type="button"
          disabled={generating}
          onClick={() => void handleGenerate()}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
        >
          {generating ? 'Generating…' : 'Generate insights'}
        </button>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading insights…</p>
      ) : !insights || insights.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-gray-300 py-24 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">No insights right now.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {groupInsightsBySection(insights).map(([section, sectionInsights]) => (
            <section key={section}>
              <h2 className="mb-3 text-sm font-medium text-gray-500 dark:text-gray-400">
                {section}
              </h2>
              <div className="space-y-3">
                {sectionInsights.map((insight) => (
                  <div
                    key={insight.id}
                    className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${severityStyle(insight.severity)}`}
                        >
                          {insight.severity}
                        </span>
                        {insight.category && (
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                            {insight.category}
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        disabled={dismissingId === insight.id}
                        onClick={() => void handleDismiss(insight.id)}
                        className="text-xs font-medium text-gray-400 hover:text-gray-700 disabled:opacity-40 dark:hover:text-gray-200"
                      >
                        Dismiss
                      </button>
                    </div>
                    <h3 className="mt-3 text-sm font-semibold text-gray-900 dark:text-gray-50">
                      {insight.title}
                    </h3>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
                      {insight.description}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
