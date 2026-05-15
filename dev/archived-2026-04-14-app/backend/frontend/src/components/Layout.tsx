import { Outlet, Link, useNavigate } from 'react-router-dom'
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

export default function Layout() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

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
        // Silently ignore - notifications are non-critical
      }
    }

    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30000) // Poll every 30s
    return () => clearInterval(interval)
  }, [])

  // Fetch notifications when dropdown is opened
  useEffect(() => {
    if (!showDropdown) return

    const fetchNotifications = async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/v1/notifications?limit=20`)
        if (res.ok) {
          const data = await res.json()
          setNotifications(data)
        }
      } catch {
        // Silently ignore
      }
    }

    fetchNotifications()
  }, [showDropdown])

  // Close dropdown when clicking outside
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
    } catch {
      // Silently ignore
    }
  }

  const handleNotificationClick = async (notification: NotificationItem) => {
    // Mark as read
    if (!notification.read) {
      try {
        await authFetch(`${API_BASE_URL}/api/v1/notifications/${notification.id}/read`, { method: 'PATCH' })
        setUnreadCount(prev => Math.max(0, prev - 1))
        setNotifications(prev => prev.map(n => n.id === notification.id ? { ...n, read: true } : n))
      } catch {
        // Silently ignore
      }
    }
    // Navigate to the related matter if available
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
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  return (
    <div className="min-h-screen bg-brand-surface">
      {/* Navigation */}
      <nav className="bg-primary-700 border-b border-primary-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-20">
            <div className="flex items-center">
              <Link to="/" className="flex items-center">
                <img src="/agora-logo.png" alt="Agora Consulting AI" className="h-12" />
              </Link>
              <div className="hidden sm:ml-10 sm:flex sm:space-x-8">
                <Link
                  to="/"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-white border-b-2 border-white"
                >
                  Dashboard
                </Link>
                <Link
                  to="/matters"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-300 hover:text-white border-b-2 border-transparent hover:border-gray-300"
                >
                  Matters
                </Link>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {user && (
                <>
                  {/* Notification Bell */}
                  <div className="relative" ref={dropdownRef}>
                    <button
                      onClick={() => setShowDropdown(prev => !prev)}
                      className="relative p-2 text-gray-300 hover:text-white transition-colors"
                      aria-label="Notifications"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                      </svg>
                      {unreadCount > 0 && (
                        <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center h-4 min-w-[1rem] px-1 text-[10px] font-bold text-white bg-primary-500 rounded-full">
                          {unreadCount > 99 ? '99+' : unreadCount}
                        </span>
                      )}
                    </button>

                    {/* Notification Dropdown */}
                    {showDropdown && (
                      <div className="absolute right-0 mt-2 w-80 bg-white rounded-card shadow-dropdown border border-brand-muted z-50 overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-brand-muted">
                          <h3 className="text-sm font-semibold text-brand-ink">Notifications</h3>
                          {unreadCount > 0 && (
                            <button
                              onClick={handleMarkAllRead}
                              className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                            >
                              Mark all as read
                            </button>
                          )}
                        </div>
                        <div className="max-h-80 overflow-y-auto">
                          {notifications.length === 0 ? (
                            <div className="px-4 py-8 text-center text-sm text-brand-ink-tertiary">
                              No notifications
                            </div>
                          ) : (
                            notifications.map(n => (
                              <button
                                key={n.id}
                                onClick={() => handleNotificationClick(n)}
                                className={`w-full text-left px-4 py-3 border-b border-brand-muted hover:bg-brand-surface-alt transition-colors ${
                                  !n.read ? 'bg-brand-surface-alt' : ''
                                }`}
                              >
                                <div className="flex items-start gap-2">
                                  {!n.read && (
                                    <span className="mt-1.5 flex-shrink-0 h-2 w-2 rounded-full bg-primary-500"></span>
                                  )}
                                  <div className={!n.read ? '' : 'ml-4'}>
                                    <p className="text-sm font-medium text-brand-ink truncate">{n.title}</p>
                                    <p className="text-xs text-brand-ink-tertiary mt-0.5 line-clamp-2">{n.message}</p>
                                    <p className="text-xs text-brand-ink-tertiary mt-1">{formatTimeAgo(n.created_at)}</p>
                                  </div>
                                </div>
                              </button>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  <span className="text-sm text-gray-300">{user.full_name || user.email}</span>
                  <button
                    onClick={handleLogout}
                    className="text-sm text-brand-ink-tertiary hover:text-white transition-colors"
                  >
                    Logout
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
