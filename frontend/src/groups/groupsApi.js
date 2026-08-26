import apiClient from '../api/client'

export const groupsApi = {
  list: () => apiClient.get('/groups'),
  create: (name) => apiClient.post('/groups', { name }),
  get: (groupId) => apiClient.get(`/groups/${groupId}`),
  addMember: (groupId, email) => apiClient.post(`/groups/${groupId}/members`, { email }),
  removeMember: (groupId, userId) => apiClient.delete(`/groups/${groupId}/members/${userId}`),
}
