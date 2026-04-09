import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

if (typeof window !== 'undefined') {
  apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('gitarch_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
}

export type AuthUser = {
  id?: string
  github_id?: string
  google_id?: string
  email?: string | null
}

export type AuthStatusResponse = {
  authenticated: boolean
  user: AuthUser | null
}

export interface AnalyzeRequest {
  repo_path: string
  query: string
  chat_session_id?: string
  top_k?: number
  max_commits?: number
  use_embeddings?: boolean
}

export interface AnalyzeResponse {
  query: string
  answer: string
  chat_session_id?: string
  evidence_count: number
  evidence?: any[]
}

export interface IndexRequest {
  repo_path: string
  max_commits?: number
  use_embeddings?: boolean
}

export interface ChatSessionListItem {
  chat_session_id: string
  created_at?: string | null
  updated_at?: string | null
  last_user_query: string
  message_count: number
}

export async function healthCheck() {
  const response = await apiClient.get('/health')
  return response.data
}

export async function getStatus(repoPath: string) {
  const response = await apiClient.get('/status', {
    params: { repo_path: repoPath },
  })
  return response.data
}

export async function indexRepository(data: IndexRequest) {
  const response = await apiClient.post('/index', data)
  return response.data
}

export async function analyzeQuery(data: AnalyzeRequest): Promise<AnalyzeResponse> {
  const response = await apiClient.post('/analyze', data)
  return response.data
}

export async function getChatHistory(chatSessionId: string) {
  const response = await apiClient.get(`/chat/${chatSessionId}`)
  return response.data
}

export async function listChatSessions(repoPath?: string, limit: number = 50) {
  const response = await apiClient.get('/chat', {
    params: {
      repo_path: repoPath,
      limit,
    },
  })
  return response.data
}

export async function createChatSession(repoPath?: string) {
  const response = await apiClient.post('/chat/session', {
    repo_path: repoPath,
  })
  return response.data
}

export function getGitHubLoginUrl() {
  return `${API_BASE_URL}/auth/github/login`
}

export const authApi = {
  login: async (email: string, password: string) => {
    const response = await apiClient.post('/auth/login', { email, password })
    return response.data
  },
  register: async (email: string, password: string) => {
    const response = await apiClient.post('/auth/register', { email, password })
    return response.data
  },
  getMe: async (): Promise<AuthStatusResponse> => {
    const response = await apiClient.get('/auth/me')
    return response.data
  },
  logout: async () => {
    const response = await apiClient.post('/auth/logout')
    return response.data
  }
}
