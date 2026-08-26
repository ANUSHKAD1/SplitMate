import apiClient from '../api/client'

const dashboardListeners = new Set()
let dashboardRefreshPromise = null

export function getDashboard() {
  return apiClient.get('/dashboard')
}

export function subscribeToDashboard(listener) {
  dashboardListeners.add(listener)
  return () => dashboardListeners.delete(listener)
}

export async function refreshDashboard() {
  if (!dashboardRefreshPromise) {
    dashboardRefreshPromise = getDashboard()
      .then((response) => {
        dashboardListeners.forEach((listener) => listener(response.data))
        return response.data
      })
      .finally(() => {
        dashboardRefreshPromise = null
      })
  }

  return dashboardRefreshPromise
}
