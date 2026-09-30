import type { AgentId, Chat, Message, ModelInfo } from '../types'

const API_BASE = 'http://localhost:8000/api'

interface ApiMessage {
  role: Message['role']
  content: string
  created_at?: string | null
}

interface ApiChat {
  id: string
  title: string
  model: string
  agent?: AgentId
  created_at: string
  updated_at: string
  messages?: ApiMessage[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new Error('Cannot reach the Bulbulito backend. Make sure FastAPI is running on port 8000.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}

function toChat(data: ApiChat): Chat {
  const updated = new Date(data.updated_at)
  const today = new Date()
  const group: Chat['group'] = updated.toDateString() === today.toDateString()
    ? 'Today'
    : updated.getFullYear() === today.getFullYear() ? 'Recent' : 'Older'
  return {
    ...data,
    agent: data.agent ?? 'jiniral',
    group,
    updatedAt: updated.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
    messages: (data.messages ?? []).map((message, index) => ({
      id: `${data.id}-${index}`,
      role: message.role,
      content: message.content,
      createdAt: message.created_at
        ? new Date(message.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
        : '',
    })),
  }
}

export async function getModels(): Promise<ModelInfo[]> {
  const registry = await request<Record<string, Omit<ModelInfo, 'id'>>>('/models')
  return Object.entries(registry).map(([id, model]) => ({ id, ...model }))
}

export async function getChats(): Promise<Chat[]> {
  return (await request<ApiChat[]>('/chats')).map(toChat)
}

export async function getChat(chatId: string): Promise<Chat> {
  return toChat(await request<ApiChat>(`/chats/${encodeURIComponent(chatId)}`))
}

export async function createChat(model?: string, agent: AgentId = 'jiniral'): Promise<Chat> {
  return toChat(await request<ApiChat>('/chats', {
    method: 'POST',
    body: JSON.stringify({ model, agent }),
  }))
}

export interface SendMessageInput {
  model: string
  agent: AgentId
  content: string
  research_depth?: 'quick' | 'standard' | 'deep'
  research_constraints?: string
}

export async function sendMessage(chatId: string, input: SendMessageInput, onProgress?: (status: string) => void): Promise<Chat> {
  const response = await fetch(`${API_BASE}/chats/${encodeURIComponent(chatId)}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }).catch(() => { throw new Error('Cannot reach the Bulbulito backend. Make sure FastAPI is running on port 8000.') })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed (${response.status}).`)
  }
  if (response.headers.get('content-type')?.includes('text/event-stream')) {
    if (!response.body) throw new Error('The research stream could not be opened.')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let completed: ApiChat | undefined
    const handleFrame = (frame: string) => {
      let event = 'message'
      let data = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) return
      const parsed = JSON.parse(data) as { status?: string; detail?: string; conversation?: ApiChat }
      if (event === 'progress' && parsed.status) onProgress?.(parsed.status)
      else if (event === 'error') throw new Error(parsed.detail ?? 'RIZARTS could not complete this research request.')
      else if (event === 'complete' && parsed.conversation) completed = parsed.conversation
    }
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''
      frames.forEach(handleFrame)
      if (done) break
    }
    if (!completed) throw new Error('RIZARTS ended without a completed research response.')
    return toChat(completed)
  }
  const result = await response.json() as { conversation: ApiChat }
  return toChat(result.conversation)
}

async function updateChat(chatId: string, patch: { title?: string; agent?: AgentId }): Promise<Chat> {
  return toChat(await request<ApiChat>(`/chats/${encodeURIComponent(chatId)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }))
}

export async function renameChat(chatId: string, title: string): Promise<Chat> {
  return updateChat(chatId, { title })
}

export async function setChatAgent(chatId: string, agent: AgentId): Promise<Chat> {
  return updateChat(chatId, { agent })
}

export async function deleteChat(chatId: string): Promise<void> {
  await request(`/chats/${encodeURIComponent(chatId)}`, { method: 'DELETE' })
}
