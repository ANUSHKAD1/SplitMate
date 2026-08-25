import { createContext, useContext, useMemo, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('splitmate_user')
    return savedUser ? JSON.parse(savedUser) : null
  })
  const value = useMemo(() => ({
    user,
    isAuthenticated: Boolean(user),
    signIn: (nextUser) => { localStorage.setItem('splitmate_user', JSON.stringify(nextUser)); setUser(nextUser) },
    signOut: () => { localStorage.removeItem('splitmate_user'); setUser(null) },
  }), [user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}
