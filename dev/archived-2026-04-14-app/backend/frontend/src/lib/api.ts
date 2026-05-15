export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

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
