// API Client for AI Gateway Admin

const API_BASE = ''

class ApiClient {
    constructor() {
        this.baseUrl = API_BASE
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`
        const token = localStorage.getItem('access_token')

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        }

        if (token) {
            headers['Authorization'] = `Bearer ${token}`
        }

        const response = await fetch(url, {
            ...options,
            headers,
        })

        if (response.status === 401) {
            // Try to refresh token
            const refreshed = await this.refreshToken()
            if (refreshed) {
                // Retry request with new token
                headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`
                const retryResponse = await fetch(url, { ...options, headers })
                if (!retryResponse.ok) {
                    throw new Error('Request failed after token refresh')
                }
                return retryResponse.json()
            } else {
                localStorage.removeItem('access_token')
                localStorage.removeItem('refresh_token')
                window.location.href = '/login'
                throw new Error('Session expired')
            }
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: { message: 'Request failed' } }))
            throw new Error(error.error?.message || error.detail || 'Request failed')
        }

        return response.json()
    }

    async refreshToken() {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) return false

        try {
            const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken }),
            })

            if (response.ok) {
                const data = await response.json()
                localStorage.setItem('access_token', data.access_token)
                localStorage.setItem('refresh_token', data.refresh_token)
                return true
            }
        } catch (err) {
            console.error('Token refresh failed:', err)
        }
        return false
    }

    // Auth
    async login(username, password) {
        return this.request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        })
    }

    async getMe() {
        return this.request('/api/auth/me')
    }

    // Dashboard
    async getDashboardStats() {
        return this.request('/api/stats/dashboard')
    }

    async getUsageStats(options = {}) {
        const { period = 'daily', days = 7 } = options
        return this.request(`/api/stats/usage?period=${period}&days=${days}`)
    }

    // Providers
    async getProviders() {
        return this.request('/api/providers')
    }

    async createProvider(data) {
        return this.request('/api/providers', {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async testProvider(providerId) {
        return this.request(`/api/providers/${providerId}/test`, {
            method: 'POST',
        })
    }

    // Models
    async getModels() {
        return this.request('/api/models')
    }

    async createModel(data) {
        return this.request('/api/models', {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async testModel(modelId, prompt = 'Hello') {
        return this.request(`/api/models/${modelId}/test`, {
            method: 'POST',
            body: JSON.stringify({ prompt }),
        })
    }

    async runHealthCheck(modelId) {
        return this.request(`/api/models/${modelId}/health-check`, {
            method: 'POST',
        })
    }

    // Logs
    async getRequestLogs(params = {}) {
        const query = new URLSearchParams(params).toString()
        return this.request(`/api/logs/requests?${query}`)
    }

    async getAuditLogs(params = {}) {
        const query = new URLSearchParams(params).toString()
        return this.request(`/api/logs/audit?${query}`)
    }

    // Users
    async getUsers() {
        return this.request('/api/users')
    }

    // Organizations
    async getOrganizations() {
        return this.request('/api/organizations')
    }

    async createOrganization(data) {
        return this.request('/api/organizations', {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async getGroups(orgId) {
        return this.request(`/api/organizations/${orgId}/groups`)
    }

    async createGroup(orgId, data) {
        return this.request(`/api/organizations/${orgId}/groups`, {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    // Organization Members
    async getOrganizationMembers(orgId) {
        return this.request(`/api/organizations/${orgId}/members`)
    }

    async addMemberToOrganization(orgId, userId) {
        return this.request(`/api/organizations/${orgId}/members/${userId}`, {
            method: 'POST',
        })
    }

    async removeMemberFromOrganization(orgId, userId) {
        return this.request(`/api/organizations/${orgId}/members/${userId}`, {
            method: 'DELETE',
        })
    }

    async setMemberAdminStatus(orgId, userId, isAdmin) {
        return this.request(`/api/organizations/${orgId}/members/${userId}/admin?is_admin=${isAdmin}`, {
            method: 'PUT',
        })
    }

    // Model Access
    async getUserModels(userId) {
        return this.request(`/api/model-access/users/${userId}/models`)
    }

    async grantUserModelAccess(userId, modelId) {
        return this.request(`/api/model-access/users/${userId}/models`, {
            method: 'POST',
            body: JSON.stringify({ model_id: modelId, is_allowed: true }),
        })
    }

    async revokeUserModelAccess(userId, modelId) {
        return this.request(`/api/model-access/users/${userId}/models/${modelId}`, {
            method: 'DELETE',
        })
    }

    async getOrgModels(orgId) {
        return this.request(`/api/model-access/organizations/${orgId}/models`)
    }

    async grantOrgModelAccess(orgId, modelId) {
        return this.request(`/api/model-access/organizations/${orgId}/models`, {
            method: 'POST',
            body: JSON.stringify({ model_id: modelId, is_allowed: true }),
        })
    }

    async revokeOrgModelAccess(orgId, modelId) {
        return this.request(`/api/model-access/organizations/${orgId}/models/${modelId}`, {
            method: 'DELETE',
        })
    }

    async getMyModels() {
        return this.request(`/api/model-access/me/models`)
    }
}

export const api = new ApiClient()




