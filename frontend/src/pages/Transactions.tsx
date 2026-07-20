import { Fragment, useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { formatCurrency } from '../lib/format'
import type { TransactionListItem, TransactionsResponse } from '../lib/types'

const PAGE_SIZE = 50

function formatScore(score: string | null) {
  return score !== null ? Number(score).toFixed(2) : '—'
}

export function Transactions() {
  const [items, setItems] = useState<TransactionListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const loadTransactions = useCallback(async (currentOffset: number) => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiFetch<TransactionsResponse>(
        `/api/transactions?limit=${PAGE_SIZE}&offset=${currentOffset}`,
      )
      setItems(response.items)
      setTotal(response.total)
    } catch {
      setError('Could not load transactions. Is the API running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadTransactions(offset)
  }, [offset, loadTransactions])

  if (loading && items === null) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Loading transactions…</p>
  }

  if (error) {
    return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
  }

  if (!items || items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-gray-300 py-24 dark:border-gray-700">
        <p className="text-sm text-gray-500 dark:text-gray-400">No transactions yet.</p>
      </div>
    )
  }

  const hasPrev = offset > 0
  const hasNext = offset + PAGE_SIZE < total

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-400 dark:border-gray-800">
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const expanded = expandedId === item.id
              return (
                <Fragment key={item.id}>
                  <tr
                    onClick={() => setExpandedId(expanded ? null : item.id)}
                    className="cursor-pointer border-b border-gray-100 last:border-0 hover:bg-gray-50 dark:border-gray-800/60 dark:hover:bg-gray-800/50"
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-gray-500 dark:text-gray-400">
                      {item.transaction_date}
                    </td>
                    <td className="px-4 py-3 text-gray-900 dark:text-gray-50">
                      {item.merchant_name ?? item.description}
                      {item.pending && (
                        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                          Pending
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {item.category ?? '—'}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-medium ${Number(item.amount) > 0 ? 'text-gray-900 dark:text-gray-50' : 'text-green-600 dark:text-green-400'}`}
                    >
                      {Number(item.amount) > 0 ? '−' : '+'}
                      {formatCurrency(String(Math.abs(Number(item.amount))), item.currency)}
                    </td>
                  </tr>
                  {expanded && (
                    <tr className="border-b border-gray-100 bg-gray-50 dark:border-gray-800/60 dark:bg-gray-800/30">
                      <td colSpan={4} className="px-4 py-4">
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                              Anomaly score
                            </p>
                            <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-50">
                              {item.analysis ? formatScore(item.analysis.anomaly_score) : 'Not yet analyzed'}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                              Behavioral score
                            </p>
                            <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-50">
                              {item.analysis
                                ? formatScore(item.analysis.behavioral_score)
                                : 'Not yet analyzed'}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                              Subscription
                            </p>
                            <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-50">
                              {item.analysis?.is_subscription ? 'Yes' : 'No'}
                            </p>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
        <span>
          {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!hasPrev}
            onClick={() => setOffset(Math.max(offset - PAGE_SIZE, 0))}
            className="rounded-md border border-gray-200 px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!hasNext}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="rounded-md border border-gray-200 px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
