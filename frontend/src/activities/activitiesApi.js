import apiClient from '../api/client'

export const activitiesApi = {
  list: (groupId, params) => apiClient.get(`/groups/${groupId}/activity`, { params }),
}
