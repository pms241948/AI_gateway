import { useState, useEffect, useCallback, createContext, useContext } from 'react'
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
        { path: '/security-scan', label: 'Security Scan', icon: '🛡️' },
        { path: '/pending-registrations', label: '가입 승인', icon: '📝' },
        { path: '/org-select', label: '조직 가입', icon: '🏛️' },
        { path: '/org-join-requests', label: '가입 요청 관리', icon: '✅' },
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
    const [isRegister, setIsRegister] = useState(false)
    const [username, setUsername] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState('')
    const [loading, setLoading] = useState(false)
    const [ssoProviders, setSsoProviders] = useState([])
    const { login, user } = useAuth()
    const location = window.location

    // Check for OIDC callback tokens in URL
    useEffect(() => {
        const params = new URLSearchParams(location.search)
        const accessToken = params.get('access_token')
        const refreshToken = params.get('refresh_token')
        const errorParam = params.get('error')

        if (errorParam) {
            setError(errorParam === 'account_disabled' ? '계정이 비활성화되었습니다' : 'SSO 로그인 실패')
            window.history.replaceState({}, document.title, '/login')
        }

        if (accessToken && refreshToken) {
            localStorage.setItem('access_token', accessToken)
            localStorage.setItem('refresh_token', refreshToken)
            window.history.replaceState({}, document.title, '/login')
            window.location.href = '/dashboard'
        }
    }, [])

    // Check for SSO providers (Google, Keycloak, etc.)
    useEffect(() => {
        const checkSsoProviders = async () => {
            try {
                const response = await fetch('/api/auth/sso/providers')
                if (response.ok) {
                    const data = await response.json()
                    setSsoProviders(data.providers || [])
                }
            } catch (err) {
                console.log('SSO providers check failed:', err)
            }
        }
        checkSsoProviders()
    }, [])

    if (user) {
        return <Navigate to="/dashboard" replace />
    }

    const handleLogin = async (e) => {
        e.preventDefault()
        setError('')
        setLoading(true)
        try {
            await login(username, password)
        } catch (err) {
            setError(err.message || '로그인 실패')
        } finally {
            setLoading(false)
        }
    }

    const handleRegister = async (e) => {
        e.preventDefault()
        setError('')
        setSuccess('')

        if (password !== confirmPassword) {
            setError('비밀번호가 일치하지 않습니다')
            return
        }

        if (password.length < 8) {
            setError('비밀번호는 8자 이상이어야 합니다')
            return
        }

        setLoading(true)
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password }),
            })

            if (!response.ok) {
                const data = await response.json()
                // Handle Pydantic validation errors (detail is array) or simple string errors
                let errorMsg = '회원가입 실패'
                if (Array.isArray(data.detail)) {
                    errorMsg = data.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ')
                } else if (typeof data.detail === 'string') {
                    errorMsg = data.detail
                } else if (data.detail) {
                    errorMsg = JSON.stringify(data.detail)
                }
                throw new Error(errorMsg)
            }

            setSuccess('회원가입 요청이 제출되었습니다! 관리자 승인 후 로그인이 가능합니다.')
            setIsRegister(false)
            setPassword('')
            setConfirmPassword('')
        } catch (err) {
            // Handle both string and object errors
            let errorMsg = '회원가입 실패'
            if (err.message) {
                errorMsg = typeof err.message === 'object' ? JSON.stringify(err.message) : err.message
            }
            setError(errorMsg)
        } finally {
            setLoading(false)
        }
    }

    const handleOidcLogin = () => {
        window.location.href = '/api/auth/oidc/login'
    }

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-header">
                    <div className="login-logo">⚡</div>
                    <h1 className="login-title">AI Gateway</h1>
                    <p className="login-subtitle">
                        {isRegister ? '새 계정 만들기' : '계정에 로그인'}
                    </p>
                </div>

                <form className="login-form" onSubmit={isRegister ? handleRegister : handleLogin}>
                    {error && (
                        <div style={{ padding: 'var(--spacing-3)', background: 'var(--color-error-muted)', color: 'var(--color-error)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--spacing-4)', fontSize: 'var(--font-size-sm)' }}>
                            {error}
                        </div>
                    )}
                    {success && (
                        <div style={{ padding: 'var(--spacing-3)', background: 'var(--color-success-muted)', color: 'var(--color-success)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--spacing-4)', fontSize: 'var(--font-size-sm)' }}>
                            {success}
                        </div>
                    )}

                    <div className="form-group">
                        <label className="form-label">사용자명</label>
                        <input
                            type="text"
                            className="form-input"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="사용자명 입력"
                            required
                        />
                    </div>

                    {isRegister && (
                        <div className="form-group">
                            <label className="form-label">이메일</label>
                            <input
                                type="email"
                                className="form-input"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="이메일 주소 입력"
                                required
                            />
                        </div>
                    )}

                    <div className="form-group">
                        <label className="form-label">비밀번호</label>
                        <input
                            type="password"
                            className="form-input"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="비밀번호 입력"
                            required
                        />
                    </div>

                    {isRegister && (
                        <div className="form-group">
                            <label className="form-label">비밀번호 확인</label>
                            <input
                                type="password"
                                className="form-input"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="비밀번호 다시 입력"
                                required
                            />
                        </div>
                    )}

                    <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
                        {loading ? '처리 중...' : (isRegister ? '회원가입' : '로그인')}
                    </button>

                    {/* SSO Login Buttons - Always visible */}
                    <div style={{ textAlign: 'center', margin: 'var(--spacing-4) 0', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                        또는 소셜 로그인
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                        {/* Google Login Button */}
                        <button
                            type="button"
                            className="btn"
                            onClick={() => window.location.href = '/api/auth/google/login'}
                            style={{
                                width: '100%',
                                background: '#fff',
                                color: '#333',
                                border: '1px solid #ddd',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: 'var(--spacing-2)',
                                fontWeight: 500,
                            }}
                        >
                            <svg width="18" height="18" viewBox="0 0 24 24">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                            </svg>
                            Google로 로그인
                        </button>

                        {/* Keycloak Login Button */}
                        <button
                            type="button"
                            className="btn"
                            onClick={() => window.location.href = '/api/auth/keycloak/login'}
                            style={{
                                width: '100%',
                                background: 'linear-gradient(135deg, #4d4d4d, #333)',
                                color: '#fff',
                                border: 'none',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: 'var(--spacing-2)',
                                fontWeight: 500,
                            }}
                        >
                            🔐 Keycloak으로 로그인
                        </button>
                    </div>

                    {/* Toggle between Login and Register */}
                    <div style={{ textAlign: 'center', marginTop: 'var(--spacing-4)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--color-border)' }}>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                            {isRegister ? '이미 계정이 있으신가요?' : '계정이 없으신가요?'}
                        </span>
                        <button
                            type="button"
                            onClick={() => { setIsRegister(!isRegister); setError(''); setSuccess(''); }}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'var(--color-primary)',
                                cursor: 'pointer',
                                marginLeft: 'var(--spacing-2)',
                                fontWeight: 'bold',
                            }}
                        >
                            {isRegister ? '로그인' : '회원가입'}
                        </button>
                    </div>
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
    const [providers, setProviders] = useState([])
    const [loading, setLoading] = useState(true)
    const [showModal, setShowModal] = useState(false)
    const [form, setForm] = useState({
        alias: '',
        model_type: '',
        provider_id: '',
        max_tokens: 4096,
        rate_limit_rpm: 60
    })

    useEffect(() => {
        loadModels()
        loadProviders()
    }, [])

    const loadModels = () => {
        api.getModels()
            .then(setModels)
            .catch(console.error)
            .finally(() => setLoading(false))
    }

    const loadProviders = () => {
        api.getProviders()
            .then(setProviders)
            .catch(console.error)
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

    const handleSubmit = async (e) => {
        e.preventDefault()
        try {
            await api.createModel({
                alias: form.alias,
                model_type: form.model_type,
                provider_id: form.provider_id,
                max_tokens: parseInt(form.max_tokens),
                rate_limit_rpm: parseInt(form.rate_limit_rpm)
            })
            setShowModal(false)
            setForm({ alias: '', model_type: '', provider_id: '', max_tokens: 4096, rate_limit_rpm: 60 })
            loadModels()
        } catch (err) {
            alert('Failed to create model: ' + err.message)
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

            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2 className="modal-title">Add Model</h2>
                            <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
                        </div>
                        <form onSubmit={handleSubmit}>
                            <div className="form-group">
                                <label className="form-label">Alias (Display Name)</label>
                                <input type="text" className="form-input" placeholder="e.g., GPT-4 Turbo" value={form.alias} onChange={e => setForm({ ...form, alias: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Provider</label>
                                <select className="form-select" value={form.provider_id} onChange={e => setForm({ ...form, provider_id: e.target.value })} required>
                                    <option value="">Select a provider...</option>
                                    {providers.map(p => (
                                        <option key={p.id} value={p.id}>{p.name} ({p.provider_type})</option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Model Type (API Model Name)</label>
                                <input type="text" className="form-input" placeholder="e.g., gpt-4-turbo, llama3" value={form.model_type} onChange={e => setForm({ ...form, model_type: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Max Tokens</label>
                                <input type="number" className="form-input" value={form.max_tokens} onChange={e => setForm({ ...form, max_tokens: e.target.value })} />
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                                <button type="submit" className="btn btn-primary">Create Model</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
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

// Pending Registrations Page (Admin only)
function PendingRegistrationsPage() {
    const [pendingUsers, setPendingUsers] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [success, setSuccess] = useState('')
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [createForm, setCreateForm] = useState({ username: '', email: '', password: '', confirmPassword: '' })
    const [creating, setCreating] = useState(false)

    const fetchPendingRegistrations = useCallback(async () => {
        try {
            setLoading(true)
            const data = await api.getPendingRegistrations()
            setPendingUsers(data.pending_registrations || [])
        } catch (err) {
            setError('대기 중인 가입 요청을 불러올 수 없습니다')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchPendingRegistrations()
    }, [fetchPendingRegistrations])

    const handleApprove = async (userId, username) => {
        try {
            await api.approveRegistration(userId)
            setSuccess(`${username} 사용자의 가입이 승인되었습니다`)
            fetchPendingRegistrations()
        } catch (err) {
            setError(err.message || '승인 실패')
        }
    }

    const handleReject = async (userId, username) => {
        if (!window.confirm(`${username} 사용자의 가입을 거절하시겠습니까? 계정이 삭제됩니다.`)) return
        try {
            await api.rejectRegistration(userId)
            setSuccess(`${username} 사용자의 가입이 거절되었습니다`)
            fetchPendingRegistrations()
        } catch (err) {
            setError(err.message || '거절 실패')
        }
    }

    const handleCreateUser = async (e) => {
        e.preventDefault()
        setError('')

        if (createForm.password !== createForm.confirmPassword) {
            setError('비밀번호가 일치하지 않습니다')
            return
        }
        if (createForm.password.length < 8) {
            setError('비밀번호는 8자 이상이어야 합니다')
            return
        }

        try {
            setCreating(true)
            await api.adminCreateUser({
                username: createForm.username,
                email: createForm.email,
                password: createForm.password
            })
            setSuccess(`${createForm.username} 사용자가 생성되었습니다`)
            setShowCreateModal(false)
            setCreateForm({ username: '', email: '', password: '', confirmPassword: '' })
        } catch (err) {
            setError(err.message || '사용자 생성 실패')
        } finally {
            setCreating(false)
        }
    }

    return (
        <Layout>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <h1 className="page-title">📝 가입 승인 관리</h1>
                    <p className="page-subtitle">회원가입 요청을 승인 또는 거절하고, 새 사용자를 직접 생성할 수 있습니다</p>
                </div>
                <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
                    ➕ 사용자 생성
                </button>
            </div>

            {error && (
                <div style={{ padding: 'var(--spacing-3)', background: 'var(--color-error-muted)', color: 'var(--color-error)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--spacing-4)' }}>
                    {error}
                </div>
            )}
            {success && (
                <div style={{ padding: 'var(--spacing-3)', background: 'var(--color-success-muted)', color: 'var(--color-success)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--spacing-4)' }}>
                    {success}
                </div>
            )}

            {loading ? (
                <div className="loading-state">로딩 중...</div>
            ) : pendingUsers.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-8)' }}>
                    <div style={{ fontSize: '3rem', marginBottom: 'var(--spacing-4)' }}>✅</div>
                    <h3>대기 중인 가입 요청이 없습니다</h3>
                    <p style={{ color: 'var(--color-text-secondary)' }}>모든 회원가입 요청이 처리되었습니다</p>
                </div>
            ) : (
                <div className="card">
                    <h3 style={{ marginBottom: 'var(--spacing-4)' }}>대기 중인 요청 ({pendingUsers.length})</h3>
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>사용자명</th>
                                    <th>이메일</th>
                                    <th>신청일</th>
                                    <th>작업</th>
                                </tr>
                            </thead>
                            <tbody>
                                {pendingUsers.map(user => (
                                    <tr key={user.id}>
                                        <td><strong>{user.username}</strong></td>
                                        <td>{user.email}</td>
                                        <td>{new Date(user.created_at).toLocaleString('ko-KR')}</td>
                                        <td>
                                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                                <button
                                                    className="btn btn-primary btn-sm"
                                                    onClick={() => handleApprove(user.id, user.username)}
                                                >
                                                    ✅ 승인
                                                </button>
                                                <button
                                                    className="btn btn-danger btn-sm"
                                                    onClick={() => handleReject(user.id, user.username)}
                                                >
                                                    ❌ 거절
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Create User Modal */}
            {showCreateModal && (
                <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3 className="modal-title">➕ 새 사용자 생성</h3>
                            <button className="modal-close" onClick={() => setShowCreateModal(false)}>×</button>
                        </div>
                        <form onSubmit={handleCreateUser}>
                            <div className="form-group">
                                <label className="form-label">사용자명</label>
                                <input
                                    type="text"
                                    className="form-input"
                                    value={createForm.username}
                                    onChange={e => setCreateForm({ ...createForm, username: e.target.value })}
                                    placeholder="사용자명을 입력하세요"
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">이메일</label>
                                <input
                                    type="email"
                                    className="form-input"
                                    value={createForm.email}
                                    onChange={e => setCreateForm({ ...createForm, email: e.target.value })}
                                    placeholder="이메일을 입력하세요"
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">비밀번호</label>
                                <input
                                    type="password"
                                    className="form-input"
                                    value={createForm.password}
                                    onChange={e => setCreateForm({ ...createForm, password: e.target.value })}
                                    placeholder="비밀번호 (8자 이상)"
                                    required
                                    minLength={8}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">비밀번호 확인</label>
                                <input
                                    type="password"
                                    className="form-input"
                                    value={createForm.confirmPassword}
                                    onChange={e => setCreateForm({ ...createForm, confirmPassword: e.target.value })}
                                    placeholder="비밀번호를 다시 입력하세요"
                                    required
                                />
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                                    취소
                                </button>
                                <button type="submit" className="btn btn-primary" disabled={creating}>
                                    {creating ? '생성 중...' : '사용자 생성'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </Layout>
    )
}


// Organization Select Page (for users without organization)
function OrganizationSelectPage() {
    const [organizations, setOrganizations] = useState([])
    const [myRequests, setMyRequests] = useState([])
    const [orgStatus, setOrgStatus] = useState(null)
    const [loading, setLoading] = useState(true)
    const [selectedOrg, setSelectedOrg] = useState(null)
    const [requestReason, setRequestReason] = useState('')
    const [showModal, setShowModal] = useState(false)

    useEffect(() => {
        loadData()
    }, [])

    const loadData = async () => {
        try {
            const [orgsData, requestsData, statusData] = await Promise.all([
                api.getAvailableOrganizations(),
                api.getMyJoinRequests(),
                api.getUserOrgStatus(),
            ])
            setOrganizations(orgsData)
            setMyRequests(requestsData)
            setOrgStatus(statusData)
        } catch (err) {
            console.error('Failed to load data:', err)
        } finally {
            setLoading(false)
        }
    }

    const handleJoinRequest = async () => {
        if (!selectedOrg) return
        try {
            await api.requestToJoinOrg(selectedOrg.id, requestReason)
            alert('가입 요청이 제출되었습니다!')
            setShowModal(false)
            setRequestReason('')
            loadData()
        } catch (err) {
            alert('요청 실패: ' + err.message)
        }
    }

    const handleSkip = async () => {
        try {
            await api.skipOrganization()
            alert('독립 사용자로 진행합니다.')
        } catch (err) {
            alert('실패: ' + err.message)
        }
    }

    if (loading) {
        return <Layout><div className="loading">Loading...</div></Layout>
    }

    // If user already has an organization
    if (orgStatus?.has_organization) {
        return (
            <Layout>
                <div className="page-header">
                    <h1>🏢 조직</h1>
                </div>
                <div className="card">
                    <h3>현재 조직</h3>
                    <p style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'bold', color: 'var(--color-primary)' }}>
                        {orgStatus.organization_name}
                    </p>
                    {orgStatus.is_org_admin && (
                        <span className="badge badge-primary">조직 관리자</span>
                    )}
                </div>
            </Layout>
        )
    }

    return (
        <Layout>
            <div className="page-header">
                <h1>🏢 조직 선택</h1>
                <p style={{ color: 'var(--color-text-muted)' }}>
                    조직에 가입하면 해당 조직의 모델에 접근할 수 있습니다.
                </p>
            </div>

            {/* Pending Request Status */}
            {orgStatus?.has_pending_request && (
                <div className="card" style={{ background: 'var(--color-info-muted)', borderColor: 'var(--color-info)' }}>
                    <h3>⏳ 대기 중인 요청</h3>
                    <p>
                        <strong>{orgStatus.pending_org_name}</strong> 조직 가입 승인을 기다리고 있습니다.
                    </p>
                </div>
            )}

            {/* My Requests History */}
            {myRequests.length > 0 && (
                <div className="card">
                    <h3>📋 내 가입 요청 내역</h3>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>조직</th>
                                <th>상태</th>
                                <th>요청일</th>
                                <th>응답</th>
                            </tr>
                        </thead>
                        <tbody>
                            {myRequests.map(req => (
                                <tr key={req.id}>
                                    <td>{req.organization_name}</td>
                                    <td>
                                        <span className={`badge ${req.status === 'pending' ? 'badge-warning' :
                                            req.status === 'approved' ? 'badge-success' : 'badge-danger'
                                            }`}>
                                            {req.status === 'pending' ? '대기' :
                                                req.status === 'approved' ? '승인' : '거절'}
                                        </span>
                                    </td>
                                    <td>{new Date(req.created_at).toLocaleDateString()}</td>
                                    <td>{req.response_note || '-'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Available Organizations */}
            <div className="card">
                <h3>🏛️ 가입 가능한 조직</h3>
                {organizations.length === 0 ? (
                    <p style={{ color: 'var(--color-text-muted)' }}>가입 가능한 조직이 없습니다.</p>
                ) : (
                    <div style={{ display: 'grid', gap: 'var(--spacing-4)' }}>
                        {organizations.map(org => (
                            <div key={org.id} className="card" style={{ background: 'var(--color-bg-secondary)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <h4 style={{ margin: 0 }}>{org.name}</h4>
                                        {org.description && (
                                            <p style={{ margin: 'var(--spacing-2) 0 0', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                                                {org.description}
                                            </p>
                                        )}
                                    </div>
                                    <button
                                        className="btn btn-primary"
                                        onClick={() => { setSelectedOrg(org); setShowModal(true); }}
                                    >
                                        가입 요청
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Skip Option */}
            <div className="card" style={{ textAlign: 'center' }}>
                <p>조직 없이 개별 사용자로 진행할 수도 있습니다.</p>
                <button className="btn btn-secondary" onClick={handleSkip}>
                    🚶 조직 없이 진행
                </button>
            </div>

            {/* Join Request Modal */}
            {showModal && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 1000
                }}>
                    <div className="card" style={{ width: '400px', maxWidth: '90%' }}>
                        <h3>📝 가입 요청</h3>
                        <p><strong>{selectedOrg?.name}</strong> 조직에 가입을 요청합니다.</p>
                        <div className="form-group">
                            <label className="form-label">요청 사유 (선택)</label>
                            <textarea
                                className="form-input"
                                rows={3}
                                value={requestReason}
                                onChange={e => setRequestReason(e.target.value)}
                                placeholder="가입 요청 사유를 입력하세요..."
                            />
                        </div>
                        <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => setShowModal(false)}>취소</button>
                            <button className="btn btn-primary" onClick={handleJoinRequest}>요청 제출</button>
                        </div>
                    </div>
                </div>
            )}
        </Layout>
    )
}

// Organization Join Requests Management Page (for org admins)
function OrgJoinRequestsPage() {
    const [requests, setRequests] = useState([])
    const [orgStatus, setOrgStatus] = useState(null)
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('pending')

    useEffect(() => {
        loadData()
    }, [filter])

    const loadData = async () => {
        try {
            const statusData = await api.getUserOrgStatus()
            setOrgStatus(statusData)

            if (statusData.is_org_admin && statusData.organization_id) {
                const requestsData = await api.getOrgJoinRequests(statusData.organization_id, filter === 'all' ? null : filter)
                setRequests(requestsData)
            }
        } catch (err) {
            console.error('Failed to load data:', err)
        } finally {
            setLoading(false)
        }
    }

    const handleApprove = async (requestId) => {
        if (!confirm('이 요청을 승인하시겠습니까?')) return
        try {
            await api.approveJoinRequest(requestId)
            alert('승인되었습니다.')
            loadData()
        } catch (err) {
            alert('실패: ' + err.message)
        }
    }

    const handleReject = async (requestId) => {
        const reason = prompt('거절 사유를 입력하세요:')
        if (reason === null) return
        try {
            await api.rejectJoinRequest(requestId, reason)
            alert('거절되었습니다.')
            loadData()
        } catch (err) {
            alert('실패: ' + err.message)
        }
    }

    if (loading) {
        return <Layout><div className="loading">Loading...</div></Layout>
    }

    if (!orgStatus?.is_org_admin) {
        return (
            <Layout>
                <div className="page-header">
                    <h1>⛔ 접근 권한 없음</h1>
                </div>
                <div className="card">
                    <p>조직 관리자만 접근할 수 있습니다.</p>
                </div>
            </Layout>
        )
    }

    const pendingCount = requests.filter(r => r.status === 'pending').length

    return (
        <Layout>
            <div className="page-header">
                <h1>👥 가입 요청 관리</h1>
                <p style={{ color: 'var(--color-text-muted)' }}>
                    {orgStatus.organization_name} 조직의 가입 요청을 관리합니다.
                    {pendingCount > 0 && (
                        <span className="badge badge-warning" style={{ marginLeft: 'var(--spacing-2)' }}>
                            {pendingCount}개 대기
                        </span>
                    )}
                </p>
            </div>

            {/* Filter */}
            <div className="card">
                <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                    {['pending', 'approved', 'rejected', 'all'].map(f => (
                        <button
                            key={f}
                            className={`btn ${filter === f ? 'btn-primary' : 'btn-secondary'}`}
                            onClick={() => setFilter(f)}
                        >
                            {f === 'pending' ? '대기 중' : f === 'approved' ? '승인됨' : f === 'rejected' ? '거절됨' : '전체'}
                        </button>
                    ))}
                </div>
            </div>

            {/* Requests Table */}
            <div className="card">
                {requests.length === 0 ? (
                    <p style={{ color: 'var(--color-text-muted)', textAlign: 'center' }}>
                        {filter === 'pending' ? '대기 중인 요청이 없습니다.' : '요청이 없습니다.'}
                    </p>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>사용자</th>
                                <th>이메일</th>
                                <th>요청 사유</th>
                                <th>상태</th>
                                <th>요청일</th>
                                <th>작업</th>
                            </tr>
                        </thead>
                        <tbody>
                            {requests.map(req => (
                                <tr key={req.id}>
                                    <td>{req.user_username}</td>
                                    <td>{req.user_email}</td>
                                    <td>{req.request_reason || '-'}</td>
                                    <td>
                                        <span className={`badge ${req.status === 'pending' ? 'badge-warning' :
                                            req.status === 'approved' ? 'badge-success' : 'badge-danger'
                                            }`}>
                                            {req.status === 'pending' ? '대기' :
                                                req.status === 'approved' ? '승인' : '거절'}
                                        </span>
                                    </td>
                                    <td>{new Date(req.created_at).toLocaleDateString()}</td>
                                    <td>
                                        {req.status === 'pending' && (
                                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                                <button
                                                    className="btn btn-success"
                                                    style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                                    onClick={() => handleApprove(req.id)}
                                                >
                                                    승인
                                                </button>
                                                <button
                                                    className="btn btn-danger"
                                                    style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                                    onClick={() => handleReject(req.id)}
                                                >
                                                    거절
                                                </button>
                                            </div>
                                        )}
                                        {req.status !== 'pending' && (
                                            <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' }}>
                                                처리됨
                                            </span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </Layout>
    )
}

// Garak Results Viewer Component
function GarakResultsViewer({ result, onClose, onDownload }) {
    const [activeTab, setActiveTab] = useState('overview')
    const [expandedProbe, setExpandedProbe] = useState(null)

    const GARAK_CATEGORIES = {
        prompt_injection: { name: 'Prompt Injection', icon: '💉', color: '#dc3545', description: '시스템 프롬프트 무력화 시도' },
        jailbreak: { name: 'Jailbreak', icon: '🔓', color: '#fd7e14', description: '정책 우회 탈옥 시도' },
        hallucination: { name: 'Hallucination', icon: '🌀', color: '#6f42c1', description: '사실 오류 및 허위 정보 생성' },
        privacy: { name: 'Privacy', icon: '🔐', color: '#17a2b8', description: '개인정보 유출 및 추론' },
        toxicity: { name: 'Toxicity', icon: '☠️', color: '#e83e8c', description: '유해 콘텐츠 생성' },
        malware: { name: 'Malware/Misuse', icon: '🦠', color: '#343a40', description: '악성코드 및 악용 시나리오' },
        robustness: { name: 'Robustness', icon: '💪', color: '#28a745', description: '모델 안정성 테스트' },
    }

    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'critical': return '#dc3545'
            case 'high': return '#fd7e14'
            case 'medium': return '#ffc107'
            case 'low': return '#28a745'
            default: return '#6c757d'
        }
    }

    const getFailureRateColor = (rate) => {
        if (rate >= 0.5) return '#dc3545'
        if (rate >= 0.25) return '#fd7e14'
        if (rate >= 0.1) return '#ffc107'
        return '#28a745'
    }

    // Parse detailed results into categories
    const parseResults = () => {
        const detailedResults = result.detailed_results || {}
        const probeResults = detailedResults.results || detailedResults.probes || []

        const categorized = {}
        for (const cat of Object.keys(GARAK_CATEGORIES)) {
            categorized[cat] = []
        }

        probeResults.forEach(probe => {
            const probeName = probe.probe || probe.name || ''
            const category = probeName.split('.')[0] || 'unknown'
            if (categorized[category]) {
                categorized[category].push(probe)
            }
        })

        return categorized
    }

    const categorizedResults = parseResults()

    const summaryData = result.detailed_results?.summary || {
        total_probes: result.total_probes || 0,
        high_risk: result.critical_count + result.high_count || 0,
        medium_risk: result.medium_count || 0,
        low_risk: result.low_count || 0,
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal" style={{ maxWidth: '1000px', width: '95%', maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)', borderBottom: '1px solid var(--color-border)', paddingBottom: 'var(--spacing-3)' }}>
                    <div>
                        <h2 style={{ margin: 0 }}>🛡️ Garak Security Scan Results</h2>
                        <p style={{ margin: 'var(--spacing-1) 0 0 0', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                            {result.model_alias} • {new Date(result.created_at || result.completed_at).toLocaleString()}
                        </p>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                        <button className="btn btn-secondary" onClick={onDownload}>⬇️ 다운로드</button>
                        <button className="btn" onClick={onClose}>✕</button>
                    </div>
                </div>

                {/* Tabs */}
                <div style={{ display: 'flex', gap: 'var(--spacing-1)', borderBottom: '1px solid var(--color-border)', marginBottom: 'var(--spacing-3)' }}>
                    {[
                        { id: 'overview', label: '📊 Overview' },
                        { id: 'categories', label: '📁 카테고리별' },
                        { id: 'probes', label: '🔬 프로브 상세' },
                        { id: 'raw', label: '📄 Raw JSON' },
                    ].map(tab => (
                        <button
                            key={tab.id}
                            className={`btn ${activeTab === tab.id ? 'btn-primary' : ''}`}
                            style={{ borderRadius: '8px 8px 0 0' }}
                            onClick={() => setActiveTab(tab.id)}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div style={{ flex: 1, overflow: 'auto', padding: 'var(--spacing-2)' }}>
                    {/* Overview Tab */}
                    {activeTab === 'overview' && (
                        <div>
                            {/* Risk Score */}
                            <div style={{ display: 'flex', gap: 'var(--spacing-4)', marginBottom: 'var(--spacing-4)', flexWrap: 'wrap' }}>
                                <div style={{
                                    textAlign: 'center',
                                    padding: 'var(--spacing-4)',
                                    background: 'linear-gradient(135deg, rgba(40,167,69,0.1), rgba(40,167,69,0.05))',
                                    border: `2px solid ${getSeverityColor(result.security_score >= 70 ? 'low' : result.security_score >= 50 ? 'medium' : 'high')}`,
                                    borderRadius: '12px',
                                    minWidth: '150px'
                                }}>
                                    <div style={{ fontSize: '3rem', fontWeight: 'bold', color: getSeverityColor(result.security_score >= 70 ? 'low' : result.security_score >= 50 ? 'medium' : 'high') }}>
                                        {result.security_score || 0}
                                    </div>
                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Security Score</div>
                                </div>

                                <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 'var(--spacing-3)' }}>
                                    <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px' }}>
                                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{summaryData.total_probes}</div>
                                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>총 프로브</div>
                                    </div>
                                    <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', borderLeft: '3px solid #dc3545' }}>
                                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#dc3545' }}>{summaryData.high_risk}</div>
                                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>High Risk</div>
                                    </div>
                                    <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', borderLeft: '3px solid #ffc107' }}>
                                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#ffc107' }}>{summaryData.medium_risk}</div>
                                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Medium Risk</div>
                                    </div>
                                    <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', borderLeft: '3px solid #28a745' }}>
                                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#28a745' }}>{summaryData.low_risk}</div>
                                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Low Risk</div>
                                    </div>
                                </div>
                            </div>

                            {/* Category Summary Cards */}
                            <h4 style={{ marginBottom: 'var(--spacing-3)' }}>카테고리별 요약</h4>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--spacing-3)' }}>
                                {Object.entries(GARAK_CATEGORIES).map(([key, cat]) => {
                                    const probes = categorizedResults[key] || []
                                    const failedCount = probes.filter(p => (p.failures || 0) > 0).length
                                    return (
                                        <div key={key} style={{
                                            padding: 'var(--spacing-3)',
                                            background: 'var(--color-bg)',
                                            borderRadius: '8px',
                                            borderLeft: `4px solid ${cat.color}`,
                                            opacity: probes.length === 0 ? 0.5 : 1
                                        }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                                                    <span style={{ fontSize: '1.5rem' }}>{cat.icon}</span>
                                                    <div>
                                                        <div style={{ fontWeight: 600 }}>{cat.name}</div>
                                                        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>{cat.description}</div>
                                                    </div>
                                                </div>
                                                <div style={{ textAlign: 'right' }}>
                                                    <div style={{ fontWeight: 'bold', color: failedCount > 0 ? '#dc3545' : '#28a745' }}>
                                                        {failedCount}/{probes.length}
                                                    </div>
                                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>실패</div>
                                                </div>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    )}

                    {/* Categories Tab */}
                    {activeTab === 'categories' && (
                        <div>
                            {Object.entries(GARAK_CATEGORIES).map(([key, cat]) => {
                                const probes = categorizedResults[key] || []
                                if (probes.length === 0) return null
                                return (
                                    <div key={key} style={{ marginBottom: 'var(--spacing-4)' }}>
                                        <div style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 'var(--spacing-2)',
                                            marginBottom: 'var(--spacing-2)',
                                            padding: 'var(--spacing-2)',
                                            background: cat.color + '20',
                                            borderRadius: '8px'
                                        }}>
                                            <span style={{ fontSize: '1.5rem' }}>{cat.icon}</span>
                                            <h4 style={{ margin: 0, color: cat.color }}>{cat.name}</h4>
                                            <span className="badge" style={{ background: cat.color }}>{probes.length} probes</span>
                                        </div>
                                        <table className="table">
                                            <thead>
                                                <tr>
                                                    <th>Probe</th>
                                                    <th>Detector</th>
                                                    <th>Attempts</th>
                                                    <th>Failures</th>
                                                    <th>Failure Rate</th>
                                                    <th>Severity</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {probes.map((probe, i) => (
                                                    <tr key={i}>
                                                        <td><code>{probe.probe || probe.name}</code></td>
                                                        <td>{probe.detector || '-'}</td>
                                                        <td>{probe.attempts || 0}</td>
                                                        <td style={{ color: (probe.failures || 0) > 0 ? '#dc3545' : '#28a745' }}>{probe.failures || 0}</td>
                                                        <td>
                                                            <div style={{
                                                                display: 'inline-block',
                                                                padding: '2px 8px',
                                                                borderRadius: '4px',
                                                                background: getFailureRateColor(probe.failure_rate || 0) + '20',
                                                                color: getFailureRateColor(probe.failure_rate || 0)
                                                            }}>
                                                                {((probe.failure_rate || 0) * 100).toFixed(1)}%
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <span className="badge" style={{ background: getSeverityColor(probe.severity), color: '#fff' }}>
                                                                {probe.severity || 'unknown'}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )
                            })}
                        </div>
                    )}

                    {/* Probes Tab */}
                    {activeTab === 'probes' && (
                        <div>
                            {Object.entries(categorizedResults).flatMap(([cat, probes]) =>
                                probes.map((probe, i) => (
                                    <div key={`${cat}-${i}`} style={{
                                        marginBottom: 'var(--spacing-3)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: '8px',
                                        overflow: 'hidden'
                                    }}>
                                        <div
                                            style={{
                                                padding: 'var(--spacing-3)',
                                                background: 'var(--color-bg)',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center'
                                            }}
                                            onClick={() => setExpandedProbe(expandedProbe === `${cat}-${i}` ? null : `${cat}-${i}`)}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
                                                <span>{expandedProbe === `${cat}-${i}` ? '▼' : '▶'}</span>
                                                <code style={{ fontWeight: 600 }}>{probe.probe || probe.name}</code>
                                                <span className="badge" style={{ background: getSeverityColor(probe.severity) }}>{probe.severity}</span>
                                            </div>
                                            <div style={{ display: 'flex', gap: 'var(--spacing-3)', alignItems: 'center' }}>
                                                <span style={{ color: (probe.failures || 0) > 0 ? '#dc3545' : '#28a745' }}>
                                                    {probe.failures || 0}/{probe.attempts || 0} failures
                                                </span>
                                                <span style={{
                                                    padding: '2px 8px',
                                                    borderRadius: '4px',
                                                    background: getFailureRateColor(probe.failure_rate || 0),
                                                    color: '#fff'
                                                }}>
                                                    {((probe.failure_rate || 0) * 100).toFixed(1)}%
                                                </span>
                                            </div>
                                        </div>

                                        {expandedProbe === `${cat}-${i}` && probe.details && (
                                            <div style={{ padding: 'var(--spacing-3)', borderTop: '1px solid var(--color-border)' }}>
                                                <h5>상세 결과</h5>
                                                {probe.details.map((detail, j) => (
                                                    <div key={j} style={{
                                                        marginBottom: 'var(--spacing-2)',
                                                        padding: 'var(--spacing-2)',
                                                        background: 'var(--color-bg)',
                                                        borderRadius: '4px',
                                                        fontSize: 'var(--font-size-sm)'
                                                    }}>
                                                        <div><strong>Prompt:</strong> {detail.prompt}</div>
                                                        <div style={{ marginTop: 'var(--spacing-1)' }}><strong>Response:</strong> {detail.response}</div>
                                                        {detail.detected_issue && (
                                                            <div style={{ marginTop: 'var(--spacing-1)', color: '#dc3545' }}>
                                                                <strong>Issue:</strong> {detail.detected_issue} (confidence: {(detail.confidence * 100).toFixed(0)}%)
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    )}

                    {/* Raw JSON Tab */}
                    {activeTab === 'raw' && (
                        <pre style={{
                            background: '#1e1e1e',
                            color: '#d4d4d4',
                            padding: 'var(--spacing-3)',
                            borderRadius: '8px',
                            overflow: 'auto',
                            fontSize: 'var(--font-size-sm)',
                            maxHeight: '500px'
                        }}>
                            {JSON.stringify(result.detailed_results || result, null, 2)}
                        </pre>
                    )}
                </div>
            </div>
        </div>
    )
}

// Security Scan Page
function SecurityScanPage() {
    const [models, setModels] = useState([])
    const [categories, setCategories] = useState([])
    const [scanResults, setScanResults] = useState([])
    const [selectedModel, setSelectedModel] = useState('')
    const [scanType, setScanType] = useState('quick')
    const [scanEngine, setScanEngine] = useState('builtin')  // 'builtin' or 'garak'
    const [scanning, setScanning] = useState(false)
    const [currentScan, setCurrentScan] = useState(null)
    const [selectedResult, setSelectedResult] = useState(null)
    const [loading, setLoading] = useState(true)
    const [garakStatus, setGarakStatus] = useState(null)

    useEffect(() => {
        loadData()
    }, [])

    const loadData = async () => {
        try {
            const [modelsData, categoriesData, resultsData, garakData] = await Promise.all([
                api.getScannableModels().catch(() => []),
                api.getScanCategories().catch(() => []),
                api.getScanResults().catch(() => []),
                api.getGarakStatus().catch(() => ({ available: false }))
            ])
            setModels(modelsData || [])
            setCategories(categoriesData || [])
            setScanResults(resultsData || [])
            setGarakStatus(garakData)
        } catch (err) {
            console.error('Failed to load security scan data:', err)
        } finally {
            setLoading(false)
        }
    }

    const handleStartScan = async () => {
        if (!selectedModel) {
            alert('모델을 선택하세요.')
            return
        }
        setScanning(true)
        setCurrentScan(null)
        try {
            let result
            if (scanEngine === 'garak') {
                result = await api.startGarakScan(selectedModel, scanType)
            } else {
                result = await api.startSecurityScan(selectedModel, scanType)
            }
            setCurrentScan({ id: result.scan_id, status: 'pending' })
            // Immediately refresh to show pending scan in history
            await loadData()
            // Poll for completion
            pollScanResult(result.scan_id)
        } catch (err) {
            alert('스캔 시작 실패: ' + err.message)
            setScanning(false)
        }
    }

    const pollScanResult = async (scanId) => {
        const poll = async () => {
            try {
                const result = await api.getScanResult(scanId)
                setCurrentScan(result)
                if (result.status === 'completed' || result.status === 'failed') {
                    setScanning(false)
                    loadData()  // Final refresh when complete
                } else {
                    // Refresh history during scan to show status updates
                    const resultsData = await api.getScanResults().catch(() => [])
                    setScanResults(resultsData || [])
                    setTimeout(poll, 2000)
                }
            } catch (err) {
                console.error('Poll failed:', err)
                setScanning(false)
                loadData()
            }
        }
        poll()
    }

    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'critical': return '#dc3545'
            case 'high': return '#fd7e14'
            case 'medium': return '#ffc107'
            case 'low': return '#28a745'
            default: return '#6c757d'
        }
    }

    const getScoreColor = (score) => {
        if (score >= 80) return '#28a745'
        if (score >= 60) return '#ffc107'
        if (score >= 40) return '#fd7e14'
        return '#dc3545'
    }

    if (loading) {
        return <Layout><div className="loading">Loading...</div></Layout>
    }

    return (
        <Layout>
            <div className="page-header">
                <h1 className="page-title">🛡️ Security Scan</h1>
                <p style={{ color: 'var(--color-text-muted)' }}>LLM 모델 보안 취약점 스캔</p>
            </div>

            {/* Garak Status Banner */}
            <div className="card" style={{
                marginBottom: 'var(--spacing-4)',
                background: garakStatus?.available ? 'linear-gradient(135deg, #1a472a 0%, #2d5a3d 100%)' : 'linear-gradient(135deg, #4a3728 0%, #5a4838 100%)',
                border: 'none'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                            <span>{garakStatus?.available ? '✅' : '⚠️'}</span>
                            Garak LLM Security Scanner
                        </h3>
                        <p style={{ margin: 'var(--spacing-2) 0 0 0', opacity: 0.8, fontSize: 'var(--font-size-sm)' }}>
                            {garakStatus?.available
                                ? `v${garakStatus.version} - 60+ 보안 프로브로 종합적인 취약점 분석`
                                : 'Garak이 설치되지 않았습니다. 기본 스캐너를 사용합니다.'}
                        </p>
                    </div>
                    {garakStatus?.available && (
                        <span className="badge badge-success" style={{ fontSize: 'var(--font-size-sm)', padding: 'var(--spacing-2) var(--spacing-3)' }}>
                            Ready
                        </span>
                    )}
                </div>
            </div>

            {/* Scan Controls */}
            <div className="card" style={{ marginBottom: 'var(--spacing-4)' }}>
                <h3 style={{ marginBottom: 'var(--spacing-4)' }}>새 스캔 시작</h3>
                <div style={{ display: 'flex', gap: 'var(--spacing-3)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '200px' }}>
                        <label className="form-label">모델 선택</label>
                        <select
                            className="form-select"
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                            disabled={scanning}
                        >
                            <option value="">-- 모델 선택 --</option>
                            {models.map(m => (
                                <option key={m.id} value={m.id}>{m.alias} ({m.display_name})</option>
                            ))}
                        </select>
                    </div>
                    <div style={{ minWidth: '150px' }}>
                        <label className="form-label">스캔 엔진</label>
                        <select
                            className="form-select"
                            value={scanEngine}
                            onChange={(e) => setScanEngine(e.target.value)}
                            disabled={scanning}
                        >
                            <option value="builtin">기본 스캐너</option>
                            <option value="garak" disabled={!garakStatus?.available}>
                                Garak {garakStatus?.available ? `(v${garakStatus.version})` : '(미설치)'}
                            </option>
                        </select>
                    </div>
                    <div style={{ minWidth: '150px' }}>
                        <label className="form-label">스캔 타입</label>
                        <select
                            className="form-select"
                            value={scanType}
                            onChange={(e) => setScanType(e.target.value)}
                            disabled={scanning}
                        >
                            <option value="quick">Quick (빠른 스캔)</option>
                            <option value="standard">Standard (표준 스캔)</option>
                        </select>
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={handleStartScan}
                        disabled={scanning || !selectedModel}
                    >
                        {scanning ? '스캔 중...' : '🔍 스캔 시작'}
                    </button>
                </div>
            </div>

            {/* Current Scan Progress */}
            {currentScan && (
                <div className="card" style={{ marginBottom: 'var(--spacing-4)', borderLeft: `4px solid ${getScoreColor(currentScan.security_score || 50)}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-3)' }}>
                        <h3>현재 스캔 결과: {currentScan.model_alias}</h3>
                        <span className={`badge ${currentScan.status === 'completed' ? 'badge-success' : currentScan.status === 'failed' ? 'badge-danger' : 'badge-warning'}`}>
                            {currentScan.status}
                        </span>
                    </div>

                    {currentScan.status === 'completed' && (
                        <>
                            <div style={{ display: 'flex', gap: 'var(--spacing-4)', marginBottom: 'var(--spacing-3)', flexWrap: 'wrap' }}>
                                <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', minWidth: '100px' }}>
                                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: getScoreColor(currentScan.security_score) }}>
                                        {currentScan.security_score}
                                    </div>
                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>보안 점수</div>
                                </div>
                                <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', minWidth: '80px' }}>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{currentScan.total_probes}</div>
                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>총 테스트</div>
                                </div>
                                <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', minWidth: '80px' }}>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#28a745' }}>{currentScan.passed_probes}</div>
                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>통과</div>
                                </div>
                                <div style={{ textAlign: 'center', padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', minWidth: '80px' }}>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#dc3545' }}>{currentScan.failed_probes}</div>
                                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>실패</div>
                                </div>
                            </div>

                            {currentScan.vulnerabilities?.length > 0 && (
                                <div>
                                    <h4 style={{ marginBottom: 'var(--spacing-2)' }}>발견된 취약점</h4>
                                    <div className="table-container">
                                        <table className="table">
                                            <thead>
                                                <tr>
                                                    <th>카테고리</th>
                                                    <th>심각도</th>
                                                    <th>프로브</th>
                                                    <th>권고사항</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {currentScan.vulnerabilities.map((v, i) => (
                                                    <tr key={i}>
                                                        <td>{v.category}</td>
                                                        <td>
                                                            <span className="badge" style={{ background: getSeverityColor(v.severity), color: '#fff' }}>
                                                                {v.severity}
                                                            </span>
                                                        </td>
                                                        <td>{v.probe_name}</td>
                                                        <td style={{ fontSize: 'var(--font-size-sm)' }}>{v.recommendation}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* Scan Categories */}
            <div className="card" style={{ marginBottom: 'var(--spacing-4)' }}>
                <h3 style={{ marginBottom: 'var(--spacing-3)' }}>테스트 카테고리</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--spacing-3)' }}>
                    {categories.map(cat => (
                        <div key={cat.id} style={{ padding: 'var(--spacing-3)', background: 'var(--color-bg)', borderRadius: '8px', borderLeft: `3px solid ${getSeverityColor(cat.severity)}` }}>
                            <div style={{ fontWeight: 500, marginBottom: 'var(--spacing-1)' }}>{cat.name}</div>
                            <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginBottom: 'var(--spacing-2)' }}>{cat.description}</div>
                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                <span className="badge" style={{ background: getSeverityColor(cat.severity), color: '#fff' }}>{cat.severity}</span>
                                <span className="badge badge-secondary">{cat.probe_count} probes</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Scan History */}
            <div className="card">
                <h3 style={{ marginBottom: 'var(--spacing-3)' }}>스캔 이력</h3>
                {scanResults.length === 0 ? (
                    <p style={{ color: 'var(--color-text-muted)', textAlign: 'center' }}>아직 스캔 기록이 없습니다.</p>
                ) : (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>모델</th>
                                    <th>타입</th>
                                    <th>상태</th>
                                    <th>점수</th>
                                    <th>취약점</th>
                                    <th>날짜</th>
                                    <th>액션</th>
                                </tr>
                            </thead>
                            <tbody>
                                {scanResults.map(scan => (
                                    <tr key={scan.id}>
                                        <td>{scan.model_alias}</td>
                                        <td><span className="badge badge-secondary">{scan.scan_type}</span></td>
                                        <td>
                                            <span className={`badge ${scan.status === 'completed' ? 'badge-success' : scan.status === 'failed' ? 'badge-danger' : 'badge-warning'}`}>
                                                {scan.status}
                                            </span>
                                        </td>
                                        <td>
                                            {scan.security_score !== null && (
                                                <span style={{ fontWeight: 'bold', color: getScoreColor(scan.security_score) }}>
                                                    {scan.security_score}/100
                                                </span>
                                            )}
                                        </td>
                                        <td>{scan.total_vulnerabilities}</td>
                                        <td>{new Date(scan.created_at).toLocaleString()}</td>
                                        <td>
                                            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                                                <button
                                                    className="btn btn-sm"
                                                    onClick={async () => {
                                                        const result = await api.getScanResult(scan.id)
                                                        setSelectedResult(result)
                                                    }}
                                                    title="상세 보기"
                                                >
                                                    👁️
                                                </button>
                                                {scan.status === 'completed' && (
                                                    <button
                                                        className="btn btn-sm btn-secondary"
                                                        onClick={() => {
                                                            const url = api.downloadScanResult(scan.id)
                                                            window.open(url, '_blank')
                                                        }}
                                                        title="결과 다운로드"
                                                    >
                                                        ⬇️
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Garak Results Viewer Modal */}
            {selectedResult && (
                <GarakResultsViewer
                    result={selectedResult}
                    onClose={() => setSelectedResult(null)}
                    onDownload={() => {
                        const url = api.downloadScanResult(selectedResult.id)
                        window.open(url, '_blank')
                    }}
                />
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

    // External PII API endpoints state
    const [piiEndpoints, setPiiEndpoints] = useState([])
    const [showAddEndpoint, setShowAddEndpoint] = useState(false)
    const [newEndpoint, setNewEndpoint] = useState({
        name: '', api_url: '', api_type: 'presidio', priority: 10,
        health_check_path: '/health', analyze_path: '/analyze'
    })
    const [editEndpoint, setEditEndpoint] = useState(null)
    const [endpointTestText, setEndpointTestText] = useState('')
    const [endpointTestResult, setEndpointTestResult] = useState(null)

    // Runtime settings (dynamic toggle)
    const [runtimeSettings, setRuntimeSettings] = useState({ enabled: true, mask_request: true, mask_response: true })

    useEffect(() => {
        loadConfig()
    }, [])

    const loadConfig = async () => {
        try {
            const [configData, entitiesData, modelsData, recognizersData, endpointsData, runtimeData] = await Promise.all([
                api.getPIIConfig(),
                api.getPIIEntities(),
                api.getNlpModels().catch(() => []),
                api.getRecognizers().catch(() => []),
                api.getPiiEndpoints().catch(() => []),
                api.getRuntimeSettings().catch(() => ({ enabled: true, mask_request: true, mask_response: true }))
            ])
            setConfig(configData)
            setEntities(entitiesData.entities || [])
            setNlpModels(modelsData || [])
            setRecognizers(recognizersData || [])
            setPiiEndpoints(endpointsData || [])
            setRuntimeSettings(runtimeData)
        } catch (err) {
            console.error('Failed to load PII config:', err)
        } finally {
            setLoading(false)
        }
    }

    const handleToggleRuntime = async (key, value) => {
        try {
            const result = await api.updateRuntimeSettings({ [key]: value })
            setRuntimeSettings(result)
        } catch (err) {
            alert('설정 변경 실패: ' + err.message)
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

    const handleToggleNlpModel = async (langCode) => {
        try {
            await api.toggleNlpModel(langCode)
            loadConfig()  // Refresh to get new status
        } catch (err) {
            alert('토글 실패: ' + err.message)
        }
    }

    // External PII API Endpoint handlers
    const handleAddEndpoint = async () => {
        if (!newEndpoint.name || !newEndpoint.api_url) {
            alert('이름과 API URL은 필수입니다.')
            return
        }
        try {
            await api.createPiiEndpoint(newEndpoint)
            setShowAddEndpoint(false)
            setNewEndpoint({
                name: '', api_url: '', api_type: 'presidio', priority: 10,
                health_check_path: '/health', analyze_path: '/analyze'
            })
            loadConfig()
        } catch (err) {
            alert('추가 실패: ' + err.message)
        }
    }

    const handleUpdateEndpoint = async () => {
        if (!editEndpoint) return
        try {
            await api.updatePiiEndpoint(editEndpoint.id, {
                name: editEndpoint.name,
                api_url: editEndpoint.api_url,
                api_type: editEndpoint.api_type,
                priority: editEndpoint.priority,
                health_check_path: editEndpoint.health_check_path,
                analyze_path: editEndpoint.analyze_path,
                is_enabled: editEndpoint.is_enabled
            })
            setEditEndpoint(null)
            loadConfig()
        } catch (err) {
            alert('수정 실패: ' + err.message)
        }
    }

    const handleDeleteEndpoint = async (id) => {
        if (!confirm('이 PII API 엔드포인트를 삭제하시겠습니까?')) return
        try {
            await api.deletePiiEndpoint(id)
            loadConfig()
        } catch (err) {
            alert('삭제 실패: ' + err.message)
        }
    }

    const handleTestEndpoint = async (endpoint) => {
        if (!endpointTestText) {
            alert('테스트할 텍스트를 입력해주세요.')
            return
        }
        try {
            const result = await api.testPiiEndpoint(endpoint.id, endpointTestText)
            setEndpointTestResult(result)
        } catch (err) {
            setEndpointTestResult({ success: false, error: err.message })
        }
    }

    const handleCheckHealth = async (endpoint) => {
        try {
            const result = await api.checkPiiEndpointHealth(endpoint.id)
            alert(result.healthy ? '✅ 연결 성공!' : `❌ 연결 실패: ${result.error || ''}`)
            loadConfig()
        } catch (err) {
            alert('헬스체크 실패: ' + err.message)
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
                                        <button
                                            className={`btn ${runtimeSettings?.enabled ? 'btn-primary' : 'btn-secondary'}`}
                                            style={{ minWidth: '60px' }}
                                            onClick={() => handleToggleRuntime('enabled', !runtimeSettings?.enabled)}
                                        >
                                            {runtimeSettings?.enabled ? 'ON' : 'OFF'}
                                        </button>
                                    </td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>요청 마스킹</td>
                                    <td>
                                        <button
                                            className={`btn ${runtimeSettings?.mask_request ? 'btn-primary' : 'btn-secondary'}`}
                                            style={{ minWidth: '60px' }}
                                            onClick={() => handleToggleRuntime('mask_request', !runtimeSettings?.mask_request)}
                                            disabled={!runtimeSettings?.enabled}
                                        >
                                            {runtimeSettings?.mask_request ? 'ON' : 'OFF'}
                                        </button>
                                    </td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>응답 마스킹</td>
                                    <td>
                                        <button
                                            className={`btn ${runtimeSettings?.mask_response ? 'btn-primary' : 'btn-secondary'}`}
                                            style={{ minWidth: '60px' }}
                                            onClick={() => handleToggleRuntime('mask_response', !runtimeSettings?.mask_response)}
                                            disabled={!runtimeSettings?.enabled}
                                        >
                                            {runtimeSettings?.mask_response ? 'ON' : 'OFF'}
                                        </button>
                                    </td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>마스킹 방식</td>
                                    <td><code>{config?.mask_type}</code></td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: 500 }}>감지 언어</td>
                                    <td>
                                        <code>
                                            {nlpModels.filter(m => m.is_enabled).map(m => m.lang_code).join(', ') || 'en'}
                                        </code>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
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
                                    <button
                                        className={`btn ${model.is_enabled ? 'btn-primary' : 'btn-secondary'}`}
                                        style={{ padding: '4px 12px', fontSize: 'var(--font-size-xs)', minWidth: '50px' }}
                                        onClick={() => handleToggleNlpModel(model.lang_code)}
                                    >
                                        {model.is_enabled ? 'ON' : 'OFF'}
                                    </button>
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

            {/* External PII API Section */}
            <div className="card" style={{ marginTop: 'var(--spacing-4)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
                    <h3>🌐 외부 PII API</h3>
                    <button className="btn btn-primary" onClick={() => setShowAddEndpoint(!showAddEndpoint)}>
                        {showAddEndpoint ? '취소' : '+ API 추가'}
                    </button>
                </div>

                {showAddEndpoint && (
                    <div style={{
                        background: 'var(--color-bg-secondary)',
                        padding: 'var(--spacing-4)',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: 'var(--spacing-4)'
                    }}>
                        <h4 style={{ marginBottom: 'var(--spacing-3)' }}>새 PII API 등록</h4>
                        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
                            <div className="form-group">
                                <label className="form-label">이름</label>
                                <input
                                    className="form-input"
                                    placeholder="Presidio Analyzer"
                                    value={newEndpoint.name}
                                    onChange={e => setNewEndpoint({ ...newEndpoint, name: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">API URL</label>
                                <input
                                    className="form-input"
                                    placeholder="http://presidio:3000"
                                    value={newEndpoint.api_url}
                                    onChange={e => setNewEndpoint({ ...newEndpoint, api_url: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">API 타입</label>
                                <select
                                    className="form-input"
                                    value={newEndpoint.api_type}
                                    onChange={e => setNewEndpoint({ ...newEndpoint, api_type: e.target.value })}
                                >
                                    <option value="presidio">Presidio</option>
                                    <option value="custom">Custom</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">우선순위 (낮을수록 높음)</label>
                                <input
                                    className="form-input"
                                    type="number"
                                    min="1"
                                    max="100"
                                    value={newEndpoint.priority}
                                    onChange={e => setNewEndpoint({ ...newEndpoint, priority: parseInt(e.target.value) || 10 })}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">분석 경로</label>
                                <input
                                    className="form-input"
                                    placeholder="/analyze"
                                    value={newEndpoint.analyze_path}
                                    onChange={e => setNewEndpoint({ ...newEndpoint, analyze_path: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">헬스체크 경로</label>
                                <input
                                    className="form-input"
                                    placeholder="/health"
                                    value={newEndpoint.health_check_path}
                                    onChange={e => setNewEndpoint({ ...newEndpoint, health_check_path: e.target.value })}
                                />
                            </div>
                        </div>
                        <div style={{ marginTop: 'var(--spacing-4)' }}>
                            <button className="btn btn-primary" onClick={handleAddEndpoint}>추가</button>
                        </div>
                    </div>
                )}

                {piiEndpoints.length > 0 ? (
                    <div className="table-container">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>이름</th>
                                    <th>URL</th>
                                    <th>타입</th>
                                    <th>상태</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {piiEndpoints.map(ep => (
                                    <tr key={ep.id}>
                                        <td style={{ fontWeight: 500 }}>{ep.name}</td>
                                        <td><code style={{ fontSize: 'var(--font-size-xs)' }}>{ep.api_url}</code></td>
                                        <td><span className="badge badge-secondary">{ep.api_type}</span></td>
                                        <td>
                                            <span className={`badge ${ep.is_healthy ? 'badge-success' : 'badge-secondary'}`}>
                                                {ep.is_healthy ? '정상' : '오류'}
                                            </span>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', gap: 'var(--spacing-1)' }}>
                                                <button
                                                    className="btn btn-secondary"
                                                    style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                                    onClick={() => handleCheckHealth(ep)}
                                                >
                                                    테스트
                                                </button>
                                                <button
                                                    className="btn btn-secondary"
                                                    style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                                    onClick={() => setEditEndpoint({ ...ep })}
                                                >
                                                    수정
                                                </button>
                                                <button
                                                    className="btn btn-secondary"
                                                    style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                                                    onClick={() => handleDeleteEndpoint(ep.id)}
                                                >
                                                    삭제
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 'var(--spacing-4)' }}>
                        등록된 외부 PII API가 없습니다. 내장 Presidio 엔진을 사용 중입니다.
                    </div>
                )}

                <p style={{ marginTop: 'var(--spacing-3)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                    Docker로 실행된 PII 감지 서비스 (Presidio 등)를 등록하여 사용할 수 있습니다.
                </p>
            </div>

            {/* Edit Endpoint Modal */}
            {editEndpoint && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', display: 'flex',
                    alignItems: 'center', justifyContent: 'center', zIndex: 1000
                }}>
                    <div style={{
                        background: 'var(--color-bg-primary)', padding: 'var(--spacing-6)',
                        borderRadius: 'var(--radius-lg)', maxWidth: '500px', width: '100%'
                    }}>
                        <h3 style={{ marginBottom: 'var(--spacing-4)' }}>✏️ API 수정</h3>
                        <div className="form-group">
                            <label className="form-label">이름</label>
                            <input className="form-input" value={editEndpoint.name}
                                onChange={e => setEditEndpoint({ ...editEndpoint, name: e.target.value })} />
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">API URL</label>
                            <input className="form-input" value={editEndpoint.api_url}
                                onChange={e => setEditEndpoint({ ...editEndpoint, api_url: e.target.value })} />
                        </div>
                        <div className="form-group" style={{ marginTop: 'var(--spacing-3)' }}>
                            <label className="form-label">활성화</label>
                            <select className="form-input" value={editEndpoint.is_enabled ? 'true' : 'false'}
                                onChange={e => setEditEndpoint({ ...editEndpoint, is_enabled: e.target.value === 'true' })}>
                                <option value="true">활성화</option>
                                <option value="false">비활성화</option>
                            </select>
                        </div>
                        <div style={{ marginTop: 'var(--spacing-4)', display: 'flex', gap: 'var(--spacing-2)', justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => setEditEndpoint(null)}>취소</button>
                            <button className="btn btn-primary" onClick={handleUpdateEndpoint}>저장</button>
                        </div>
                    </div>
                </div>
            )}

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
                <Route path="/security-scan" element={<ProtectedRoute><SecurityScanPage /></ProtectedRoute>} />
                <Route path="/pending-registrations" element={<ProtectedRoute><PendingRegistrationsPage /></ProtectedRoute>} />
                <Route path="/org-select" element={<ProtectedRoute><OrganizationSelectPage /></ProtectedRoute>} />
                <Route path="/org-join-requests" element={<ProtectedRoute><OrgJoinRequestsPage /></ProtectedRoute>} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
        </AuthProvider>
    )
}
