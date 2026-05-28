import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'

export default function AdminDashboard({ onClose }) {
  const { apiFetch } = useAuth()
  const [users, setUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState(null)
  const [sessions, setSessions] = useState([])
  const [selectedSession, setSelectedSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchUsers()
  }, [])

  useEffect(() => {
    if (selectedUser) fetchSessions(selectedUser)
  }, [selectedUser])

  useEffect(() => {
    if (selectedSession) fetchMessages(selectedSession)
  }, [selectedSession])

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/api/admin/users')
      setUsers(await res.json())
    } catch (e) {
      console.error('fetch users error:', e)
    } finally {
      setLoading(false)
    }
  }

  const fetchSessions = async (userId) => {
    try {
      const res = await apiFetch(`/api/admin/sessions?user_id=${encodeURIComponent(userId)}`)
      setSessions(await res.json())
    } catch (e) {
      console.error('fetch sessions error:', e)
      setSessions([])
    }
    setSelectedSession(null)
    setMessages([])
  }

  const fetchMessages = async (sessionId) => {
    try {
      const res = await apiFetch(`/api/admin/sessions/${encodeURIComponent(sessionId)}/messages`)
      const data = await res.json()
      setMessages(data.messages || [])
    } catch (e) {
      console.error('fetch messages error:', e)
      setMessages([])
    }
  }

  const formatTime = (ts) => {
    if (!ts) return '—'
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto w-[90vw] max-w-[1200px] h-full bg-slate-900/98 border-l border-slate-700/50 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-700/50 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <span>🔍</span> 管理员监控台
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors text-lg">✕</button>
        </div>

        {/* 3-column layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Column 1: Users */}
          <div className="w-56 border-r border-slate-700/40 flex flex-col">
            <div className="px-4 py-2 border-b border-slate-700/30">
              <p className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">Users</p>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="text-center text-slate-500 py-6 text-xs">Loading...</div>
              ) : users.map(u => (
                <button
                  key={u.user_id}
                  onClick={() => { setSelectedUser(u.user_id); }}
                  className={`w-full text-left px-4 py-3 border-b border-slate-800/40 hover:bg-slate-800/50 transition-colors ${
                    selectedUser === u.user_id ? 'bg-slate-800/70 border-l-2 border-l-cyan-400' : ''
                  }`}
                >
                  <p className="text-xs text-slate-200 font-medium">{u.username}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[9px] px-1.5 py-0.5 rounded ${u.role === 'admin' ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-700/50 text-slate-400'}`}>
                      {u.role}
                    </span>
                    <span className="text-[9px] text-slate-500">{u.session_count} 会话</span>
                  </div>
                  <p className="text-[9px] text-slate-600 mt-0.5">活跃: {formatTime(u.last_active)}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Column 2: Sessions */}
          <div className="w-64 border-r border-slate-700/40 flex flex-col">
            <div className="px-4 py-2 border-b border-slate-700/30">
              <p className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">
                Sessions {selectedUser ? `— ${selectedUser}` : ''}
              </p>
            </div>
            <div className="flex-1 overflow-y-auto">
              {!selectedUser ? (
                <div className="text-center text-slate-600 py-8 text-xs">← 选择用户</div>
              ) : sessions.length === 0 ? (
                <div className="text-center text-slate-600 py-8 text-xs">无会话记录</div>
              ) : sessions.map(s => (
                <button
                  key={s.session_id}
                  onClick={() => setSelectedSession(s.session_id)}
                  className={`w-full text-left px-4 py-3 border-b border-slate-800/40 hover:bg-slate-800/50 transition-colors ${
                    selectedSession === s.session_id ? 'bg-slate-800/70 border-l-2 border-l-emerald-400' : ''
                  }`}
                >
                  <p className="text-xs text-slate-200 truncate">{s.name || '(未命名)'}</p>
                  <p className="text-[9px] text-slate-500 mt-1 font-mono">{formatTime(s.updated_at)}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Column 3: Messages */}
          <div className="flex-1 flex flex-col">
            <div className="px-4 py-2 border-b border-slate-700/30">
              <p className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">
                Messages {selectedSession ? `— ${selectedSession.split(':').pop()?.slice(0, 12)}` : ''}
              </p>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {!selectedSession ? (
                <div className="h-full flex items-center justify-center text-slate-600 text-xs">← 选择会话查看消息</div>
              ) : messages.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-600 text-xs">无消息</div>
              ) : messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-xs ${
                    m.role === 'user'
                      ? 'bg-cyan-500/10 border border-cyan-500/20 text-cyan-200'
                      : 'bg-slate-800/60 border border-slate-700/40 text-slate-300'
                  }`}>
                    <p className="text-[9px] text-slate-500 mb-1 font-mono">
                      {m.role === 'user' ? '👤 用户' : '🤖 AI'}
                    </p>
                    <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
