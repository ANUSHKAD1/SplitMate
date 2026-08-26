import apiClient from '../api/client'

export const expensesApi = {
  create: (groupId, expense) => apiClient.post(`/groups/${groupId}/expenses`, expense),
  list: (groupId, params) => apiClient.get(`/groups/${groupId}/expenses`, { params }),
  update: (expenseId, expense) => apiClient.put(`/expenses/${expenseId}`, expense),
  remove: (expenseId) => apiClient.delete(`/expenses/${expenseId}`),
  balances: (groupId) => apiClient.get(`/groups/${groupId}/balances`),
}
