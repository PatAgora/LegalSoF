import { Outlet, Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useCurrentMatter } from '../stores/currentMatterStore'
import { API_BASE_URL, authFetch } from '../lib/api'

interface NotificationItem {
  id: number
  type: string
  title: string
  message: string
  matter_id: number | null
  read: boolean
  created_at: string | null
}

// Sidebar links table — primary navigation lives here.
const NAV_LINKS: { href: string; label: string }[] = [
  { href: '/', label: 'Dashboard' },
  { href: '/matters', label: 'Matters' },
]

// Tabs shown in the sidebar when the user is INSIDE a matter. Each
// links via ?tab=<id> on the current matter URL so the tab choice is
// reflected in the address bar (bookmarkable, refresh-safe).
const MATTER_TABS: { id: string; label: string }[] = [
  { id: 'sof-assessment', label: 'SoF Assessment' },
  { id: 'transactions',   label: 'Transaction Review' },
  { id: 'funds-lineage',  label: 'Funds Lineage' },
  { id: 'verification',   label: 'Verification' },
  { id: 'audit-trail',    label: 'Audit Trail' },
]

function SidebarLink({ href, label, currentPath, onClick }: {
  href: string;
  label: string;
  currentPath: string;
  onClick?: () => void;
}) {
  const isActive = href === '/' ? currentPath === '/' : currentPath === href || currentPath.startsWith(href + '/')
  // Slightly thinner / smaller type than the SaaS default — reads more
  // premium, more legal-journal.
  const baseCls = 'pl-6 pr-4 py-2 text-[13px] transition-colors'
  const stateCls = isActive
    ? 'bg-zinc-100 text-zinc-900 font-medium border-l-2 border-zinc-900 -ml-px'
    : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 font-normal border-l-2 border-transparent -ml-px'
  return (
    <Link to={href} onClick={onClick} className={`${baseCls} ${stateCls}`}>
      {label}
    </Link>
  )
}

