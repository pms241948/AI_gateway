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

    // PII Masking
    async getPIIConfig() {
        return this.request('/api/pii/config')
    }

    async testPIIMasking(text, language = 'en') {
        return this.request('/api/pii/test', {
            method: 'POST',
            body: JSON.stringify({ text, language }),
        })
    }

    async getPIIEntities() {
        return this.request('/api/pii/entities')
    }

    // PII Runtime Settings (Dynamic Toggle)
    async getRuntimeSettings() {
        return this.request('/api/pii/runtime-settings')
    }

    async updateRuntimeSettings(settings) {
        return this.request('/api/pii/runtime-settings', {
            method: 'PUT',
            body: JSON.stringify(settings),
        })
    }

    // PII Model Management
    async getNlpModels() {
        return this.request('/api/pii/nlp-models')
    }

    async addNlpModel(data) {
        return this.request('/api/pii/nlp-models', {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async deleteNlpModel(modelId) {
        return this.request(`/api/pii/nlp-models/${modelId}`, {
            method: 'DELETE',
        })
    }

    async toggleNlpModel(langCode) {
        return this.request(`/api/pii/nlp-models/${langCode}/toggle`, {
            method: 'POST',
        })
    }

    async getRecognizers() {
        return this.request('/api/pii/recognizers')
    }

    async createRecognizer(data) {
        return this.request('/api/pii/recognizers', {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async updateRecognizer(recognizerId, data) {
        return this.request(`/api/pii/recognizers/${recognizerId}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        })
    }

    async deleteRecognizer(recognizerId) {
        return this.request(`/api/pii/recognizers/${recognizerId}`, {
            method: 'DELETE',
        })
    }

    async testPattern(pattern, text) {
        return this.request('/api/pii/recognizers/test', {
            method: 'POST',
            body: JSON.stringify({ pattern, text }),
        })
    }

    // External PII API Endpoints
    async getPiiEndpoints() {
        return this.request('/api/pii/endpoints')
    }

    async createPiiEndpoint(data) {
        return this.request('/api/pii/endpoints', {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async updatePiiEndpoint(endpointId, data) {
        return this.request(`/api/pii/endpoints/${endpointId}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        })
    }

    async deletePiiEndpoint(endpointId) {
        return this.request(`/api/pii/endpoints/${endpointId}`, {
            method: 'DELETE',
        })
    }

    async testPiiEndpoint(endpointId, text, language = 'en') {
        return this.request(`/api/pii/endpoints/${endpointId}/test`, {
            method: 'POST',
            body: JSON.stringify({ text, language }),
        })
    }

    async checkPiiEndpointHealth(endpointId) {
        return this.request(`/api/pii/endpoints/${endpointId}/health`, {
            method: 'POST',
        })
    }

    // Security Scan
    async getScannableModels() {
        return this.request('/api/security/models')
    }

    async getScanCategories() {
        return this.request('/api/security/categories')
    }

    async startSecurityScan(modelId, scanType = 'quick', categories = null) {
        return this.request(`/api/security/scan/${modelId}`, {
            method: 'POST',
            body: JSON.stringify({ scan_type: scanType, categories }),
        })
    }

    async getScanResult(scanId) {
        return this.request(`/api/security/scan/${scanId}`)
    }

    async getScanResults(modelId = null, limit = 20) {
        const params = new URLSearchParams()
        if (modelId) params.append('model_id', modelId)
        params.append('limit', limit)
        return this.request(`/api/security/results?${params.toString()}`)
    }

    // Garak Security Scan
    async getGarakStatus() {
        return this.request('/api/security/garak/status')
    }

    async getGarakCategories() {
        return this.request('/api/security/garak/categories')
    }

    async getGarakProbes() {
        return this.request('/api/security/garak/probes')
    }

    async startGarakScan(modelId, scanType = 'quick', categories = null) {
        return this.request(`/api/security/garak/scan/${modelId}`, {
            method: 'POST',
            body: JSON.stringify({ scan_type: scanType, categories }),
        })
    }

    downloadScanResult(scanId) {
        // Return download URL directly
        return `${this.baseUrl}/api/security/scan/${scanId}/download`
    }

    // Model Access Request Workflow
    async createAccessRequest(modelId, requestReason = null) {
        return this.request('/api/model-access/requests', {
            method: 'POST',
            body: JSON.stringify({ model_id: modelId, request_reason: requestReason }),
        })
    }

    async getAccessRequests(status = null) {
        const params = status ? `?status=${status}` : ''
        return this.request(`/api/model-access/requests${params}`)
    }

    async getMyAccessRequests() {
        return this.request('/api/model-access/my-requests')
    }

    async approveAccessRequest(requestId, responseNote = null) {
        return this.request(`/api/model-access/requests/${requestId}/approve`, {
            method: 'PUT',
            body: JSON.stringify({ response_note: responseNote }),
        })
    }

    async rejectAccessRequest(requestId, responseNote = null) {
        return this.request(`/api/model-access/requests/${requestId}/reject`, {
            method: 'PUT',
            body: JSON.stringify({ response_note: responseNote }),
        })
    }

    async getPendingRequestsCount() {
        return this.request('/api/model-access/requests/pending/count')
    }

    // Organization Join Workflow
    async getAvailableOrganizations() {
        return this.request('/api/organizations/available')
    }

    async getUserOrgStatus() {
        return this.request('/api/organizations/user-status')
    }

    async requestToJoinOrg(orgId, requestReason = null) {
        return this.request(`/api/organizations/${orgId}/join`, {
            method: 'POST',
            body: JSON.stringify({ request_reason: requestReason }),
        })
    }

    async getMyJoinRequests() {
        return this.request('/api/organizations/my-join-requests')
    }

    async getOrgJoinRequests(orgId, status = null) {
        const params = status ? `?status=${status}` : ''
        return this.request(`/api/organizations/${orgId}/join-requests${params}`)
    }

    async approveJoinRequest(requestId, responseNote = null) {
        return this.request(`/api/organizations/join-requests/${requestId}/approve`, {
            method: 'PUT',
            body: JSON.stringify({ response_note: responseNote }),
        })
    }

    async rejectJoinRequest(requestId, responseNote = null) {
        return this.request(`/api/organizations/join-requests/${requestId}/reject`, {
            method: 'PUT',
            body: JSON.stringify({ response_note: responseNote }),
        })
    }

    async skipOrganization() {
        return this.request('/api/organizations/skip-organization', {
            method: 'POST',
        })
    }

    // ============================================================================
    // Pending Registrations (Admin)
    // ============================================================================

    async getPendingRegistrations() {
        return this.request('/api/auth/pending-registrations')
    }

    async approveRegistration(userId) {
        return this.request(`/api/auth/registrations/${userId}/approve`, { method: 'PUT' })
    }

    async rejectRegistration(userId) {
        return this.request(`/api/auth/registrations/${userId}/reject`, { method: 'PUT' })
    }

    async adminCreateUser(userData) {
        return this.request('/api/auth/admin/create-user', {
            method: 'POST',
            body: JSON.stringify(userData)
        })
    }
}

export const api = new ApiClient()
