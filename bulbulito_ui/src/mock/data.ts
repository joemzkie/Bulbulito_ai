import type { Agent, Chat, Model, Provider } from '../types'

export const models: Model[] = [
  { id: 'gpt-oss', name: 'GPT-OSS 120B', provider: 'OpenAI compatible', note: 'General purpose' },
  { id: 'qwen-coder', name: 'Qwen3 Coder', provider: 'Local runtime', note: 'Code focused' },
  { id: 'nemotron', name: 'Nemotron', provider: 'NVIDIA', note: 'Reasoning' },
  { id: 'gemini', name: 'Gemini', provider: 'Google', note: 'Multimodal' },
  { id: 'cerebras', name: 'Cerebras', provider: 'Cerebras', note: 'Fast inference' },
]

export const providers: Provider[] = [
  { id: 'local', name: 'Local runtime', configured: true },
  { id: 'openai', name: 'OpenAI compatible', configured: false },
  { id: 'google', name: 'Google Gemini', configured: false },
  { id: 'cerebras', name: 'Cerebras', configured: false },
]

export const generalAgent: Agent = { id: 'general', name: 'Bulbulito', role: 'General Assistant', status: 'online' }

export const starterChats: Chat[] = [
  {
    id: 'postgres', title: 'PostgreSQL learning', group: 'Recent', updatedAt: '10:42 AM', messages: [
      { id: 'pg-u1', role: 'user', content: 'Explain PostgreSQL indexing.', createdAt: '10:41 AM' },
      { id: 'pg-a1', role: 'assistant', content: 'PostgreSQL indexes are data structures that help the database find rows without scanning an entire table. Think of an index like the entries at the back of a book: it trades a little storage and write overhead for much faster lookups.\n\nFor example, if you often find users by email, a B-tree index is a solid default:', createdAt: '10:42 AM' },
      { id: 'pg-a2', role: 'assistant', content: '```sql\nCREATE INDEX idx_users_email ON users (email);\n\n-- PostgreSQL can use the index for this lookup\nSELECT id, name FROM users WHERE email = \'ava@example.com\';\n```\n\nPostgreSQL creates **B-tree indexes by default**. They work well for equality checks, ranges, and sorting. You can inspect whether a query uses an index with `EXPLAIN ANALYZE`.\n\nA useful rule: index columns you filter, join, or order by often, but avoid adding indexes to every column. Each index takes space and makes inserts, updates, and deletes a little more expensive.', createdAt: '10:42 AM' },
    ],
  },
  { id: 'python-etl', title: 'Python ETL project', group: 'Recent', updatedAt: 'Yesterday', messages: [] },
  { id: 'data-notes', title: 'Data Engineering notes', group: 'Recent', updatedAt: 'Yesterday', messages: [] },
  { id: 'random', title: 'Random conversation', group: 'Recent', updatedAt: 'Sep 26', messages: [] },
  { id: 'build-agent', title: 'Build my AI agent', group: 'Today', updatedAt: '9:18 AM', messages: [] },
  { id: 'react-project', title: 'React project', group: 'Older', updatedAt: 'Sep 21', messages: [] },
  { id: 'crypto-pipeline', title: 'Crypto pipeline', group: 'Older', updatedAt: 'Sep 18', messages: [] },
]

export const promptIdeas = [
  { icon: 'database', title: 'Explain a PostgreSQL concept', detail: 'Indexes, joins, query plans...' },
  { icon: 'terminal', title: 'Debug Python code', detail: 'Trace an error together' },
  { icon: 'workflow', title: 'Design a data pipeline', detail: 'From source to dashboard' },
  { icon: 'search', title: 'Research a topic', detail: 'Get a clear starting point' },
]
