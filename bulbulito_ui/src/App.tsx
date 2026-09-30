import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import {
  ArrowDown, ArrowLeft, ArrowUp, Bot, Check, ChevronDown, ChevronRight,
  Code2, Copy, Database, Ellipsis, FileUp, FolderOpen, Globe2, Menu, MessageSquarePlus,
  PanelLeftClose, PanelLeftOpen, Paperclip, Plus, Search, Settings,
  ShieldCheck, Sparkles, Terminal, ThumbsDown, ThumbsUp, Workflow, X,
} from 'lucide-react'
import { generalAgent, promptIdeas } from './mock/data'
import type { Agent, Chat, Message, ModelInfo } from './types'
import * as api from './services/api'
import bulbulitoLogo from './assets/BAI.png'
import './App.css'

function BulbulitoMark({ size = 'normal' }: { size?: 'small' | 'normal' | 'large' }) {
  return <div className={`bulbulito-mark mark-${size}`} aria-label="Bulbulito icon placeholder">
    <img src={bulbulitoLogo} alt="" />
    <span className="mark-fallback"><Sparkles size={size === 'large' ? 23 : 16} strokeWidth={1.6} /></span>
  </div>
}

function AssistantAvatar() {
  return <BulbulitoMark size="small" />
}

function AgentIdentity({ agent }: { agent: Agent }) {
  return <div className="agent-identity"><BulbulitoMark size="small" /><span className="agent-copy"><strong>{agent.name}</strong><span>{agent.role}</span></span><span className="online-dot" title="Online" /></div>
}

function Sidebar({ chats, activeId, collapsed, onToggle, onNew, onSelect, onRename, onDelete, onSettings }: {
  chats: Chat[]; activeId: string | null; collapsed: boolean; onToggle: () => void; onNew: () => void
  onSelect: (id: string) => void; onRename: (id: string, title: string) => Promise<void>
  onDelete: (id: string) => Promise<void>; onSettings: () => void
}) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)
  const [savingRename, setSavingRename] = useState(false)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const renameInputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (!openMenuId) return
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpenMenuId(null)
    }
    document.addEventListener('pointerdown', closeOnOutsideClick)
    return () => document.removeEventListener('pointerdown', closeOnOutsideClick)
  }, [openMenuId])
  useEffect(() => {
    if (editingId) renameInputRef.current?.focus()
  }, [editingId])
  useEffect(() => {
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (pendingDeleteId) setPendingDeleteId(null)
      else if (editingId) {
        setEditingId(null)
        setRenameError(null)
      }
      setOpenMenuId(null)
    }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [editingId, pendingDeleteId])

  const beginRename = (chat: Chat) => {
    setOpenMenuId(null)
    setRenameError(null)
    setDraftTitle(chat.title)
    setEditingId(chat.id)
  }
  const saveRename = async (event: FormEvent, chatId: string) => {
    event.preventDefault()
    const title = draftTitle.trim()
    if (!title) {
      setRenameError('A conversation title is required.')
      return
    }
    setSavingRename(true)
    setRenameError(null)
    try {
      await onRename(chatId, title)
      setEditingId(null)
    } catch (cause) {
      setRenameError(cause instanceof Error ? cause.message : 'Could not rename conversation.')
    } finally {
      setSavingRename(false)
    }
  }
  const confirmDelete = async () => {
    if (!pendingDeleteId) return
    const chatId = pendingDeleteId
    try {
      await onDelete(chatId)
      setPendingDeleteId(null)
    } catch {
      // The app-level error banner reports a failed delete; keep confirmation open.
    }
  }

  const groups: Chat['group'][] = ['Today', 'Recent', 'Older']
  const groupIcons = { Today: 'TODAY', Recent: 'RECENT', Older: 'OLDER' }
  return <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <div className="brand-row"><BulbulitoMark /><span className="brand-name">bulbulito<span>ai</span></span><button className="icon-button collapse-button" onClick={onToggle} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button></div>
    <button className="new-chat-button" onClick={onNew} title="New chat"><Plus size={16} /><span>New chat</span><kbd>⌘ K</kbd></button>
    <div className="history-scroll">
      {groups.map((group) => {
        const items = chats.filter((chat) => chat.group === group)
        if (!items.length) return null
        return <section className="history-group" key={group}><div className="section-label">{groupIcons[group]}</div>{items.map((chat) => <div className={`history-item ${activeId === chat.id ? 'active' : ''}`} key={chat.id}>
          {editingId === chat.id ? <form className="history-rename-form" onSubmit={(event) => void saveRename(event, chat.id)}>
            <input ref={renameInputRef} className="history-rename-input" value={draftTitle} maxLength={120} aria-label="Conversation title" onChange={(event) => { setDraftTitle(event.target.value); setRenameError(null) }} onKeyDown={(event) => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setEditingId(null); setRenameError(null) } }} />
            <div className="history-rename-actions"><button type="submit" disabled={savingRename || !draftTitle.trim()}>Save</button><button type="button" disabled={savingRename} onClick={() => { setEditingId(null); setRenameError(null) }}>Cancel</button></div>
            {renameError && <span className="history-rename-error" role="alert">{renameError}</span>}
          </form> : <button className="history-select" onClick={() => onSelect(chat.id)} title={chat.title}><MessageIcon active={activeId === chat.id} /><span>{chat.title}</span></button>}
          <button className="history-more" aria-label={`Actions for ${chat.title}`} aria-haspopup="menu" aria-expanded={openMenuId === chat.id} onClick={(event) => { event.stopPropagation(); setOpenMenuId((current) => current === chat.id ? null : chat.id) }} title="Conversation actions"><Ellipsis size={16} /></button>
          {openMenuId === chat.id && <div ref={menuRef} className="chat-context-menu" role="menu" aria-label={`Actions for ${chat.title}`}>
            <button role="menuitem" onClick={(event) => { event.stopPropagation(); beginRename(chat) }}>Rename</button>
            <button role="menuitem" className="chat-context-delete" onClick={(event) => { event.stopPropagation(); setOpenMenuId(null); setPendingDeleteId(chat.id) }}>Delete</button>
          </div>}
        </div>)}</section>
      })}
      <div className="tools-preview"><div className="section-label">WORKSPACE</div><div className="future-tool"><FolderOpen size={15} /><span>Local files</span><span className="soon-tag">SOON</span></div><div className="future-tool"><Globe2 size={15} /><span>Web research</span><span className="soon-tag">SOON</span></div></div>
    </div>
    <div className="sidebar-bottom"><AgentIdentity agent={generalAgent} /><button className="sidebar-setting" onClick={onSettings}><Settings size={16} /><span>Settings & providers</span><ChevronRight size={14} className="setting-chevron" /></button><div className="storage-status"><span className="storage-led" /><span>Local storage</span><span className="storage-label">READY</span></div></div>
    {pendingDeleteId && <DeleteConversationDialog chat={chats.find((chat) => chat.id === pendingDeleteId) ?? null} onCancel={() => setPendingDeleteId(null)} onConfirm={() => void confirmDelete()} />}
  </aside>
}

