import { useCallback, useEffect, useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ConnectBankButton } from '../components/ConnectBankButton'
import { apiFetch } from '../lib/api'
import { formatCurrency } from '../lib/format'
import type {
  AccountsResponse,
  BankAccountSummary,
  SpendingByCategoryResponse,
  SpendingSummaryResponse,
} from '../lib/types'

const CATEGORY_COLORS = [
  '#6366f1',
  '#22c55e',
  '#f59e0b',
  '#ef4444',
  '#06b6d4',
  '#a855f7',
  '#ec4899',
  '#84cc16',
]

function groupByType(accounts: BankAccountSummary[]) {
  const groups = new Map<string, BankAccountSummary[]>()
  for (const account of accounts) {
    const key = account.account_type
    groups.set(key, [...(groups.get(key) ?? []), account])
  }
  return groups
}

export function Dashboard() {
  const [accounts, setAccounts] = useState<BankAccountSummary[] | null>(null)
  const [spendingSummary, setSpendingSummary] = useState<SpendingSummaryResponse | null>(null)
  const [spendingByCategory, setSpendingByCategory] = useState<SpendingByCategoryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [accountsRes, summaryRes, categoryRes] = await Promise.all([
        apiFetch<AccountsResponse>('/api/accounts'),
        apiFetch<SpendingSummaryResponse>('/api/dashboard/spending-summary'),
        apiFetch<SpendingByCategoryResponse>('/api/dashboard/spending-by-category'),
      ])
      setAccounts(accountsRes.accounts)
      setSpendingSummary(summaryRes)
      setSpendingByCategory(categoryRes)
    } catch {
      setError('Could not load your dashboard. Is the API running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDashboard()
  }, [loadDashboard])

  if (loading) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Loading dashboard…</p>
  }

  if (error) {
    return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
  }

  if (!accounts || accounts.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-gray-300 py-24 dark:border-gray-700">
        <p className="text-sm text-gray-500 dark:text-gray-400">No bank accounts connected yet.</p>
        <ConnectBankButton onConnected={() => void loadDashboard()} />
      </div>
    )
  }

  const grouped = groupByType(accounts)
  const percentChange = spendingSummary?.percent_change ?? null

  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 text-sm font-medium text-gray-500 dark:text-gray-400">Account summary</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...grouped.entries()].map(([type, typeAccounts]) => (
            <div
              key={type}
              className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{type}</p>
              <div className="mt-2 space-y-2">
                {typeAccounts.map((account) => (
                  <div key={account.id} className="flex items-baseline justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-300">{account.account_name}</span>
                    <span className="text-sm font-semibold text-gray-900 dark:text-gray-50">
                      {account.current_balance !== null
                        ? formatCurrency(account.current_balance, account.currency)
                        : '—'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">Monthly spending</h2>
          {spendingSummary ? (
            <>
              <p className="mt-2 text-3xl font-semibold text-gray-900 dark:text-gray-50">
                {formatCurrency(spendingSummary.total_spend)}
              </p>
              {percentChange !== null && (
                <p
                  className={`mt-1 text-sm font-medium ${percentChange >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}
                >
                  {percentChange >= 0 ? '+' : ''}
                  {percentChange.toFixed(1)}% vs last month
                </p>
              )}
            </>
          ) : (
            <p className="mt-2 text-sm text-gray-400">No data yet.</p>
          )}
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">Spending by category</h2>
          {spendingByCategory && spendingByCategory.categories.length > 0 ? (
            <div className="mt-2 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={spendingByCategory.categories}
                    dataKey={(entry) => Number(entry.total)}
                    nameKey="category"
                    innerRadius={50}
                    outerRadius={80}
                  >
                    {spendingByCategory.categories.map((entry, index) => (
                      <Cell key={entry.category} fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => formatCurrency(String(value))} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="mt-2 text-sm text-gray-400">No categorized spending this month yet.</p>
          )}
        </div>
      </section>
    </div>
  )
}
