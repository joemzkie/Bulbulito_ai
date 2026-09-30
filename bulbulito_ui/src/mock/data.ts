import type { Agent } from '../types'

export const generalAgent: Agent = { id: 'general', name: 'Bulbulito', role: 'General Assistant', status: 'online' }

export const promptIdeas = [
  { icon: 'database', title: 'Explain a PostgreSQL concept', detail: 'Indexes, joins, query plans...' },
  { icon: 'terminal', title: 'Debug Python code', detail: 'Trace an error together' },
  { icon: 'workflow', title: 'Design a data pipeline', detail: 'From source to dashboard' },
  { icon: 'search', title: 'Research a topic', detail: 'Get a clear starting point' },
]
