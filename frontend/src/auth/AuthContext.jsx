import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import {
  clearAuthTokens,
  getAccessToken,
  restoreSession,
  setAuthFailureHandler,
  setAuthTokens,
} from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const navigate = useNavigate()
  const [accessToken, setAccessToken] = useState(getAccessToken)
  const [user, setUser] = useState(null)
  const [isRestoring, setIsRestoring] = useState(true)

  const clearAuthState = useCallback(() => {
    clearAuthTokens()
    setAccessToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setAuthFailureHandler(() => {
      clearAuthState()
      navigate('/login', { replace: true })
    })

    return () => setAuthFailureHandler(() => window.location.assign('/login'))
  }, [clearAuthState, navigate])

  useEffect(() => {
    let isMounted = true

    restoreSession()
      .then((nextAccessToken) => {
        if (isMounted && nextAccessToken) setAccessToken(nextAccessToken)
      })
      .catch(() => {
        // The shared refresh handler has already cleared state and redirected.
      })
      .finally(() => {
        if (isMounted) setIsRestoring(false)
      })

    return () => {
      isMounted = false
    }
  }, [])

  const login = useCallback(async (credentials) => {
    const response = await authApi.login(credentials)
    setAuthTokens(response.data)
    setAccessToken(response.data.access_token)
    setUser(null)
    return response.data
  }, [])

  const register = useCallback(async (registration) => {
    const response = await authApi.register(registration)
    return response.data
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = sessionStorage.getItem('splitmate_refresh_token')

    try {
      if (refreshToken) await authApi.logout(refreshToken)
    } catch {
      // Local sign-out still succeeds if the network request cannot complete.
    } finally {
      clearAuthState()
      navigate('/login', { replace: true })
    }
  }, [clearAuthState, navigate])

  const value = useMemo(() => ({
    login,
    register,
    logout,
    user,
    accessToken,
    isAuthenticated: Boolean(accessToken),
    isRestoring,
  }), [accessToken, isRestoring, login, logout, register, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}
