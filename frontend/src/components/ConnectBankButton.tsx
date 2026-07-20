import { useEffect, useState } from 'react'
import { usePlaidLink, type PlaidLinkOnSuccess } from 'react-plaid-link'
import { apiFetch } from '../lib/api'

interface ExchangeResponse {
  plaid_item_id: string
  item_id: string
  status: string
}

export function ConnectBankButton({ onConnected }: { onConnected: () => void }) {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ link_token: string }>('/api/plaid/link-token', { method: 'POST' })
      .then((res) => setLinkToken(res.link_token))
      .catch(() => setError('Could not start bank connection.'))
  }, [])

  const onSuccess: PlaidLinkOnSuccess = async (publicToken, metadata) => {
    setBusy(true)
    setError(null)
    try {
      const exchanged = await apiFetch<ExchangeResponse>('/api/plaid/exchange', {
        method: 'POST',
        body: JSON.stringify({
          public_token: publicToken,
          institution_id: metadata.institution?.institution_id ?? '',
          institution_name: metadata.institution?.name ?? '',
        }),
      })
      await apiFetch('/api/plaid/accounts', {
        method: 'POST',
        body: JSON.stringify({ plaid_item_id: exchanged.plaid_item_id }),
      })
      await apiFetch('/api/plaid/transactions/sync', {
        method: 'POST',
        body: JSON.stringify({ plaid_item_id: exchanged.plaid_item_id }),
      })
      onConnected()
    } catch {
      setError('Connected to your bank, but syncing failed. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const { open, ready } = usePlaidLink({
    token: linkToken ?? '',
    onSuccess,
  })

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        disabled={!ready || busy}
        onClick={() => open()}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
      >
        {busy ? 'Connecting…' : 'Connect a bank'}
      </button>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