// Sidebar tab link for the in-matter view. Activity tracked by ?tab=
// search param; falls back to "sof-assessment" if no tab in URL.
function MatterTabLink({ tabId, label, activeTab, matterId, onClick }: {
  tabId: string;
  label: string;
  activeTab: string;
  matterId: number;
  onClick?: () => void;
}) {
  const isActive = activeTab === tabId
  const baseCls = 'pl-6 pr-4 py-2 text-[13px] transition-colors'
  const stateCls = isActive
    ? 'bg-zinc-100 text-zinc-900 font-medium border-l-2 border-zinc-900 -ml-px'
    : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 font-normal border-l-2 border-transparent -ml-px'
  return (
    <Link to={`/matters/${matterId}?tab=${tabId}`} onClick={onClick} className={`${baseCls} ${stateCls}`}>
      {label}
    </Link>
  )
}

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { user, logout } = useAuthStore()
  const currentMatter = useCurrentMatter((s) => s.matter)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false) // mobile drawer
  const dropdownRef = useRef<HTMLDivElement>(null)
  const activeTab = searchParams.get('tab') || 'sof-assessment'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Close sidebar / dropdown on route change
  useEffect(() => {
    setSidebarOpen(false)
    setShowDropdown(false)
  }, [location.pathname])

  // Fetch unread count on mount and periodically
  useEffect(() => {
    const fetchUnreadCount = async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/v1/notifications/unread-count`)
        if (res.ok) {
          const data = await res.json()
          setUnreadCount(data.unread_count || 0)
        }
      } catch {
        /* notifications are non-critical */
      }
    }
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  // Fetch notification list when dropdown opens
  useEffect(() => {
    if (!showDropdown) return
    const fetchNotifications = async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/v1/notifications?limit=20`)
        if (res.ok) setNotifications(await res.json())
      } catch {/* */}
    }
    fetchNotifications()
  }, [showDropdown])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleMarkAllRead = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/notifications/read-all`, { method: 'PATCH' })
      if (res.ok) {
        setUnreadCount(0)
        setNotifications(prev => prev.map(n => ({ ...n, read: true })))
      }
    } catch {/* */}
  }

  const handleNotificationClick = async (notification: NotificationItem) => {
    if (!notification.read) {
      try {
        await authFetch(`${API_BASE_URL}/api/v1/notifications/${notification.id}/read`, { method: 'PATCH' })
        setUnreadCount(prev => Math.max(0, prev - 1))
        setNotifications(prev => prev.map(n => n.id === notification.id ? { ...n, read: true } : n))
      } catch {/* */}
    }
    if (notification.matter_id) {
      setShowDropdown(false)
      navigate(`/matters/${notification.matter_id}`)
    }
  }

  const formatTimeAgo = (dateStr: string | null) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    return `${Math.floor(diffHours / 24)}d ago`
  }

  const SidebarBody = (
    <>
      {/* Sidebar header — wordmark in serif, like a masthead. Hidden
          when we're inside a matter so the matter reference becomes
          the title instead. */}
      {!currentMatter && (
        <div className="flex items-center h-16 px-6 border-b border-zinc-200">
          <Link to="/" className="flex items-baseline" onClick={() => setSidebarOpen(false)}>
            <span className="font-serif text-2xl font-medium text-zinc-900">Agora</span>
          </Link>
        </div>
      )}

      {currentMatter ? (
        <>
          {/* Matter context header — reference + client */}
          <div className="px-6 pt-5 pb-4 border-b border-zinc-200">
            <Link
              to="/matters"
              onClick={() => setSidebarOpen(false)}
              className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-700 mb-2 transition-colors"
            >
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              All matters
            </Link>
            <div className="font-serif text-xl font-medium text-zinc-900 leading-tight truncate" title={currentMatter.reference_number ?? ''}>
              {currentMatter.reference_number || `Matter #${currentMatter.id}`}
            </div>
            {currentMatter.client_name && (
              <div className="mt-1 text-xs text-zinc-500 truncate" title={currentMatter.client_name}>
                {currentMatter.client_name}
              </div>
            )}
          </div>

          <div className="px-6 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-400">
            Matter
          </div>
          <div className="flex flex-col">
            {MATTER_TABS.map(tab => (
              <MatterTabLink
                key={tab.id}
                tabId={tab.id}
                label={tab.label}
                activeTab={activeTab}
                matterId={currentMatter.id}
                onClick={() => setSidebarOpen(false)}
              />
            ))}
          </div>
        </>
      ) : (
        <>
          {/* Workspace section — primary app nav */}
          <div className="px-6 pt-5 pb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-400">
            Workspace
          </div>
          <div className="flex flex-col">
            {NAV_LINKS.map(link => (
              <SidebarLink
                key={link.href}
                href={link.href}
                label={link.label}
                currentPath={location.pathname}
                onClick={() => setSidebarOpen(false)}
              />
            ))}
          </div>
        </>
      )}

      {/* Footer — user + logout, sticks to bottom */}
      {user && (
        <div className="mt-auto border-t border-zinc-200 px-6 py-4 text-[11px] text-zinc-500">
          <div className="font-medium text-zinc-700 truncate text-[12px]">{user.full_name || user.email}</div>
          <button
            onClick={handleLogout}
            className="mt-3 text-zinc-500 hover:text-zinc-900 transition-colors underline-offset-2 hover:underline"
          >
            Logout
          </button>
        </div>
      )}
    </>
  )

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Desktop sidebar — persistent on md+ */}
      <aside className="hidden md:flex md:flex-col md:w-64 md:fixed md:inset-y-0 md:left-0 bg-white border-r border-zinc-200 overflow-y-auto">
        {SidebarBody}
      </aside>

      {/* Mobile drawer overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 w-64 bg-white border-r border-zinc-200 z-50 transform transition-transform duration-200 ease-in-out md:hidden flex flex-col ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {SidebarBody}
      </aside>

      {/* Content area — offset by sidebar width on md+ */}
      <div className="flex-1 md:ml-64 flex flex-col min-w-0">
        {/* Slim top bar — hamburger on mobile + notification bell on the right */}
        <header className="bg-white border-b border-zinc-200 h-14 flex items-center justify-between px-4 sm:px-6 lg:px-8">
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden p-2 rounded text-zinc-600 hover:bg-zinc-100"
            aria-label="Open navigation"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div className="hidden md:block" />

          {user && (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setShowDropdown(prev => !prev)}
                className="relative p-2 rounded text-zinc-500 hover:text-zinc-900 hover:bg-zinc-50 transition-colors"
                aria-label="Notifications"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                    d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center h-4 min-w-[1rem] px-1 text-[10px] font-bold text-white bg-zinc-900 rounded-full">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>

              {showDropdown && (
                <div className="absolute right-0 mt-2 w-80 bg-white rounded-md shadow-lg border border-zinc-200 z-50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100">
                    <h3 className="text-sm font-semibold text-zinc-900">Notifications</h3>
                    {unreadCount > 0 && (
                      <button
                        onClick={handleMarkAllRead}
                        className="text-xs text-zinc-700 hover:text-zinc-900 font-medium underline-offset-2 hover:underline"
                      >
                        Mark all as read
                      </button>
                    )}
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {notifications.length === 0 ? (
                      <div className="px-4 py-8 text-center text-sm text-zinc-400">No notifications</div>
                    ) : (
                      notifications.map(n => (
                        <button
                          key={n.id}
                          onClick={() => handleNotificationClick(n)}
                          className={`w-full text-left px-4 py-3 border-b border-zinc-100 hover:bg-zinc-50 transition-colors ${
                            !n.read ? 'bg-zinc-50' : ''
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            {!n.read && (
                              <span className="mt-1.5 flex-shrink-0 h-2 w-2 rounded-full bg-zinc-900"></span>
                            )}
                            <div className={!n.read ? '' : 'ml-4'}>
                              <p className="text-sm font-medium text-zinc-900 truncate">{n.title}</p>
                              <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{n.message}</p>
                              <p className="text-xs text-zinc-400 mt-1">{formatTimeAgo(n.created_at)}</p>
                            </div>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </header>

        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
