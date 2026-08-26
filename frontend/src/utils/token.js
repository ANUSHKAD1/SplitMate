export function getTokenSubject(accessToken) {
  try {
    const payload = accessToken?.split('.')[1]
    if (!payload) return null
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    return Number.isInteger(Number(decoded.sub)) ? Number(decoded.sub) : null
  } catch {
    return null
  }
}
