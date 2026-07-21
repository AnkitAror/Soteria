import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const NAV_LINKS = [
  { label: 'Dashboard', to: '/' },
  { label: 'Transactions', to: '/transactions' },
  { label: 'Insights', to: '/insights' },
  { label: 'Subscriptions', to: '/subscriptions' },
  { label: 'Account Management', to: '/account' },
  { label: 'Chat', to: '/chat' },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth()

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <span className="text-lg font-semibold text-gray-900 dark:text-gray-50">Soteria</span>
            <nav className="flex gap-1">
              {NAV_LINKS.map((item) => (
                <NavLink
                  key={item.label}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm font-medium ${
                      isActive
                        ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
                        : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500 dark:text-gray-400">{user?.email}</span>
            <button
              type="button"
              onClick={() => void signOut()}
              className="text-sm font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
