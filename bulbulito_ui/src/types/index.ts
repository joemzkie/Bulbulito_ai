export type MessageRole = 'system' | 'user' | 'assistant'
export type AgentId = 'jiniral' | 'bai-coding' | 'rizarts'

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
  agent: AgentId
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
