import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import { useAuthStore } from '../stores/authStore'
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

function SidebarLink({ href, label, currentPath, onClick }: {
  href: string;
  label: string;
  currentPath: string;
  onClick?: () => void;
}) {
  const isActive = href === '/' ? currentPath === '/' : currentPath === href || currentPath.startsWith(href + '/')
  const baseCls = 'px-4 py-2 text-sm font-medium transition-colors'
  const stateCls = isActive
    ? 'bg-zinc-100 text-zinc-900 border-l-2 border-zinc-900'
    : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 border-l-2 border-transparent'
  return (
    <Link to={href} onClick={onClick} className={`${baseCls} ${stateCls}`}>
      {label}
    </Link>
  )
}

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false) // mobile drawer
  const dropdownRef = useRef<HTMLDivElement>(null)

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
      {/* Sidebar header — wordmark */}
      <div className="flex items-center h-16 px-4 border-b border-zinc-200">
        <Link to="/" className="flex items-baseline gap-2" onClick={() => setSidebarOpen(false)}>
          <span className="text-xl font-bold tracking-tight text-zinc-900">Agora</span>
        </Link>
      </div>

      {/* Primary nav */}
      <div className="py-2 flex flex-col">
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

      {/* Footer — user + logout, sticks to bottom */}
      {user && (
        <div className="mt-auto border-t border-zinc-200 px-4 py-3 text-xs text-zinc-500">
          <div className="font-medium text-zinc-700 truncate">{user.full_name || user.email}</div>
          <button
            onClick={handleLogout}
            className="mt-2 text-zinc-500 hover:text-zinc-900 transition-colors underline-offset-2 hover:underline"
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
      <aside className="hidden md:flex md:flex-col md:w-60 md:fixed md:inset-y-0 md:left-0 bg-white border-r border-zinc-200 overflow-y-auto">
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
      <div className="flex-1 md:ml-60 flex flex-col min-w-0">
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
