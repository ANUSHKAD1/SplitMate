import axios from 'axios'

const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']
const REFRESH_TOKEN_KEY = 'splitmate_refresh_token'

let accessToken = null
let refreshPromise = null
let authFailureHandler = () => window.location.assign('/login')
const accessTokenListeners = new Set()

function notifyAccessTokenListeners() {
  accessTokenListeners.forEach((listener) => listener(accessToken))
}

function isAuthEndpoint(url = '') {
  const pathname = String(url).split('?')[0]
  return AUTH_ENDPOINTS.some((endpoint) => pathname.endsWith(endpoint))
}

function getRefreshToken() {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY)
}

export function getAccessToken() {
  return accessToken
}

export function subscribeToAccessToken(listener) {
  accessTokenListeners.add(listener)
  return () => accessTokenListeners.delete(listener)
}

export function setAuthTokens(tokens) {
  const { access_token: nextAccessToken, refresh_token: nextRefreshToken } = tokens
  if (!nextAccessToken || !nextRefreshToken) {
    throw new Error('The authentication response did not include both tokens.')
  }

  // Store the rotated refresh token before exposing its matching access token.
  sessionStorage.setItem(REFRESH_TOKEN_KEY, nextRefreshToken)
  accessToken = nextAccessToken
  notifyAccessTokenListeners()
}

export function clearAuthTokens() {
  accessToken = null
  sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  notifyAccessTokenListeners()
}

export function setAuthFailureHandler(handler) {
  authFailureHandler = handler
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  headers: { 'Content-Type': 'application/json' },
})

const refreshClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  headers: { 'Content-Type': 'application/json' },
})

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshToken = getRefreshToken()
      if (!refreshToken) throw new Error('No refresh token is available.')

      const response = await refreshClient.post('/auth/refresh', { refresh_token: refreshToken })
      setAuthTokens(response.data)
      return response.data.access_token
    })()
      .catch((error) => {
        clearAuthTokens()
        authFailureHandler()
        throw error
      })
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

export function restoreSession() {
  return getRefreshToken() ? refreshAccessToken() : Promise.resolve(null)
}

apiClient.interceptors.request.use((config) => {
  if (!isAuthEndpoint(config.url) && accessToken) {
    config.headers = { ...config.headers, Authorization: `Bearer ${accessToken}` }
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const hasAuthorization = Boolean(
      originalRequest?.headers?.Authorization || originalRequest?.headers?.get?.('Authorization'),
    )

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      !hasAuthorization ||
      isAuthEndpoint(originalRequest.url)
    ) {
      return Promise.reject(error)
    }

    originalRequest._retry = true

    try {
      const nextAccessToken = await refreshAccessToken()
      originalRequest.headers = {
        ...originalRequest.headers,
        Authorization: `Bearer ${nextAccessToken}`,
      }
      return apiClient(originalRequest)
    } catch (refreshError) {
      return Promise.reject(refreshError)
    }
  },
)

export default apiClient
