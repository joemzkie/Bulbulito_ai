export type MessageRole = 'user' | 'assistant'

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
  messages: Message[]
}

export interface Model {
  id: string
  name: string
  provider: string
  note: string
}

export interface Provider {
  id: string
  name: string
  configured: boolean
}

export interface Agent {
  id: string
  name: string
  role: string
  status: 'online' | 'offline'
}
