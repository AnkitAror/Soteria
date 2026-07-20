import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { formatCurrency } from '../lib/format'
import type { SubscriptionsResponse, SubscriptionSummary } from '../lib/types'

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  paused: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  cancelled: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
}

const BILLING_CYCLE_LABELS: Record<string, string> = {
  weekly: 'Weekly',
  biweekly: 'Biweekly',
  semi_monthly: 'Twice a month',
  monthly: 'Monthly',
  annually: 'Annually',
  unknown: 'Unknown cycle',
}

function billingCycleLabel(cycle: string) {
  return BILLING_CYCLE_LABELS[cycle] ?? cycle
}

function priceChangeLabel(amount: string | null, currency: string) {
  if (amount === null) return null
  const value = Number(amount)
  if (value === 0) return null
  const formatted = formatCurrency(String(Math.abs(value)), currency)
  return value > 0 ? `+${formatted} price increase` : `−${formatted} price decrease`
}

export function Subscriptions() {
  const [subscriptions, setSubscriptions] = useState<SubscriptionSummary[] | null>(null)
  const [totalMonthlyCost, setTotalMonthlyCost] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadSubscriptions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiFetch<SubscriptionsResponse>('/api/subscriptions')
      setSubscriptions(response.subscriptions)
      setTotalMonthlyCost(response.total_monthly_cost)
    } catch {
      setError('Could not load subscriptions. Is the API running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadSubscriptions()
  }, [loadSubscriptions])

  if (loading) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Loading subscriptions…</p>
  }

  if (error) {
    return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
  }

  if (!subscriptions || subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-gray-300 py-24 dark:border-gray-700">
        <p className="text-sm text-gray-500 dark:text-gray-400">No subscriptions detected yet.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
        <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Monthly subscription spend
        </h2>
        <p className="mt-2 text-3xl font-semibold text-gray-900 dark:text-gray-50">
          {formatCurrency(totalMonthlyCost ?? '0')}
        </p>
        <p className="mt-1 text-sm text-gray-400">Across active subscriptions only</p>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-400 dark:border-gray-800">
              <th className="px-4 py-3">Merchant</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Billing cycle</th>
              <th className="px-4 py-3">Next charge</th>
              <th className="px-4 py-3 text-right">Per charge</th>
              <th className="px-4 py-3 text-right">Monthly</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => {
              const change = priceChangeLabel(sub.last_price_change_amount, sub.currency)
              return (
                <tr
                  key={sub.id}
                  className="border-b border-gray-100 last:border-0 dark:border-gray-800/60"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 dark:text-gray-50">
                      {sub.merchant_name}
                    </div>
                    {sub.category && (
                      <div className="text-xs text-gray-400">{sub.category}</div>
                    )}
                    {change && (
                      <div
                        className={`mt-0.5 text-xs font-medium ${change.startsWith('+') ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}
                      >
                        {change}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[sub.status] ?? STATUS_STYLES.cancelled}`}
                    >
                      {sub.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {billingCycleLabel(sub.billing_cycle)}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {sub.next_expected_charge ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-900 dark:text-gray-50">
                    {formatCurrency(sub.average_cost, sub.currency)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-gray-50">
                    {formatCurrency(sub.monthly_cost, sub.currency)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
