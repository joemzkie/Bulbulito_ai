export type MessageRole = 'system' | 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  createdAt: string
  liked?: boolean | null
}

export interface Chat {
  id: string
  title: string
  group: 'Today' | 'Recent' | 'Older'
  updatedAt: string
  model: string
  created_at: string
  updated_at: string
  messages: Message[]
}

export interface ModelInfo {
  id: string
  name: string
  provider: string
  description: string
}

export interface Agent {
  id: string
  name: string
  role: string
  status: 'online' | 'offline'
}
