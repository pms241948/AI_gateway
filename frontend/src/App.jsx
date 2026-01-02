import { useState, useEffect, createContext, useContext } from 'react'
import { Routes, Route, Navigate, useNavigate, Link, useLocation } from 'react-router-dom'
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { api } from './api/client'

// Auth Context
const AuthContext = createContext(null)

export function useAuth() {
    return useContext(AuthContext)
}

// Auth Provider
function AuthProvider({ children }) {
    const [user, setUser] = useState(null)
    const [loading, setLoading] = useState(true)
    const navigate = useNavigate()

    useEffect(() => {
        const token = localStorage.getItem('access_token')
        if (token) {
            api.getMe()
                .then(userData => {
                    setUser(userData)
                })
                .catch(() => {
                    localStorage.removeItem('access_token')
                    localStorage.removeItem('refresh_token')
                })
                .finally(() => setLoading(false))
        } else {
            setLoading(false)
        }
    }, [])

    const login = async (username, password) => {
        const data = await api.login(username, password)
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        const userData = await api.getMe()
        setUser(userData)
        navigate('/dashboard')
    }

    const logout = () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        setUser(null)
        navigate('/login')
    }

    if (loading) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
                <div className="loading-spinner"></div>
            </div>
        )
    }

    return (
        <AuthContext.Provider value={{ user, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

// Protected Route
function ProtectedRoute({ children }) {
    const { user } = useAuth()
    if (!user) {
        return <Navigate to="/login" replace />
    }
    return children
}

// Sidebar Component
function Sidebar() {
    const location = useLocation()
    const { user, logout } = useAuth()

    const navItems = [
        { path: '/dashboard', label: 'Dashboard', icon: '📊' },
        { path: '/models', label: 'Models', icon: '🤖' },
        { path: '/providers', label: 'Providers', icon: '🔌' },
        { path: '/logs', label: 'Request Logs', icon: '📋' },
        { path: '/organizations', label: 'Organizations', icon: '🏢' },
        { path: '/users', label: 'Users', icon: '👥' },
        { path: '/pii-settings', label: 'PII Masking', icon: '🔒' },
    ]

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="sidebar-logo">
                    <div className="sidebar-logo-icon">⚡</div>
                    AI Gateway
                </div>
            </div>
            <nav className="sidebar-nav">
                <div className="nav-section">
                    <div className="nav-section-title">Main</div>
                    {navItems.map(item => (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
                        >
                            <span className="nav-item-icon">{item.icon}</span>
                            {item.label}
                        </Link>
                    ))}
                </div>
            </nav>
            <div style={{ padding: 'var(--spacing-4)', borderTop: '1px solid var(--color-border)' }}>
                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginBottom: 'var(--spacing-2)' }}>
                    {user?.email}
                </div>
                <button className="btn btn-secondary" style={{ width: '100%' }} onClick={logout}>
                    Logout
                </button>
            </div>
        </aside>
    )
}

// Layout Component
function Layout({ children }) {
    return (
        <div className="app-container">
            <Sidebar />
            <main className="main-content">
                {children}
            </main>
        </div>
    )
}

