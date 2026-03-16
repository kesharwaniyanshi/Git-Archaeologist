import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

export type AuthUser = {
  github_id?: string
  login?: string
  email?: string | null
  name?: string | null
  avatar_url?: string | null
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

export function getGitHubLoginUrl() {
  return `${API_BASE_URL}/auth/github/login`
}

export async function getAuthMe(): Promise<AuthStatusResponse> {
  const response = await apiClient.get('/auth/me')
  return response.data
}

export async function logoutAuth() {
  const response = await apiClient.post('/auth/logout')
  return response.data
}
