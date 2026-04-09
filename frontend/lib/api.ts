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