function DeleteConversationDialog({ chat, onCancel, onConfirm }: { chat: Chat | null; onCancel: () => void; onConfirm: () => void }) {
  if (!chat) return null
  return <div className="modal-backdrop delete-confirm-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel() }}><section className="delete-confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-chat-title" aria-describedby="delete-chat-description"><h2 id="delete-chat-title">Delete conversation?</h2><p id="delete-chat-description">This action cannot be undone.</p><div className="delete-confirm-actions"><button type="button" onClick={onCancel}>Cancel</button><button type="button" className="confirm-delete-button" onClick={onConfirm}>Delete</button></div></section></div>
}

function MessageIcon({ active }: { active: boolean }) { return <MessageSquarePlus size={15} className={active ? 'history-icon selected' : 'history-icon'} /> }

function ModelPicker({ current, models, onChange }: { current: string; models: ModelInfo[]; onChange: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const model = models.find((item) => item.id === current) ?? models[0]
  const filtered = models.filter((item) => item.name.toLowerCase().includes(query.toLowerCase()))
  return <div className="model-picker-wrap"><button className={`model-picker ${open ? 'model-open' : ''}`} onClick={() => setOpen((value) => !value)} disabled={!model}><span className="model-spark"><Sparkles size={13} /></span><span>{model?.name ?? 'Loading models…'}</span><ChevronDown size={14} /></button>
    {open && <><button className="click-away" aria-label="Close model menu" onClick={() => setOpen(false)} /><div className="model-menu"><div className="model-menu-heading">CHOOSE A MODEL <span>LOCAL + CLOUD</span></div><label className="model-search"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a model" autoFocus /></label>{filtered.map((item) => <button key={item.id} className={`model-option ${current === item.id ? 'chosen' : ''}`} onClick={() => { onChange(item.id); setOpen(false); setQuery('') }}><span className="model-option-icon"><Sparkles size={14} /></span><span className="model-option-copy"><strong>{item.name}</strong><small>{item.description}</small></span><span className="model-provider">{item.provider}</span>{current === item.id && <Check size={15} />}</button>)}<div className="model-menu-footer">Provider credentials are managed by the local backend</div></div></>}
  </div>
}

function Header({ title, modelId, models, onModel, onSettings, onSidebar }: { title: string; modelId: string; models: ModelInfo[]; onModel: (id: string) => void; onSettings: () => void; onSidebar: () => void }) {
  return <header className="topbar"><div className="topbar-title"><button className="icon-button mobile-menu" onClick={onSidebar} aria-label="Toggle sidebar"><Menu size={18} /></button><div className="breadcrumbs"><span className="breadcrumb-muted">Workspace</span><ChevronRight size={13} /><strong>{title}</strong></div></div><div className="topbar-actions"><div className="local-indicator"><span />Local workspace</div><ModelPicker current={modelId} models={models} onChange={onModel} /><button className="icon-button header-settings" aria-label="Settings" onClick={onSettings}><Settings size={17} /></button></div></header>
}

function Composer({ onSend, placeholder = 'Ask Bulbulito anything...', compact = false, disabled = false }: { onSend: (text: string) => void; placeholder?: string; compact?: boolean; disabled?: boolean }) {
  const [value, setValue] = useState('')
  const [toolsOpen, setToolsOpen] = useState(false)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const send = () => { const text = value.trim(); if (!text) return; onSend(text); setValue(''); if (textarea.current) textarea.current.style.height = 'auto' }
  const submit = (event: FormEvent) => { event.preventDefault(); send() }
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send() } }
  const resize = () => { if (textarea.current) { textarea.current.style.height = 'auto'; textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, 180)}px` } }
  return <div className={`composer-shell ${compact ? 'composer-compact' : ''}`}><form className="composer" onSubmit={submit}><textarea ref={textarea} value={value} onChange={(event) => { setValue(event.target.value); resize() }} onKeyDown={keyDown} placeholder={placeholder} rows={1} aria-label="Message Bulbulito" />
    <div className="composer-toolbar"><div className="composer-left"><button type="button" className="composer-tool" title="Attach a file"><Paperclip size={16} /></button><div className="tools-wrap"><button type="button" className={`composer-tool tools-button ${toolsOpen ? 'tool-active' : ''}`} onClick={() => setToolsOpen((value) => !value)}><Plus size={16} /><span>Tools</span></button>{toolsOpen && <><button className="click-away" onClick={() => setToolsOpen(false)} aria-label="Close tools" /><div className="tools-menu"><div className="tools-menu-title">ADD A TOOL <span>COMING SOON</span></div><div><Globe2 size={15} />Web search</div><div><FileUp size={15} />Analyze files</div><div><Terminal size={15} />Run Python</div></div></>}</div><span className="composer-context">Local workspace</span></div><div className="composer-right"><span className="key-hint"><kbd>↵</kbd> to send</span><button type="submit" className="send-button" disabled={!value.trim() || disabled} aria-label="Send message"><ArrowUp size={18} /></button></div></div>
  </form><div className="composer-disclaimer">Bulbulito can make mistakes. Check important information.</div></div>
}

function MessageBody({ content }: { content: string }) {
  const lines = content.split('\n')
  const blocks: ReactNode[] = []
  let paragraph: string[] = []
  let codeLines: string[] = []
  let inCode = false
  const inline = (text: string) => text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => part.startsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> : part.startsWith('`') ? <code key={index}>{part.slice(1, -1)}</code> : part)
  const flushParagraph = () => { if (paragraph.length) { blocks.push(<p key={`p-${blocks.length}`}>{paragraph.map((line, index) => <span key={index}>{index > 0 && <br />}{inline(line)}</span>)}</p>); paragraph = [] } }
  lines.forEach((line) => {
    if (line.startsWith('```')) { if (inCode) { blocks.push(<CodeBlock key={`c-${blocks.length}`} code={codeLines.join('\n')} />); codeLines = []; inCode = false } else { flushParagraph(); inCode = true } }
    else if (inCode) codeLines.push(line)
    else if (!line.trim()) flushParagraph()
    else if (line.startsWith('- ')) { flushParagraph(); blocks.push(<div key={`li-${blocks.length}`} className="answer-list">· <span>{inline(line.slice(2))}</span></div>) }
    else paragraph.push(line)
  })
  if (inCode) blocks.push(<CodeBlock key={`c-${blocks.length}`} code={codeLines.join('\n')} />)
  flushParagraph()
  return <div className="message-content">{blocks}</div>
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => { await navigator.clipboard?.writeText(code); setCopied(true); window.setTimeout(() => setCopied(false), 1600) }
  return <div className="code-block"><div className="code-head"><div><span className="code-led" /><span className="code-led" /><span className="code-led" /><span className="code-lang">SQL</span></div><button onClick={copy}>{copied ? <Check size={13} /> : <Copy size={13} />}{copied ? 'Copied' : 'Copy'}</button></div><pre><code>{code.split('\n').map((line, index) => <span key={index} className="code-line"><span className="line-number">{index + 1}</span><span>{line.split(/(\b(?:CREATE|INDEX|ON|SELECT|FROM|WHERE)\b|'[^']*'|--.*)/g).map((part, token) => part.startsWith('--') ? <span key={token} className="syntax-comment">{part}</span> : part.startsWith("'") ? <span key={token} className="syntax-string">{part}</span> : /^(CREATE|INDEX|ON|SELECT|FROM|WHERE)$/.test(part) ? <span key={token} className="syntax-keyword">{part}</span> : part)}</span></span>)}</code></pre></div>
}

function MessageItem({ message, onRate }: { message: Message; onRate: (id: string, rating: boolean | null) => void }) {
  const [copied, setCopied] = useState(false)
  const isAssistant = message.role === 'assistant'
  const copy = async () => { await navigator.clipboard?.writeText(message.content); setCopied(true); window.setTimeout(() => setCopied(false), 1500) }
  return <article className={`message-row ${isAssistant ? 'assistant-row' : 'user-row'}`}>{isAssistant ? <AssistantAvatar /> : <div className="user-avatar">J</div>}<div className="message-main"><div className="message-label"><strong>{isAssistant ? 'Bulbulito' : 'You'}</strong><time>{message.createdAt}</time></div><MessageBody content={message.content} />{isAssistant && <div className="message-actions"><button onClick={copy} title="Copy response">{copied ? <Check size={14} /> : <Copy size={14} />}<span>{copied ? 'Copied' : 'Copy'}</span></button><button title="Regenerate response"><ArrowDown size={14} /><span>Regenerate</span></button><span className="action-divider" /><button className={message.liked === true ? 'rated' : ''} aria-label="Helpful" onClick={() => onRate(message.id, message.liked === true ? null : true)}><ThumbsUp size={14} /></button><button className={message.liked === false ? 'rated' : ''} aria-label="Not helpful" onClick={() => onRate(message.id, message.liked === false ? null : false)}><ThumbsDown size={14} /></button></div>}</div></article>
}

function Conversation({ chat, onRate, onSend, sending }: { chat: Chat; onRate: (id: string, rating: boolean | null) => void; onSend: (text: string) => void; sending: boolean }) {
  const messagesEnd = useRef<HTMLDivElement>(null)
  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [chat.messages.length])
  return <><div className="conversation-scroll"><div className="conversation-inner">{chat.messages.length ? chat.messages.map((message) => <MessageItem key={message.id} message={message} onRate={onRate} />) : <div className="empty-chat"><BulbulitoMark size="large" /><h2>Ready when you are.</h2><p>Your conversation starts with a question, a problem, or a curious thought.</p></div>}{sending && <div className="message-row assistant-row"><AssistantAvatar /><div className="message-main"><div className="message-label"><strong>Bulbulito</strong></div><p className="message-content">Thinking…</p></div></div>}<div ref={messagesEnd} /></div></div><Composer onSend={onSend} disabled={sending} /></>
}

function Landing({ onPrompt }: { onPrompt: (text: string) => void }) {
  const icons = { database: Database, terminal: Code2, workflow: Workflow, search: Search }
  return <div className="landing-area"><div className="landing-content"><div className="landing-mark-wrap"><BulbulitoMark size="large" /><span className="orbit orbit-one" /><span className="orbit orbit-two" /></div><div className="landing-eyebrow"><span className="eyebrow-line" />YOUR LOCAL AI WORKSPACE<span className="eyebrow-line" /></div><h1>What are we<br /><em>building today?</em></h1><p className="landing-subtitle">A quiet place to think through code, data, research,<br className="desktop-break" /> and everything in between.</p><div className="landing-composer"><Composer onSend={onPrompt} compact /></div><div className="ideas-label"><span>NEED A STARTING POINT?</span><span className="ideas-line" /></div><div className="prompt-grid">{promptIdeas.map((idea) => { const Icon = icons[idea.icon as keyof typeof icons]; return <button key={idea.title} className="prompt-card" onClick={() => onPrompt(idea.title)}><span className="prompt-icon"><Icon size={16} /></span><span className="prompt-copy"><strong>{idea.title}</strong><small>{idea.detail}</small></span><ArrowUp size={14} className="prompt-arrow" /></button> })}</div><div className="future-chips"><span><ShieldCheck size={13} /> Private by default</span><i /><span><Bot size={13} /> Your models, your way</span><i /><span><Workflow size={13} /> Tools on the horizon</span></div></div></div>
}

function SettingsModal({ onClose }: { onClose: () => void }) {
  const [section, setSection] = useState('General')
  const sections = ['General', 'LLM Provider', 'Context & Memory', 'System Prompt', 'Agent Settings']
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title"><header className="settings-header"><div><span className="settings-kicker">PREFERENCES</span><h2 id="settings-title">Workspace settings</h2></div><button className="icon-button" onClick={onClose} aria-label="Close settings"><X size={18} /></button></header><div className="settings-body"><nav className="settings-nav">{sections.map((item) => <button key={item} className={section === item ? 'selected' : ''} onClick={() => setSection(item)}>{item}</button>)}</nav><div className="settings-panel">{section === 'General' && <><h3>Appearance</h3><p className="settings-description">Make the workspace feel like yours.</p><label className="settings-row"><span><strong>Theme</strong><small>Color palette for your workspace</small></span><select defaultValue="dark"><option value="dark">Midnight</option><option value="system">System</option></select></label><label className="settings-row"><span><strong>Accent</strong><small>A subtle highlight color</small></span><span className="accent-choice"><i /><i /><i className="selected" /><i /></span></label><div className="settings-divider" /><h3>Local credentials</h3><p className="settings-description">Provider credentials are read only by the local backend from the project root .env file. They are never stored in this browser.</p></>}{section === 'LLM Provider' && <><h3>LLM Provider</h3><p className="settings-description">Choose a model from the selector in the top bar. Configure provider credentials in the project root .env file, then restart the backend.</p></>}{section === 'Context & Memory' && <><h3>Context & Memory</h3><p className="settings-description">Conversation messages are saved locally by the backend.</p><div className="note-card"><ShieldCheck size={16} /><span>Chat history is stored as JSON on this device.</span></div></>}{section === 'System Prompt' && <><h3>System Prompt</h3><p className="settings-description">The backend applies Bulbulito's default system instruction to each chat.</p></>}{section === 'Agent Settings' && <><h3>Agent Settings</h3><p className="settings-description">Your agent lineup is taking shape.</p><div className="agent-preview-card"><AgentIdentity agent={generalAgent} /><span className="agent-current-badge">CURRENT</span></div><div className="future-agent-row"><span className="future-agent-icon"><Code2 size={17} /></span><span><strong>Bulbulito Code</strong><small>Coding agent · coming later</small></span><span className="soon-tag">SOON</span></div><div className="future-agent-row"><span className="future-agent-icon"><Search size={17} /></span><span><strong>Bulbulito Research</strong><small>Research agent · coming later</small></span><span className="soon-tag">SOON</span></div></>}</div></div><footer className="settings-footer"><span>Changes are saved in this session</span><button onClick={onClose}>Done</button></footer></section></div>
}

function App() {
  const [chats, setChats] = useState<Chat[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [modelId, setModelId] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const activeChat = chats.find((chat) => chat.id === activeId) ?? null
  const title = activeChat?.title ?? 'New conversation'
  const refreshChats = async () => {
    try { setChats(await api.getChats()) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load conversations.') }
  }
  const createChat = async (initialText?: string) => {
    setError(null)
    try {
      const chat = await api.createChat(modelId || undefined)
      setChats((current) => [chat, ...current.filter((item) => item.id !== chat.id)])
      setActiveId(chat.id)
      if (initialText) await sendMessage(initialText, chat.id, modelId || chat.model)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create conversation.') }
  }
  const selectChat = async (id: string) => {
    setActiveId(id)
    setError(null)
    try {
      const chat = await api.getChat(id)
      setChats((current) => current.map((item) => item.id === id ? chat : item))
      setModelId(chat.model)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load conversation.') }
  }
  const sendMessage = async (text: string, targetId = activeId, selectedModel = modelId) => {
    if (!targetId) { await createChat(text); return }
    if (!selectedModel || sending) return
    setError(null)
    const userMessage: Message = { id: `pending-${Date.now()}`, role: 'user', content: text, createdAt: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) }
    setChats((current) => current.map((chat) => chat.id === targetId ? { ...chat, messages: [...chat.messages, userMessage] } : chat))
    setSending(true)
    try {
      const updated = await api.sendMessage(targetId, selectedModel, text)
      setChats((current) => current.map((chat) => chat.id === targetId ? updated : chat))
      setModelId(updated.model)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not send your message.')
      setChats((current) => current.map((chat) => chat.id === targetId ? { ...chat, messages: chat.messages.filter((message) => message.id !== userMessage.id) } : chat))
    } finally { setSending(false) }
  }
  const rateMessage = (messageId: string, rating: boolean | null) => setChats((current) => current.map((chat) => ({ ...chat, messages: chat.messages.map((message) => message.id === messageId ? { ...message, liked: rating } : message) })))
  const renameChat = async (id: string, title: string) => {
    const updated = await api.renameChat(id, title)
    setChats((current) => current.map((chat) => chat.id === id ? updated : chat))
  }
  const deleteChat = async (id: string) => {
    setError(null)
    try {
      await api.deleteChat(id)
      setChats((current) => current.filter((chat) => chat.id !== id))
      if (activeId === id) setActiveId(null)
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not delete conversation.'
      setError(message)
      throw cause instanceof Error ? cause : new Error(message)
    }
  }
  useEffect(() => {
    void api.getModels().then((available) => {
      setModels(available)
      setModelId((current) => current || available[0]?.id || '')
    }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load models.'))
    void refreshChats()
  }, [])
  useEffect(() => {
    const hotkey = (event: globalThis.KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setSearchOpen(true) } if (event.key === 'Escape') { setSearchOpen(false); setSettingsOpen(false) } }
    window.addEventListener('keydown', hotkey); return () => window.removeEventListener('keydown', hotkey)
  }, [])
  return <div className="app-shell"><Sidebar chats={chats} activeId={activeId} collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} onNew={() => void createChat()} onSelect={(id) => void selectChat(id)} onRename={renameChat} onDelete={deleteChat} onSettings={() => setSettingsOpen(true)} /><main className="workspace"><Header title={title} modelId={modelId} models={models} onModel={setModelId} onSettings={() => setSettingsOpen(true)} onSidebar={() => setCollapsed((value) => !value)} />{error && <div role="alert" className="backend-error">{error}<button onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}{activeChat ? <Conversation chat={activeChat} onRate={rateMessage} onSend={(text) => void sendMessage(text)} sending={sending} /> : <Landing onPrompt={(text) => void createChat(text)} />}</main>{settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}{searchOpen && <SearchDialog chats={chats} onClose={() => setSearchOpen(false)} onSelect={(id) => { void selectChat(id); setSearchOpen(false) }} />}</div>
}

function SearchDialog({ chats, onClose, onSelect }: { chats: Chat[]; onClose: () => void; onSelect: (id: string) => void }) {
  const [query, setQuery] = useState('')
  const filtered = chats.filter((chat) => chat.title.toLowerCase().includes(query.toLowerCase()))
  return <div className="modal-backdrop search-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="search-dialog"><label className="search-dialog-input"><Search size={18} /><input autoFocus placeholder="Search conversations..." value={query} onChange={(event) => setQuery(event.target.value)} /><kbd>ESC</kbd></label><div className="search-results"><div className="section-label">CONVERSATIONS</div>{filtered.length ? filtered.map((chat) => <button key={chat.id} onClick={() => onSelect(chat.id)}><MessageSquarePlus size={15} /><span>{chat.title}</span><ArrowLeft size={13} /></button>) : <p>No conversations found.</p>}</div></section></div>
}

export default App
