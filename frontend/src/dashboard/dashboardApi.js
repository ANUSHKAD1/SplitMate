import apiClient from '../api/client'

export function getDashboard() {
  return apiClient.get('/dashboard')
}
