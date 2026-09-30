import type { Chat, Message, ModelInfo } from '../types'

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

export async function createChat(model?: string): Promise<Chat> {
  return toChat(await request<ApiChat>('/chats', {
    method: 'POST',
    body: JSON.stringify(model ? { model } : {}),
  }))
}

export async function sendMessage(chatId: string, model: string, content: string): Promise<Chat> {
  const result = await request<{ conversation: ApiChat }>(`/chats/${encodeURIComponent(chatId)}/messages`, {
    method: 'POST',
    body: JSON.stringify({ model, content }),
  })
  return toChat(result.conversation)
}

export async function deleteChat(chatId: string): Promise<void> {
  await request(`/chats/${encodeURIComponent(chatId)}`, { method: 'DELETE' })
}