// Login Page
function LoginPage() {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const { login, user } = useAuth()

    if (user) {
        return <Navigate to="/dashboard" replace />
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')
        setLoading(true)
        try {
            await login(username, password)
        } catch (err) {
            setError(err.message || 'Login failed')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-header">
                    <div className="login-logo">⚡</div>
                    <h1 className="login-title">AI Gateway</h1>
                    <p className="login-subtitle">Sign in to your account</p>
                </div>
                <form className="login-form" onSubmit={handleSubmit}>
                    {error && (
                        <div style={{ padding: 'var(--spacing-3)', background: 'var(--color-error-muted)', color: 'var(--color-error)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--spacing-4)', fontSize: 'var(--font-size-sm)' }}>
                            {error}
                        </div>
                    )}
                    <div className="form-group">
                        <label className="form-label">Username or Email</label>
                        <input
                            type="text"
                            className="form-input"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Enter your username"
                            required
                        />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Password</label>
                        <input
                            type="password"
                            className="form-input"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Enter your password"
                            required
                        />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={loading}>
                        {loading ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>
            </div>
        </div>
    )
}

// Chart colors
const CHART_COLORS = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

// Dashboard Page
function DashboardPage() {
    const [stats, setStats] = useState(null)
    const [usageData, setUsageData] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        Promise.all([
            api.getDashboardStats(),
            api.getUsageStats({ days: 7 }).catch(() => ({ data: [] }))
        ])
            .then(([statsData, usage]) => {
                setStats(statsData)
                // Format usage data for charts
                const formatted = (usage.data || []).map(d => ({
                    date: new Date(d.period).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }),
                    requests: d.request_count || 0,
                    tokens: (d.input_tokens || 0) + (d.output_tokens || 0),
                    latency: Math.round(d.avg_latency_ms || 0),
                }))
                setUsageData(formatted)
            })
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    if (loading) {
        return (
            <Layout>
                <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-12)' }}>
                    <div className="loading-spinner"></div>
                </div>
            </Layout>
        )
    }

    return (
        <Layout>
            <div className="page-header">
                <h1 className="page-title">Dashboard</h1>
                <p className="page-subtitle">Overview of your AI Gateway usage</p>
            </div>

            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-card-label">Requests (24h)</div>
                    <div className="stat-card-value">{stats?.total_requests_24h?.toLocaleString() || 0}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-card-label">Active Models</div>
                    <div className="stat-card-value">{stats?.active_models || 0}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-card-label">Avg Latency</div>
                    <div className="stat-card-value">{Math.round(stats?.avg_latency_ms || 0)}ms</div>
                </div>
                <div className="stat-card">
                    <div className="stat-card-label">Error Rate</div>
                    <div className="stat-card-value">{(stats?.error_rate || 0).toFixed(2)}%</div>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <h2 className="card-title">Token Usage (30 days)</h2>
                </div>
                <div className="stats-grid" style={{ marginBottom: 0 }}>
                    <div>
                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Input Tokens</div>
                        <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 600 }}>{stats?.total_input_tokens?.toLocaleString() || 0}</div>
                    </div>
                    <div>
                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Output Tokens</div>
                        <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 600 }}>{stats?.total_output_tokens?.toLocaleString() || 0}</div>
                    </div>
                    <div>
                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Estimated Cost</div>
                        <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 600 }}>${(stats?.total_cost || 0).toFixed(4)}</div>
                    </div>
                </div>
            </div>

            {usageData.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--spacing-4)' }}>
                    <div className="card">
                        <div className="card-header">
                            <h2 className="card-title">Requests (7 days)</h2>
                        </div>
                        <div style={{ height: '250px', padding: 'var(--spacing-4)' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={usageData}>
                                    <defs>
                                        <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                                    <XAxis dataKey="date" stroke="var(--color-text-muted)" fontSize={12} />
                                    <YAxis stroke="var(--color-text-muted)" fontSize={12} />
                                    <Tooltip
                                        contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
                                        labelStyle={{ color: 'var(--color-text-primary)' }}
                                    />
                                    <Area type="monotone" dataKey="requests" stroke="#8b5cf6" fillOpacity={1} fill="url(#colorRequests)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                    <div className="card">
                        <div className="card-header">
                            <h2 className="card-title">Latency (7 days)</h2>
                        </div>
                        <div style={{ height: '250px', padding: 'var(--spacing-4)' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={usageData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                                    <XAxis dataKey="date" stroke="var(--color-text-muted)" fontSize={12} />
                                    <YAxis stroke="var(--color-text-muted)" fontSize={12} unit="ms" />
                                    <Tooltip
                                        contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
                                        labelStyle={{ color: 'var(--color-text-primary)' }}
                                    />
                                    <Line type="monotone" dataKey="latency" stroke="#10b981" strokeWidth={2} dot={{ fill: '#10b981' }} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            )}
        </Layout>
    )
}

// Models Page
function ModelsPage() {
    const [models, setModels] = useState([])
    const [loading, setLoading] = useState(true)
    const [showModal, setShowModal] = useState(false)

    useEffect(() => {
        loadModels()
    }, [])

    const loadModels = () => {
        api.getModels()
            .then(setModels)
            .catch(console.error)
            .finally(() => setLoading(false))
    }

    const handleTest = async (modelId) => {
        try {
            const result = await api.testModel(modelId)
            alert(result.success ?
                `Success! Response: ${result.response?.substring(0, 100)}... (${result.latency_ms}ms)` :
                `Error: ${result.error_message}`)
        } catch (err) {
            alert('Test failed: ' + err.message)
        }
    }

    return (
        <Layout>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 className="page-title">Models</h1>
                    <p className="page-subtitle">Manage your LLM model configurations</p>
                </div>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                    + Add Model
                </button>
            </div>

            <div className="card">
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-8)' }}>
                        <div className="loading-spinner"></div>
                    </div>
                ) : models.length === 0 ? (
                    <div className="empty-state">
                        <div className="empty-state-icon">🤖</div>
                        <div className="empty-state-title">No models configured</div>
                        <p>Add your first model to get started</p>
                    </div>
                ) : (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Alias</th>
                                    <th>Type</th>
                                    <th>Status</th>
                                    <th>Endpoints</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {models.map(model => (
                                    <tr key={model.id}>
                                        <td style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{model.alias}</td>
                                        <td><span className="badge badge-primary">{model.model_type}</span></td>
                                        <td>
                                            <span className={`badge ${model.is_active ? 'badge-success' : 'badge-warning'}`}>
                                                {model.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td>{model.endpoints?.length || 0}</td>
                                        <td>
                                            <button className="btn btn-secondary" onClick={() => handleTest(model.id)}>
                                                Test
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </Layout>
    )
}

// Providers Page
function ProvidersPage() {
    const [providers, setProviders] = useState([])
    const [loading, setLoading] = useState(true)
    const [showModal, setShowModal] = useState(false)
    const [form, setForm] = useState({
        name: '',
        provider_type: 'ollama',
        base_url: 'http://localhost:11434',
        auth_type: 'none',
        auth_credentials: '',
    })

    useEffect(() => {
        loadProviders()
    }, [])

    const loadProviders = () => {
        api.getProviders()
            .then(setProviders)
            .catch(console.error)
            .finally(() => setLoading(false))
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        try {
            await api.createProvider(form)
            setShowModal(false)
            setForm({ name: '', provider_type: 'ollama', base_url: 'http://localhost:11434', auth_type: 'none', auth_credentials: '' })
            loadProviders()
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const handleTest = async (providerId) => {
        try {
            const result = await api.testProvider(providerId)
            alert(result.success ?
                `Connection successful! Latency: ${result.latency_ms}ms` :
                `Connection failed: ${result.error_message}`)
        } catch (err) {
            alert('Test failed: ' + err.message)
        }
    }

    return (
        <Layout>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 className="page-title">Providers</h1>
                    <p className="page-subtitle">Configure LLM provider connections</p>
                </div>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                    + Add Provider
                </button>
            </div>

            <div className="card">
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-8)' }}>
                        <div className="loading-spinner"></div>
                    </div>
                ) : providers.length === 0 ? (
                    <div className="empty-state">
                        <div className="empty-state-icon">🔌</div>
                        <div className="empty-state-title">No providers configured</div>
                        <p>Add a provider to connect to LLM endpoints</p>
                    </div>
                ) : (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Type</th>
                                    <th>Base URL</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {providers.map(provider => (
                                    <tr key={provider.id}>
                                        <td style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{provider.name}</td>
                                        <td><span className="badge badge-primary">{provider.provider_type}</span></td>
                                        <td style={{ fontSize: 'var(--font-size-sm)', fontFamily: 'monospace' }}>{provider.base_url}</td>
                                        <td>
                                            <span className={`badge ${provider.is_active ? 'badge-success' : 'badge-warning'}`}>
                                                {provider.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td>
                                            <button className="btn btn-secondary" onClick={() => handleTest(provider.id)}>
                                                Test
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2 className="modal-title">Add Provider</h2>
                            <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
                        </div>
                        <form onSubmit={handleSubmit}>
                            <div className="form-group">
                                <label className="form-label">Name</label>
                                <input type="text" className="form-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Provider Type</label>
                                <select className="form-select" value={form.provider_type} onChange={e => setForm({ ...form, provider_type: e.target.value })}>
                                    <option value="ollama">Ollama</option>
                                    <option value="openai_compatible">OpenAI Compatible</option>
                                    <option value="vllm">vLLM</option>
                                    <option value="openai">OpenAI</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Base URL</label>
                                <input type="text" className="form-input" value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Auth Type</label>
                                <select className="form-select" value={form.auth_type} onChange={e => setForm({ ...form, auth_type: e.target.value })}>
                                    <option value="none">None</option>
                                    <option value="api_key">API Key</option>
                                    <option value="bearer">Bearer Token</option>
                                </select>
                            </div>
                            {form.auth_type !== 'none' && (
                                <div className="form-group">
                                    <label className="form-label">API Key / Token</label>
                                    <input type="password" className="form-input" value={form.auth_credentials} onChange={e => setForm({ ...form, auth_credentials: e.target.value })} />
                                </div>
                            )}
                            <div className="modal-footer">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                                <button type="submit" className="btn btn-primary">Create Provider</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </Layout>
    )
}

// Logs Page
function LogsPage() {
    const [logs, setLogs] = useState([])
    const [loading, setLoading] = useState(true)
    const [page, setPage] = useState(1)
    const [total, setTotal] = useState(0)

    useEffect(() => {
        loadLogs()
    }, [page])

    const loadLogs = () => {
        setLoading(true)
        api.getRequestLogs({ page, page_size: 50 })
            .then(data => {
                setLogs(data.items || [])
                setTotal(data.total || 0)
            })
            .catch(console.error)
            .finally(() => setLoading(false))
    }

    const formatDate = (dateStr) => {
        return new Date(dateStr).toLocaleString()
    }

    return (
        <Layout>
            <div className="page-header">
                <h1 className="page-title">Request Logs</h1>
                <p className="page-subtitle">View API request history and details</p>
            </div>

            <div className="card">
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-8)' }}>
                        <div className="loading-spinner"></div>
                    </div>
                ) : logs.length === 0 ? (
                    <div className="empty-state">
                        <div className="empty-state-icon">📋</div>
                        <div className="empty-state-title">No logs yet</div>
                        <p>API requests will appear here</p>
                    </div>
                ) : (
                    <>
                        <div className="table-container">
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Endpoint</th>
                                        <th>Status</th>
                                        <th>Latency</th>
                                        <th>Tokens</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {logs.map(log => (
                                        <tr key={log.id}>
                                            <td style={{ fontSize: 'var(--font-size-xs)' }}>{formatDate(log.created_at)}</td>
                                            <td style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-sm)' }}>{log.endpoint}</td>
                                            <td>
                                                <span className={`badge ${log.status_code < 400 ? 'badge-success' : 'badge-error'}`}>
                                                    {log.status_code}
                                                </span>
                                            </td>
                                            <td>{log.latency_ms}ms</td>
                                            <td>{log.input_tokens || '-'} / {log.output_tokens || '-'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--spacing-4)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--color-border)' }}>
                            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                                Showing {logs.length} of {total} logs
                            </span>
                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                <button className="btn btn-secondary" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
                                <button className="btn btn-secondary" disabled={logs.length < 50} onClick={() => setPage(p => p + 1)}>Next</button>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </Layout>
    )
}

// Organizations Page
function OrganizationsPage() {
    const [organizations, setOrganizations] = useState([])
    const [loading, setLoading] = useState(true)
    const [showModal, setShowModal] = useState(false)
    const [showMemberModal, setShowMemberModal] = useState(false)
    const [showModelModal, setShowModelModal] = useState(false)
    const [selectedOrg, setSelectedOrg] = useState(null)
    const [members, setMembers] = useState([])
    const [allUsers, setAllUsers] = useState([])
    const [orgModels, setOrgModels] = useState([])
    const [allModels, setAllModels] = useState([])
    const [form, setForm] = useState({ name: '', description: '' })

    useEffect(() => {
        loadOrganizations()
    }, [])

    const loadOrganizations = () => {
        api.getOrganizations()
            .then(setOrganizations)
            .catch(console.error)
            .finally(() => setLoading(false))
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        try {
            await api.createOrganization(form)
            setShowModal(false)
            setForm({ name: '', description: '' })
            loadOrganizations()
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const openMemberModal = async (org) => {
        setSelectedOrg(org)
        setShowMemberModal(true)
        try {
            const [orgMembers, users] = await Promise.all([
                api.getOrganizationMembers(org.id),
                api.getUsers()
            ])
            setMembers(orgMembers)
            setAllUsers(users)
        } catch (err) {
            console.error(err)
        }
    }

    const addMember = async (userId) => {
        try {
            await api.addMemberToOrganization(selectedOrg.id, userId)
            const orgMembers = await api.getOrganizationMembers(selectedOrg.id)
            setMembers(orgMembers)
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const removeMember = async (userId) => {
        if (!confirm('Remove this user from the organization?')) return
        try {
            await api.removeMemberFromOrganization(selectedOrg.id, userId)
            const orgMembers = await api.getOrganizationMembers(selectedOrg.id)
            setMembers(orgMembers)
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const toggleAdmin = async (userId, currentStatus) => {
        try {
            await api.setMemberAdminStatus(selectedOrg.id, userId, !currentStatus)
            const orgMembers = await api.getOrganizationMembers(selectedOrg.id)
            setMembers(orgMembers)
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const openModelModal = async (org) => {
        setSelectedOrg(org)
        setShowModelModal(true)
        try {
            const [models, all] = await Promise.all([
                api.getOrgModels(org.id),
                api.getModels()
            ])
            setOrgModels(models)
            setAllModels(all)
        } catch (err) {
            console.error(err)
        }
    }

    const grantModel = async (modelId) => {
        try {
            await api.grantOrgModelAccess(selectedOrg.id, modelId)
            const models = await api.getOrgModels(selectedOrg.id)
            setOrgModels(models)
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const revokeModel = async (modelId) => {
        if (!confirm('Revoke access to this model regarding this organization?')) return
        try {
            await api.revokeOrgModelAccess(selectedOrg.id, modelId)
            const models = await api.getOrgModels(selectedOrg.id)
            setOrgModels(models)
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }


    const availableUsers = allUsers.filter(
        user => !members.some(m => m.id === user.id)
    )

    const availableModels = allModels.filter(
        model => !orgModels.some(m => m.model_id === model.id)
    )

    return (
        <Layout>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 className="page-title">Organizations</h1>
                    <p className="page-subtitle">Manage organizations and groups</p>
                </div>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                    + Add Organization
                </button>
            </div>

            <div className="card">
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-8)' }}>
                        <div className="loading-spinner"></div>
                    </div>
                ) : organizations.length === 0 ? (
                    <div className="empty-state">
                        <div className="empty-state-icon">🏢</div>
                        <div className="empty-state-title">No organizations</div>
                        <p>Create an organization to manage user groups</p>
                    </div>
                ) : (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Description</th>
                                    <th>Status</th>
                                    <th>Created</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {organizations.map(org => (
                                    <tr key={org.id}>
                                        <td style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{org.name}</td>
                                        <td>{org.description || '-'}</td>
                                        <td>
                                            <span className={`badge ${org.is_active ? 'badge-success' : 'badge-warning'}`}>
                                                {org.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: 'var(--font-size-sm)' }}>
                                            {new Date(org.created_at).toLocaleDateString()}
                                        </td>
                                        <td>
                                            <button className="btn btn-secondary" onClick={() => openMemberModal(org)}>
                                                👥 Members
                                            </button>
                                            <button className="btn btn-secondary" style={{ marginLeft: 'var(--spacing-2)' }} onClick={() => openModelModal(org)}>
                                                🤖 Models
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Create Organization Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2 className="modal-title">Add Organization</h2>
                            <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
                        </div>
                        <form onSubmit={handleSubmit}>
                            <div className="form-group">
                                <label className="form-label">Name</label>
                                <input type="text" className="form-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Description</label>
                                <textarea className="form-input" rows={3} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                                <button type="submit" className="btn btn-primary">Create Organization</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Manage Members Modal */}
            {showMemberModal && selectedOrg && (
                <div className="modal-overlay" onClick={() => setShowMemberModal(false)}>
                    <div className="modal" style={{ maxWidth: '600px' }} onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2 className="modal-title">Members of {selectedOrg.name}</h2>
                            <button className="modal-close" onClick={() => setShowMemberModal(false)}>×</button>
                        </div>

                        {/* Add Member Section */}
                        {availableUsers.length > 0 && (
                            <div style={{ padding: 'var(--spacing-4)', borderBottom: '1px solid var(--color-border)' }}>
                                <label className="form-label">Add User to Organization</label>
                                <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                    <select
                                        id="userSelect"
                                        className="form-select"
                                        style={{ flex: 1 }}
                                        defaultValue=""
                                    >
                                        <option value="" disabled>Select a user...</option>
                                        {availableUsers.map(user => (
                                            <option key={user.id} value={user.id}>{user.username} ({user.email})</option>
                                        ))}
                                    </select>
                                    <button
                                        className="btn btn-primary"
                                        onClick={() => {
                                            const select = document.getElementById('userSelect')
                                            if (select.value) {
                                                addMember(select.value)
                                                select.value = ''
                                            }
                                        }}
                                    >
                                        Add
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Members List */}
                        <div style={{ padding: 'var(--spacing-4)', maxHeight: '400px', overflow: 'auto' }}>
                            {members.length === 0 ? (
                                <div style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 'var(--spacing-6)' }}>
                                    No members in this organization
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                                    {members.map(member => (
                                        <div key={member.id} style={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            padding: 'var(--spacing-3)',
                                            background: 'var(--color-surface-elevated)',
                                            borderRadius: 'var(--radius-md)',
                                        }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                                                <div>
                                                    <div style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                                                        {member.username}
                                                        {member.is_org_admin && (
                                                            <span className="badge badge-primary" style={{ fontSize: '10px' }}>Admin</span>
                                                        )}
                                                    </div>
                                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>{member.email}</div>
                                                </div>
                                            </div>
                                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                                <button
                                                    className={`btn ${member.is_org_admin ? 'btn-secondary' : 'btn-primary'}`}
                                                    style={{ fontSize: 'var(--font-size-xs)' }}
                                                    onClick={() => toggleAdmin(member.id, member.is_org_admin)}
                                                    title={member.is_org_admin ? 'Remove admin rights' : 'Make admin'}
                                                >
                                                    {member.is_org_admin ? '👤 Demote' : '⭐ Make Admin'}
                                                </button>
                                                <button
                                                    className="btn btn-secondary"
                                                    style={{ color: 'var(--color-error)' }}
                                                    onClick={() => removeMember(member.id)}
                                                >
                                                    Remove
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="modal-footer">
                            <button type="button" className="btn btn-secondary" onClick={() => setShowMemberModal(false)}>Close</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Manage Models Modal */}
            {showModelModal && selectedOrg && (
                <div className="modal-overlay" onClick={() => setShowModelModal(false)}>
                    <div className="modal" style={{ maxWidth: '600px' }} onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2 className="modal-title">Models for {selectedOrg.name}</h2>
                            <button className="modal-close" onClick={() => setShowModelModal(false)}>×</button>
                        </div>

                        {/* Add Model Section */}
                        {availableModels.length > 0 && (
                            <div style={{ padding: 'var(--spacing-4)', borderBottom: '1px solid var(--color-border)' }}>
                                <label className="form-label">Grant Access to Model</label>
                                <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                    <select
                                        id="modelSelect"
                                        className="form-select"
                                        style={{ flex: 1 }}
                                        defaultValue=""
                                    >
                                        <option value="" disabled>Select a model...</option>
                                        {availableModels.map(model => (
                                            <option key={model.id} value={model.id}>{model.display_name} ({model.alias})</option>
                                        ))}
                                    </select>
                                    <button
                                        className="btn btn-primary"
                                        onClick={() => {
                                            const select = document.getElementById('modelSelect')
                                            if (select.value) {
                                                grantModel(select.value)
                                                select.value = ''
                                            }
                                        }}
                                    >
                                        Grant
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Models List */}
                        <div style={{ padding: 'var(--spacing-4)', maxHeight: '400px', overflow: 'auto' }}>
                            {orgModels.length === 0 ? (
                                <div style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 'var(--spacing-6)' }}>
                                    No models assigned to this organization
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                                    {orgModels.map(model => (
                                        <div key={model.model_id} style={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            padding: 'var(--spacing-3)',
                                            background: 'var(--color-surface-elevated)',
                                            borderRadius: 'var(--radius-md)',
                                        }}>
                                            <div>
                                                <div style={{ fontWeight: 500 }}>{model.model_display_name}</div>
                                                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>{model.model_alias}</div>
                                            </div>
                                            <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center' }}>
                                                <div style={{ fontSize: 'var(--font-size-xs)', padding: '2px 6px', borderRadius: '4px', background: 'var(--color-success-bg)', color: 'var(--color-success-text)' }}>
                                                    Access Granted
                                                </div>
                                                <button
                                                    className="btn btn-secondary"
                                                    style={{ color: 'var(--color-error)' }}
                                                    onClick={() => revokeModel(model.model_id)}
                                                >
                                                    Revoke
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="modal-footer">
                            <button type="button" className="btn btn-secondary" onClick={() => setShowModelModal(false)}>Close</button>
                        </div>
                    </div>
                </div>
            )}
        </Layout>
    )
}

// Users Page
function UsersPage() {
    const [users, setUsers] = useState([])
    const [loading, setLoading] = useState(true)
    const [showModelModal, setShowModelModal] = useState(false)
    const [selectedUser, setSelectedUser] = useState(null)
    const [userModels, setUserModels] = useState([])
    const [allModels, setAllModels] = useState([])

    useEffect(() => {
        api.getUsers()
            .then(setUsers)
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    const openModelModal = async (user) => {
        setSelectedUser(user)
        setShowModelModal(true)
        try {
            const [models, all] = await Promise.all([
                api.getUserModels(user.id),
                api.getModels()
            ])
            setUserModels(models)
            setAllModels(all)
        } catch (err) {
            console.error(err)
        }
    }

    const grantModel = async (modelId) => {
        try {
            await api.grantUserModelAccess(selectedUser.id, modelId)
            const models = await api.getUserModels(selectedUser.id)
            setUserModels(models)
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const revokeModel = async (modelId) => {
        if (!confirm('Revoke access to this model for this user?')) return
        try {
            await api.revokeUserModelAccess(selectedUser.id, modelId)
            const models = await api.getUserModels(selectedUser.id)
            setUserModels(models)
        } catch (err) {
            alert('Error: ' + err.message)
        }
    }

    const availableModels = allModels.filter(
        model => !userModels.some(m => m.model_id === model.id)
    )

    return (
        <Layout>
            <div className="page-header">
                <h1 className="page-title">Users</h1>
                <p className="page-subtitle">Manage user accounts and permissions</p>
            </div>
            <div className="card">
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-8)' }}>
                        <div className="loading-spinner"></div>
                    </div>
                ) : users.length === 0 ? (
                    <div className="empty-state">
                        <div className="empty-state-icon">👥</div>
                        <div className="empty-state-title">No users found</div>
                    </div>
                ) : (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Username</th>
                                    <th>Email</th>
                                    <th>Status</th>
                                    <th>Role</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map(user => (
                                    <tr key={user.id}>
                                        <td style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{user.username}</td>
                                        <td>{user.email}</td>
                                        <td>
                                            <span className={`badge ${user.is_active ? 'badge-success' : 'badge-warning'}`}>
                                                {user.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td>
                                            <span className="badge badge-primary">
                                                {user.is_superuser ? 'Admin' : 'User'}
                                            </span>
                                        </td>
                                        <td>
                                            <button className="btn btn-secondary" onClick={() => openModelModal(user)}>
                                                🤖 Models
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Manage Models Modal */}
            {showModelModal && selectedUser && (
                <div className="modal-overlay" onClick={() => setShowModelModal(false)}>
                    <div className="modal" style={{ maxWidth: '600px' }} onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2 className="modal-title">Models for {selectedUser.username}</h2>
                            <button className="modal-close" onClick={() => setShowModelModal(false)}>×</button>
                        </div>

                        {/* Add Model Section */}
                        {availableModels.length > 0 && (
                            <div style={{ padding: 'var(--spacing-4)', borderBottom: '1px solid var(--color-border)' }}>
                                <label className="form-label">Grant Access to Model</label>
                                <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                    <select
                                        id="userModelSelect"
                                        className="form-select"
                                        style={{ flex: 1 }}
                                        defaultValue=""
                                    >
                                        <option value="" disabled>Select a model...</option>
                                        {availableModels.map(model => (
                                            <option key={model.id} value={model.id}>{model.display_name} ({model.alias})</option>
                                        ))}
                                    </select>
                                    <button
                                        className="btn btn-primary"
                                        onClick={() => {
                                            const select = document.getElementById('userModelSelect')
                                            if (select.value) {
                                                grantModel(select.value)
                                                select.value = ''
                                            }
                                        }}
                                    >
                                        Grant
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Models List */}
                        <div style={{ padding: 'var(--spacing-4)', maxHeight: '400px', overflow: 'auto' }}>
                            {userModels.length === 0 ? (
                                <div style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 'var(--spacing-6)' }}>
                                    No models assigned to this user
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                                    {userModels.map(model => (
                                        <div key={model.model_id} style={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            padding: 'var(--spacing-3)',
                                            background: 'var(--color-surface-elevated)',
                                            borderRadius: 'var(--radius-md)',
                                        }}>
                                            <div>
                                                <div style={{ fontWeight: 500 }}>{model.model_display_name}</div>
                                                <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>{model.model_alias}</div>
                                                {model.source && (
                                                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                                                        Source: {model.source}
                                                    </div>
                                                )}
                                            </div>
                                            <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center' }}>
                                                <div style={{ fontSize: 'var(--font-size-xs)', padding: '2px 6px', borderRadius: '4px', background: 'var(--color-success-bg)', color: 'var(--color-success-text)' }}>
                                                    Access Granted
                                                </div>
                                                {model.source !== 'organization' && (
                                                    <button
                                                        className="btn btn-secondary"
                                                        style={{ color: 'var(--color-error)' }}
                                                        onClick={() => revokeModel(model.model_id)}
                                                    >
                                                        Revoke
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="modal-footer">
                            <button type="button" className="btn btn-secondary" onClick={() => setShowModelModal(false)}>Close</button>
                        </div>
                    </div>
                </div>
            )}
        </Layout>
    )
}

// PII Settings Page
function PIISettingsPage() {
    const [config, setConfig] = useState(null)
    const [entities, setEntities] = useState([])
    const [testText, setTestText] = useState('')
    const [testResult, setTestResult] = useState(null)
    const [loading, setLoading] = useState(true)
    const [testing, setTesting] = useState(false)

    // Model management state
    const [nlpModels, setNlpModels] = useState([])
    const [recognizers, setRecognizers] = useState([])
    const [showAddRecognizer, setShowAddRecognizer] = useState(false)
    const [newRecognizer, setNewRecognizer] = useState({ name: '', display_name: '', pattern: '', score: 0.85 })
    const [patternTestText, setPatternTestText] = useState('')
    const [patternTestResult, setPatternTestResult] = useState(null)

    // Edit recognizer state
    const [editRecognizer, setEditRecognizer] = useState(null)
    const [editPatternTestText, setEditPatternTestText] = useState('')
    const [editPatternTestResult, setEditPatternTestResult] = useState(null)

    // NLP model management state
    const [showAddNlpModel, setShowAddNlpModel] = useState(false)
    const [newNlpModel, setNewNlpModel] = useState({ name: '', lang_code: '', model_name: '', description: '' })

    useEffect(() => {
        loadConfig()
    }, [])

    const loadConfig = async () => {
        try {
            const [configData, entitiesData, modelsData, recognizersData] = await Promise.all([
                api.getPIIConfig(),
                api.getPIIEntities(),
                api.getNlpModels().catch(() => []),
                api.getRecognizers().catch(() => [])
            ])
            setConfig(configData)
            setEntities(entitiesData.entities || [])
            setNlpModels(modelsData || [])
            setRecognizers(recognizersData || [])
        } catch (err) {
            console.error('Failed to load PII config:', err)
        } finally {
            setLoading(false)
        }
    }

    const handleTest = async () => {
        if (!testText.trim()) return
        setTesting(true)
        setTestResult(null)
        try {
            const result = await api.testPIIMasking(testText)
            setTestResult(result)
        } catch (err) {
            alert('테스트 실패: ' + err.message)
        } finally {
            setTesting(false)
        }
    }

    const handleAddRecognizer = async () => {
        if (!newRecognizer.name || !newRecognizer.pattern) {
            alert('이름과 패턴은 필수입니다.')
            return
        }
        try {
            await api.createRecognizer(newRecognizer)
            setShowAddRecognizer(false)
            setNewRecognizer({ name: '', display_name: '', pattern: '', score: 0.85 })
            loadConfig()
        } catch (err) {
            alert('추가 실패: ' + err.message)
        }
    }

    const handleDeleteRecognizer = async (id) => {
        if (!confirm('이 인식기를 삭제하시겠습니까?')) return
        try {
            await api.deleteRecognizer(id)
            loadConfig()
        } catch (err) {
            alert('삭제 실패: ' + err.message)
        }
    }

    const handleTestPattern = async () => {
        if (!newRecognizer.pattern || !patternTestText) return
        try {
            const result = await api.testPattern(newRecognizer.pattern, patternTestText)
            setPatternTestResult(result)
        } catch (err) {
            alert('패턴 테스트 실패: ' + err.message)
        }
    }

    // Edit recognizer handlers
    const handleEditRecognizer = (rec) => {
        setEditRecognizer({ ...rec })
        setEditPatternTestText('')
        setEditPatternTestResult(null)
    }

    const handleUpdateRecognizer = async () => {
        if (!editRecognizer) return
        try {
            await api.updateRecognizer(editRecognizer.id, {
                display_name: editRecognizer.display_name,
                pattern: editRecognizer.pattern,
                score: editRecognizer.score,
                is_enabled: editRecognizer.is_enabled
            })
            setEditRecognizer(null)
            loadConfig()
        } catch (err) {
            alert('수정 실패: ' + err.message)
        }
    }

    const handleEditTestPattern = async () => {
        if (!editRecognizer?.pattern || !editPatternTestText) return
        try {
            const result = await api.testPattern(editRecognizer.pattern, editPatternTestText)
            setEditPatternTestResult(result)
        } catch (err) {
            alert('패턴 테스트 실패: ' + err.message)
        }
    }

    // NLP model handlers
    const handleAddNlpModel = async () => {
        if (!newNlpModel.name || !newNlpModel.lang_code || !newNlpModel.model_name) {
            alert('이름, 언어 코드, 모델명은 필수입니다.')
            return
        }
        try {
            await api.addNlpModel(newNlpModel)
            setShowAddNlpModel(false)
            setNewNlpModel({ name: '', lang_code: '', model_name: '', description: '' })
            loadConfig()
        } catch (err) {
            alert('NLP 모델 추가 실패: ' + err.message)
        }
    }

    const handleDeleteNlpModel = async (id) => {
        if (!confirm('이 NLP 모델을 삭제하시겠습니까?')) return
        try {
            await api.deleteNlpModel(id)
            loadConfig()
        } catch (err) {
            alert('삭제 실패: ' + err.message)
        }
    }

    if (loading) {
        return (
            <Layout>
                <div className="page-header">
                    <h1 className="page-title">🔒 PII Masking Settings</h1>
                </div>
                <div className="card"><p>Loading...</p></div>
            </Layout>
        )
    }

    return (
        <Layout>
            <div className="page-header">
                <h1 className="page-title">🔒 PII Masking Settings</h1>
                <p style={{ color: 'var(--color-text-muted)', marginTop: 'var(--spacing-2)' }}>
                    개인식별정보(PII) 자동 탐지 및 마스킹 설정
                </p>
            </div>

            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
                {/* Configuration Card */}
                <div className="card">
                    <h3 style={{ marginBottom: 'var(--spacing-4)' }}>현재 설정</h3>
                    <div className="table-container">
                        <table className="table">
                            <tbody>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>마스킹 활성화</td>
                                    <td>
                                        <span className={`badge ${config?.enabled ? 'badge-success' : 'badge-secondary'}`}>
                                            {config?.enabled ? 'ON' : 'OFF'}
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>요청 마스킹</td>
                                    <td>
                                        <span className={`badge ${config?.mask_request ? 'badge-success' : 'badge-secondary'}`}>
                                            {config?.mask_request ? 'ON' : 'OFF'}
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>응답 마스킹</td>
                                    <td>
                                        <span className={`badge ${config?.mask_response ? 'badge-success' : 'badge-secondary'}`}>
                                            {config?.mask_response ? 'ON' : 'OFF'}
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>마스킹 방식</td>
                                    <td><code>{config?.mask_type}</code></td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>감지 언어</td>
                                    <td><code>{config?.language}</code></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <p style={{ marginTop: 'var(--spacing-3)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                        설정 변경은 환경변수(.env)를 수정 후 서버 재시작이 필요합니다.
                    </p>
                </div>

                {/* NLP Models Card */}
                <div className="card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
                        <h3>🧠 NLP 모델</h3>
                        <button className="btn btn-secondary" onClick={() => setShowAddNlpModel(!showAddNlpModel)}>
                            {showAddNlpModel ? '취소' : '+ 모델 추가'}
                        </button>
                    </div>

                    {showAddNlpModel && (
                        <div style={{
                            background: 'var(--color-bg-secondary)',
                            padding: 'var(--spacing-3)',
                            borderRadius: 'var(--radius-md)',
                            marginBottom: 'var(--spacing-3)'
                        }}>
                            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-2)' }}>
                                <input
                                    className="form-input"
                                    placeholder="표시 이름 (예: Korean)"
                                    value={newNlpModel.name}
                                    onChange={e => setNewNlpModel({ ...newNlpModel, name: e.target.value })}
                                />
                                <input
                                    className="form-input"
                                    placeholder="언어 코드 (예: ko)"
                                    value={newNlpModel.lang_code}
                                    onChange={e => setNewNlpModel({ ...newNlpModel, lang_code: e.target.value })}
                                />
                            </div>
                            <input
                                className="form-input"
                                style={{ marginTop: 'var(--spacing-2)' }}
                                placeholder="spaCy 모델명 (예: ko_core_news_sm)"
                                value={newNlpModel.model_name}
                                onChange={e => setNewNlpModel({ ...newNlpModel, model_name: e.target.value })}
                            />
                            <button className="btn btn-primary" style={{ marginTop: 'var(--spacing-2)' }} onClick={handleAddNlpModel}>추가</button>
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                        {nlpModels.map(model => (
                            <div key={model.id} style={{
                                padding: 'var(--spacing-2) var(--spacing-3)',
                                background: 'var(--color-bg-secondary)',
                                borderRadius: 'var(--radius-md)',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                            }}>
                                <div>
                                    <div style={{ fontWeight: 500 }}>{model.name}</div>
                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                                        {model.model_name} ({model.lang_code})
                                    </div>
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center' }}>
                                    <span className={`badge ${model.is_enabled ? 'badge-success' : 'badge-secondary'}`}>
                                        {model.is_enabled ? 'ON' : 'OFF'}
                                    </span>
                                    {model.is_default && (
                                        <span className="badge badge-primary">기본</span>
                                    )}
                                    {!model.is_default && (
                                        <button
                                            className="btn btn-secondary"
                                            style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                            onClick={() => handleDeleteNlpModel(model.id)}
                                        >
                                            삭제
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                        {nlpModels.length === 0 && (
                            <div style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: 'var(--spacing-2)' }}>
                                en_core_web_sm (기본 내장)
                            </div>
                        )}
                    </div>
                    <p style={{ marginTop: 'var(--spacing-3)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                        ⚠️ 추가할 모델은 Docker 이미지에 먼저 설치되어 있어야 합니다.
                    </p>
                </div>
            </div>

            {/* Custom Recognizers Section */}
            <div className="card" style={{ marginTop: 'var(--spacing-4)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
                    <h3>🎯 PII 인식기</h3>
                    <button className="btn btn-primary" onClick={() => setShowAddRecognizer(!showAddRecognizer)}>
                        {showAddRecognizer ? '취소' : '+ 인식기 추가'}
                    </button>
                </div>

                {showAddRecognizer && (
                    <div style={{
                        background: 'var(--color-bg-secondary)',
                        padding: 'var(--spacing-4)',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: 'var(--spacing-4)'
                    }}>
                        <h4 style={{ marginBottom: 'var(--spacing-3)' }}>새 인식기 추가</h4>
                        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
                            <div className="form-group">
                                <label className="form-label">엔티티 이름 (영문 대문자)</label>
                                <input
                                    className="form-input"
                                    placeholder="KOREAN_PASSPORT"
                                    value={newRecognizer.name}
                                    onChange={e => setNewRecognizer({ ...newRecognizer, name: e.target.value.toUpperCase().replace(/[^A-Z_]/g, '') })}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">표시 이름</label>
                                <input
                                    className="form-input"
                                    placeholder="여권번호"
                                    value={newRecognizer.display_name}
                                    onChange={e => setNewRecognizer({ ...newRecognizer, display_name: e.target.value })}
                                />
                            </div>
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">정규식 패턴</label>
                            <input
                                className="form-input"
                                placeholder="[A-Z]{1}[0-9]{8}"
                                value={newRecognizer.pattern}
                                onChange={e => setNewRecognizer({ ...newRecognizer, pattern: e.target.value })}
                            />
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">패턴 테스트</label>
                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                <input
                                    className="form-input"
                                    placeholder="테스트할 텍스트 입력"
                                    value={patternTestText}
                                    onChange={e => setPatternTestText(e.target.value)}
                                    style={{ flex: 1 }}
                                />
                                <button className="btn btn-secondary" onClick={handleTestPattern}>테스트</button>
                            </div>
                            {patternTestResult && (
                                <div style={{ marginTop: 'var(--spacing-2)', fontSize: 'var(--font-size-sm)' }}>
                                    매칭: {patternTestResult.count}개
                                    {patternTestResult.matches.map((m, i) => (
                                        <span key={i} style={{ marginLeft: 'var(--spacing-2)', color: 'var(--color-success)' }}>
                                            [{m.text}]
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div style={{ marginTop: 'var(--spacing-4)' }}>
                            <button className="btn btn-primary" onClick={handleAddRecognizer}>추가</button>
                        </div>
                    </div>
                )}

                <div className="table-container">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>이름</th>
                                <th>표시명</th>
                                <th>패턴</th>
                                <th>신뢰도</th>
                                <th>유형</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {recognizers.map(rec => (
                                <tr key={rec.id}>
                                    <td><code>{rec.name}</code></td>
                                    <td>{rec.display_name}</td>
                                    <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        <code style={{ fontSize: 'var(--font-size-xs)' }}>{rec.pattern}</code>
                                    </td>
                                    <td>{(rec.score * 100).toFixed(0)}%</td>
                                    <td>
                                        <span className={`badge ${rec.is_builtin ? 'badge-primary' : 'badge-secondary'}`}>
                                            {rec.is_builtin ? '내장' : '커스텀'}
                                        </span>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 'var(--spacing-1)' }}>
                                            {!rec.is_builtin && (
                                                <>
                                                    <button
                                                        className="btn btn-secondary"
                                                        style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                                        onClick={() => handleEditRecognizer(rec)}
                                                    >
                                                        수정
                                                    </button>
                                                    <button
                                                        className="btn btn-secondary"
                                                        style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                                        onClick={() => handleDeleteRecognizer(rec.id)}
                                                    >
                                                        삭제
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Edit Recognizer Modal */}
            {editRecognizer && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(0,0,0,0.5)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000
                }}>
                    <div style={{
                        background: 'var(--color-bg-primary)',
                        padding: 'var(--spacing-6)',
                        borderRadius: 'var(--radius-lg)',
                        maxWidth: '500px',
                        width: '100%',
                        maxHeight: '80vh',
                        overflow: 'auto'
                    }}>
                        <h3 style={{ marginBottom: 'var(--spacing-4)' }}>✏️ 인식기 수정</h3>
                        <div className="form-group">
                            <label className="form-label">엔티티 이름</label>
                            <input className="form-input" value={editRecognizer.name} disabled />
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">표시 이름</label>
                            <input
                                className="form-input"
                                value={editRecognizer.display_name}
                                onChange={e => setEditRecognizer({ ...editRecognizer, display_name: e.target.value })}
                            />
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">정규식 패턴</label>
                            <input
                                className="form-input"
                                value={editRecognizer.pattern}
                                onChange={e => setEditRecognizer({ ...editRecognizer, pattern: e.target.value })}
                            />
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">신뢰도 ({(editRecognizer.score * 100).toFixed(0)}%)</label>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={editRecognizer.score}
                                onChange={e => setEditRecognizer({ ...editRecognizer, score: parseFloat(e.target.value) })}
                                style={{ width: '100%' }}
                            />
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">패턴 테스트</label>
                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                <input
                                    className="form-input"
                                    placeholder="테스트할 텍스트"
                                    value={editPatternTestText}
                                    onChange={e => setEditPatternTestText(e.target.value)}
                                    style={{ flex: 1 }}
                                />
                                <button className="btn btn-secondary" onClick={handleEditTestPattern}>테스트</button>
                            </div>
                            {editPatternTestResult && (
                                <div style={{ marginTop: 'var(--spacing-2)', fontSize: 'var(--font-size-sm)' }}>
                                    매칭: {editPatternTestResult.count}개
                                    {editPatternTestResult.matches.map((m, i) => (
                                        <span key={i} style={{ marginLeft: 'var(--spacing-2)', color: 'var(--color-success)' }}>
                                            [{m.text}]
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div style={{ marginTop: 'var(--spacing-4)', display: 'flex', gap: 'var(--spacing-2)', justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => setEditRecognizer(null)}>취소</button>
                            <button className="btn btn-primary" onClick={handleUpdateRecognizer}>저장</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Test Section */}
            <div className="card" style={{ marginTop: 'var(--spacing-4)' }}>
                <h3 style={{ marginBottom: 'var(--spacing-4)' }}>🧪 마스킹 테스트</h3>
                <p style={{ marginBottom: 'var(--spacing-3)', color: 'var(--color-text-muted)' }}>
                    샘플 텍스트를 입력하여 PII 탐지 및 마스킹 결과를 미리 확인할 수 있습니다.
                </p>
                <div className="form-group">
                    <label className="form-label">테스트 텍스트</label>
                    <textarea
                        className="form-input"
                        rows="4"
                        value={testText}
                        onChange={(e) => setTestText(e.target.value)}
                        placeholder="예: 제 이메일은 test@example.com이고 전화번호는 010-1234-5678입니다. 주민번호는 901231-1234567입니다."
                    />
                </div>
                <button
                    className="btn btn-primary"
                    onClick={handleTest}
                    disabled={testing || !testText.trim()}
                >
                    {testing ? '분석 중...' : '마스킹 테스트'}
                </button>

                {testResult && (
                    <div style={{ marginTop: 'var(--spacing-4)' }}>
                        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
                            <div>
                                <h4 style={{ marginBottom: 'var(--spacing-2)' }}>원본 텍스트</h4>
                                <div style={{
                                    padding: 'var(--spacing-3)',
                                    background: 'var(--color-bg-secondary)',
                                    borderRadius: 'var(--radius-md)',
                                    fontFamily: 'monospace',
                                    whiteSpace: 'pre-wrap'
                                }}>
                                    {testResult.original_text}
                                </div>
                            </div>
                            <div>
                                <h4 style={{ marginBottom: 'var(--spacing-2)' }}>마스킹 결과</h4>
                                <div style={{
                                    padding: 'var(--spacing-3)',
                                    background: 'var(--color-success-bg)',
                                    borderRadius: 'var(--radius-md)',
                                    fontFamily: 'monospace',
                                    whiteSpace: 'pre-wrap',
                                    border: '1px solid var(--color-success)'
                                }}>
                                    {testResult.masked_text}
                                </div>
                            </div>
                        </div>

                        {testResult.entities_count > 0 && (
                            <div style={{ marginTop: 'var(--spacing-4)' }}>
                                <h4 style={{ marginBottom: 'var(--spacing-2)' }}>
                                    탐지된 PII ({testResult.entities_count}개)
                                </h4>
                                <div className="table-container">
                                    <table className="table">
                                        <thead>
                                            <tr>
                                                <th>유형</th>
                                                <th>원본 값</th>
                                                <th>신뢰도</th>
                                                <th>위치</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {testResult.entities_found.map((entity, idx) => (
                                                <tr key={idx}>
                                                    <td><code>{entity.entity_type}</code></td>
                                                    <td style={{ fontFamily: 'monospace' }}>{entity.original}</td>
                                                    <td>{(entity.score * 100).toFixed(0)}%</td>
                                                    <td>{entity.start}-{entity.end}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {testResult.entities_count === 0 && (
                            <div style={{
                                marginTop: 'var(--spacing-4)',
                                padding: 'var(--spacing-3)',
                                background: 'var(--color-bg-secondary)',
                                borderRadius: 'var(--radius-md)',
                                textAlign: 'center',
                                color: 'var(--color-text-muted)'
                            }}>
                                PII가 탐지되지 않았습니다.
                            </div>
                        )}
                    </div>
                )}
            </div>
        </Layout>
    )
}

// Main App
export default function App() {
    return (
        <AuthProvider>
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
                <Route path="/models" element={<ProtectedRoute><ModelsPage /></ProtectedRoute>} />
                <Route path="/providers" element={<ProtectedRoute><ProvidersPage /></ProtectedRoute>} />
                <Route path="/logs" element={<ProtectedRoute><LogsPage /></ProtectedRoute>} />
                <Route path="/organizations" element={<ProtectedRoute><OrganizationsPage /></ProtectedRoute>} />
                <Route path="/users" element={<ProtectedRoute><UsersPage /></ProtectedRoute>} />
                <Route path="/pii-settings" element={<ProtectedRoute><PIISettingsPage /></ProtectedRoute>} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
        </AuthProvider>
    )
}
