import apiClient from '../api/client'

export const settlementsApi = {
  create: (groupId, settlement) => apiClient.post(`/groups/${groupId}/settlements`, settlement),
  list: (groupId) => apiClient.get(`/groups/${groupId}/settlements`),
  balances: (groupId) => apiClient.get(`/groups/${groupId}/balances`),
}
