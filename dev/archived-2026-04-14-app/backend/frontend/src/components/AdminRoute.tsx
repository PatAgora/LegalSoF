import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

interface AdminRouteProps {
  children: React.ReactNode
}

// Route guard for admin-only pages (Configuration, Compliance, RCA).
// Defence-in-depth on the client - the backend enforces the role on
// the API itself; this just keeps the pages out of the non-admin UI.
export default function AdminRoute({ children }: AdminRouteProps) {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  if (String(user?.role || '').toLowerCase() !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
