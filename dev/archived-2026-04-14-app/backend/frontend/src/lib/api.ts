// Resolve the API base URL.
//
// Production (single-service deploy): backend serves the frontend bundle, so
// the API lives at the SAME origin as the page — base URL must be empty so
// fetch('/api/v1/...') stays on this host.
//
// We deliberately ignore VITE_API_BASE_URL when running on a *.railway.app
// host. A previous build accidentally baked a stale separate-backend URL into
// the bundle, and env-var changes only take effect on the next rebuild —
// this guard makes the running bundle robust regardless of what was baked.
//
// Local dev still honours VITE_API_BASE_URL if you point the frontend at a
// detached backend.
function resolveApiBase(): string {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const host = window.location.hostname
    if (host.endsWith('.railway.app') || host.endsWith('.up.railway.app')) {
      return ''
    }
  }
  const envUrl = import.meta.env.VITE_API_BASE_URL
  return (envUrl && typeof envUrl === 'string') ? envUrl : ''
}

export const API_BASE_URL = resolveApiBase()

export function getAuthHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extra,
  }
  const token = localStorage.getItem('access_token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

/** Fetch wrapper that automatically adds auth headers and handles expired tokens */
export async function authFetch(url: string, options?: RequestInit): Promise<Response> {
  const token = localStorage.getItem('access_token')
  const headers = new Headers(options?.headers)
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (!headers.has('Content-Type') && options?.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(url, { ...options, headers })

  // If token expired or invalid, clear auth state and redirect to login
  if (response.status === 401) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('auth-storage')
    window.location.href = '/login'
  }

  return response
}

class ApiClient {
  async login(email: string, password: string) {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw { response: { data } }
    }
    return response.json()
  }

  async getCurrentUser() {
    const response = await authFetch(`${API_BASE_URL}/api/v1/auth/me`)
    if (!response.ok) {
      throw new Error('Failed to get current user')
    }
    return response.json()
  }
}

export const api = new ApiClient()
