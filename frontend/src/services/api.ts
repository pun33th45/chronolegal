import axios, { AxiosError, type AxiosInstance } from 'axios'
import { useAuthStore } from '@/store/authStore'
import type {
  AdminStats,
  AnalyticsDashboard,
  ChatRequest,
  ChatResponse,
  Conversation,
  LegalCase,
  LegalEntities,
  SearchResponse,
  SummaryResponse,
  SummaryType,
  TimelineEvent,
  TokenResponse,
  User,
} from '@/types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle 401 → refresh or logout
api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const originalRequest = error.config as any
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const { refreshToken, logout, setTokens } = useAuthStore.getState()
      if (refreshToken) {
        try {
          const res = await axios.post(`${BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          const { access_token, refresh_token: new_refresh, user } = res.data as TokenResponse
          setTokens(access_token, new_refresh, user)
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        } catch {
          logout()
        }
      } else {
        logout()
      }
    }
    return Promise.reject(error)
  },
)

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: { email: string; username: string; password: string; full_name?: string }) =>
    api.post<User>('/auth/register', data).then((r) => r.data),

  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }).then((r) => r.data),

  refresh: (refresh_token: string) =>
    api.post<TokenResponse>('/auth/refresh', { refresh_token }).then((r) => r.data),

  me: () => api.get<User>('/auth/me').then((r) => r.data),

  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password', { current_password, new_password }),
}

// ─── Chat ─────────────────────────────────────────────────────────────────────
export const chatApi = {
  send: (data: ChatRequest) =>
    api.post<ChatResponse>('/chat/', data).then((r) => r.data),

  getConversations: (page = 1, page_size = 20) =>
    api.get<Conversation[]>('/chat/conversations', { params: { page, page_size } }).then((r) => r.data),

  getConversation: (id: string) =>
    api.get<Conversation>(`/chat/conversations/${id}`).then((r) => r.data),

  updateConversation: (id: string, data: { title?: string; is_archived?: boolean }) =>
    api.patch<Conversation>(`/chat/conversations/${id}`, data).then((r) => r.data),

  deleteConversation: (id: string) =>
    api.delete(`/chat/conversations/${id}`),

  streamUrl: () => `${BASE_URL}/chat/stream`,
}

// ─── Search ───────────────────────────────────────────────────────────────────
export const searchApi = {
  search: (data: {
    query: string
    top_k?: number
    search_type?: string
    filters?: Record<string, unknown>
  }) => api.post<SearchResponse>('/search/', data).then((r) => r.data),

  suggestions: (q: string, limit = 5) =>
    api.get<string[]>('/search/suggestions', { params: { q, limit } }).then((r) => r.data),

  filters: () => api.get('/search/filters').then((r) => r.data),
}

// ─── Cases ────────────────────────────────────────────────────────────────────
export const casesApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<LegalCase[]>('/cases/', { params }).then((r) => r.data),

  get: (caseId: string) =>
    api.get<LegalCase>(`/cases/${caseId}`).then((r) => r.data),

  getSimilar: (caseId: string, top_k = 5) =>
    api.get<LegalCase[]>(`/cases/${caseId}/similar`, { params: { top_k } }).then((r) => r.data),
}

// ─── Summary ──────────────────────────────────────────────────────────────────
export const summaryApi = {
  generate: (case_id: string, summary_type: SummaryType, max_length = 500) =>
    api.post<SummaryResponse>('/summary/', { case_id, summary_type, max_length }).then((r) => r.data),
}

// ─── NER ──────────────────────────────────────────────────────────────────────
export const nerApi = {
  extract: (case_id?: string, text?: string) =>
    api.post<LegalEntities>('/ner/', { case_id, text }).then((r) => r.data),
}

// ─── Timeline ─────────────────────────────────────────────────────────────────
export const timelineApi = {
  get: (caseId: string) =>
    api.get<TimelineEvent[]>(`/timeline/${caseId}`).then((r) => r.data),
}

// ─── Analytics ────────────────────────────────────────────────────────────────
export const analyticsApi = {
  dashboard: () =>
    api.get<AnalyticsDashboard>('/analytics/dashboard').then((r) => r.data),

  topActs: (limit = 20) =>
    api.get('/analytics/top-acts', { params: { limit } }).then((r) => r.data),

  topCourts: (limit = 20) =>
    api.get('/analytics/top-courts', { params: { limit } }).then((r) => r.data),

  caseTrends: (years = 20) =>
    api.get('/analytics/case-trends', { params: { years } }).then((r) => r.data),
}

// ─── Admin ────────────────────────────────────────────────────────────────────
export const adminApi = {
  stats: () =>
    api.get<AdminStats>('/admin/stats').then((r) => r.data),

  users: (page = 1, page_size = 50) =>
    api.get('/admin/users', { params: { page, page_size } }).then((r) => r.data),

  reindex: () =>
    api.post('/admin/reindex').then((r) => r.data),

  searchLogs: (page = 1, page_size = 50) =>
    api.get('/admin/search-logs', { params: { page, page_size } }).then((r) => r.data),
}

// ─── Feedback ─────────────────────────────────────────────────────────────────
export const feedbackApi = {
  submit: (data: {
    query: string
    message_id?: string
    rating?: number
    is_helpful?: boolean
    comment?: string
  }) => api.post('/feedback/', data),
}

export default api
