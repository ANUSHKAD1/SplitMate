import apiClient from './client'

export const authApi = {
  login: (credentials) => apiClient.post('/auth/login', credentials),
  register: (registration) => apiClient.post('/auth/register', registration),
  logout: (refreshToken) => apiClient.post('/auth/logout', { refresh_token: refreshToken }),
}

export function getApiErrorMessage(error, fallbackMessage) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).filter(Boolean).join(' ') || fallbackMessage
  }
  return typeof detail === 'string' ? detail : fallbackMessage
}
