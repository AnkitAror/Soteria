import { useEffect, useState } from 'react'
import { usePlaidLink, type PlaidLinkOnSuccess } from 'react-plaid-link'
import { apiFetch } from '../lib/api'

export function RelinkButton({
  institutionId,
  onRelinked,
}: {
  institutionId: string
  onRelinked: () => void
}) {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ link_token: string }>(`/api/institutions/${institutionId}/relink-token`, {
      method: 'POST',
    })
      .then((res) => setLinkToken(res.link_token))
      .catch(() => setError('Could not start relinking.'))
  }, [institutionId])

  const onSuccess: PlaidLinkOnSuccess = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/institutions/${institutionId}/relink-complete`, { method: 'POST' })
      onRelinked()
    } catch {
      setError('Relinked with your bank, but could not confirm it here. Try refreshing.')
    } finally {
      setBusy(false)
    }
  }

  const { open, ready } = usePlaidLink({
    token: linkToken ?? '',
    onSuccess,
  })

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        disabled={!ready || busy}
        onClick={() => open()}
        className="rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-500 disabled:opacity-50"
      >
        {busy ? 'Relinking…' : 'Relink'}
      </button>
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
