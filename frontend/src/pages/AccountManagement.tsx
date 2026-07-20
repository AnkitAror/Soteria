import { useCallback, useEffect, useState } from 'react'
import { ConnectBankButton } from '../components/ConnectBankButton'
import { RelinkButton } from '../components/RelinkButton'
import { apiFetch } from '../lib/api'
import type { InstitutionsResponse, InstitutionSummary } from '../lib/types'

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  login_required: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  error: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
}

const STATUS_LABELS: Record<string, string> = {
  active: 'Connected',
  login_required: 'Needs relink',
  error: 'Error',
}

export function AccountManagement() {
  const [institutions, setInstitutions] = useState<InstitutionSummary[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null)

  const loadInstitutions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiFetch<InstitutionsResponse>('/api/institutions')
      setInstitutions(response.institutions)
    } catch {
      setError('Could not load connected institutions. Is the API running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadInstitutions()
  }, [loadInstitutions])

  const handleUnlink = async (institution: InstitutionSummary) => {
    if (!window.confirm(`Unlink ${institution.institution_name}? This removes access to it.`)) {
      return
    }
    setUnlinkingId(institution.id)
    try {
      await apiFetch(`/api/institutions/${institution.id}`, { method: 'DELETE' })
      setInstitutions((current) => current?.filter((i) => i.id !== institution.id) ?? current)
    } catch {
      setError('Could not unlink that institution. Try again.')
    } finally {
      setUnlinkingId(null)
    }
  }

  if (loading) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Loading institutions…</p>
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {!institutions || institutions.length === 0 ? (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-gray-300 py-24 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">No banks connected yet.</p>
          <ConnectBankButton onConnected={() => void loadInstitutions()} />
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {institutions.map((institution) => (
              <div
                key={institution.id}
                className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900 dark:text-gray-50">
                      {institution.institution_name}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[institution.status] ?? STATUS_STYLES.error}`}
                    >
                      {STATUS_LABELS[institution.status] ?? institution.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-gray-400">
                    {institution.account_count} account{institution.account_count === 1 ? '' : 's'}
                    {institution.last_synced_at && ` · last synced ${institution.last_synced_at}`}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {institution.status === 'login_required' && (
                    <RelinkButton
                      institutionId={institution.id}
                      onRelinked={() => void loadInstitutions()}
                    />
                  )}
                  <button
                    type="button"
                    disabled={unlinkingId === institution.id}
                    onClick={() => void handleUnlink(institution)}
                    className="text-xs font-medium text-gray-400 hover:text-red-600 disabled:opacity-40 dark:hover:text-red-400"
                  >
                    Unlink
                  </button>
                </div>
              </div>
            ))}
          </div>

          <ConnectBankButton onConnected={() => void loadInstitutions()} />
        </>
      )}
    </div>
  )
}
