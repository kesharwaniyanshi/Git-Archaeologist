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

export interface LinkRepoRequest {
  url: string
}

export interface RepositoryResponse {
  id: string
  url: string
  owner: string
  name: string
  last_indexed_commit?: string
  created_at: string
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

export async function linkRepository(data: LinkRepoRequest): Promise<RepositoryResponse> {
  const response = await apiClient.post('/repos/link', data)
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

// ── Chat Session Types ──
export interface ChatMessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatSessionItem {
  chat_session_id: string
  title: string | null
  created_at: string | null
  updated_at: string | null
  message_count: number
}

export interface SendMessageResponse {
  user_message: ChatMessageItem
  assistant_message: ChatMessageItem
}

// ── Chat Session API ──
export async function createChatSession(repositoryId?: string) {
  const response = await apiClient.post('/chat/sessions', { repository_id: repositoryId || null })
  return response.data as { chat_session_id: string; title: string | null }
}

export async function listChatSessions(limit = 50) {
  const response = await apiClient.get('/chat/sessions', { params: { limit } })
  return response.data as { sessions: ChatSessionItem[] }
}

export async function getChatHistory(sessionId: string) {
  const response = await apiClient.get(`/chat/sessions/${sessionId}`)
  return response.data as { chat_session_id: string; title: string | null; messages: ChatMessageItem[] }
}

export async function sendMessage(sessionId: string, content: string): Promise<SendMessageResponse> {
  const response = await apiClient.post(`/chat/sessions/${sessionId}/messages`, { content })
  return response.data
}
