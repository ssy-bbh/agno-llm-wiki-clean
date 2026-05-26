import { useState, useRef, useEffect } from 'react'
import { marked } from 'marked'
import { mockQueryResponse } from '../data/mockData'

// Terminal log lines that appear sequentially
const MOCK_LOG_LINES = [
  { text: '> 路由分析中...', delay: 400 },
  { text: '> 挂载本地知识库: data/wiki/', delay: 800 },
  { text: '> LanceDB 向量检索: 3 个候选命中', delay: 1400 },
  { text: '> 检索 index.md 全局导航...', delay: 2000 },
  { text: '> 启动 web_researcher 交叉验证', delay: 2800 },
  { text: '> 合成回答...', delay: 3500 },
]

function TerminalBlock({ lines }) {
  const [visible, setVisible] = useState(false)
  const [shownLines, setShownLines] = useState([])

  useEffect(() => {
    if (lines.length === 0) return
    setVisible(true)
    const timeouts = lines.map((line) =>
      setTimeout(() => {
        setShownLines(prev => [...prev, line.text])
      }, line.delay)
    )
    return () => timeouts.forEach(clearTimeout)
  }, [lines])

  if (!visible) return null

  return (
    <div className="bg-black/60 rounded-lg border border-slate-700/50 p-3 font-mono text-xs">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-700/30">
        <div className="w-2 h-2 rounded-full bg-red-500/80" />
        <div className="w-2 h-2 rounded-full bg-yellow-500/80" />
        <div className="w-2 h-2 rounded-full bg-green-500/80" />
        <span className="text-slate-500 text-[10px] ml-1">思维轨迹</span>
      </div>
      <div className="space-y-0.5">
        {shownLines.map((line, i) => (
          <div key={i} className="text-emerald-400/80 leading-relaxed animate-fade-in">
            {line}
          </div>
        ))}
        {shownLines.length < lines.length && (
          <div className="text-emerald-400/40 typing-cursor">&nbsp;</div>
        )}
      </div>
    </div>
  )
}

function ChatBubble({ message }) {
  const { role, content, logs } = message
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 animate-slide-up`}>
      <div className={`max-w-[80%] ${isUser ? 'order-1' : ''}`}>
        {/* Terminal logs (only for assistant) */}
        {!isUser && logs && logs.length > 0 && (
          <div className="mb-2">
            <TerminalBlock lines={logs} />
          </div>
        )}

        {/* Message bubble */}
        <div className={`rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-emerald-500/15 border border-emerald-500/30 text-slate-100'
            : 'glass rounded-tl-none text-slate-200'
        }`}>
          {isUser ? (
            <p className="text-sm leading-relaxed">{content}</p>
          ) : (
            <div
              className="prose prose-sm prose-invert max-w-none prose-headings:text-cyan-300 prose-a:text-emerald-400 prose-code:text-amber-300 prose-code:bg-slate-800/60 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-blockquote:border-l-cyan-500/50 prose-blockquote:text-slate-400 prose-strong:text-slate-100"
              dangerouslySetInnerHTML={{ __html: marked.parse(content) }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default function QueryMode() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || isTyping) return
    const userMsg = { role: 'user', content: input.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)

    // Simulate assistant response with delay
    setTimeout(() => {
      const assistantMsg = {
        role: 'assistant',
        content: mockQueryResponse,
        logs: MOCK_LOG_LINES,
      }
      setMessages(prev => [...prev, assistantMsg])
      setIsTyping(false)
    }, 600)
  }

  return (
    <div className="flex flex-col h-full bg-slate-900 relative">
      {/* Subtle grid background */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: 'linear-gradient(rgba(148,163,184,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.3) 1px, transparent 1px)',
        backgroundSize: '40px 40px'
      }} />

      {/* Chat area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 relative z-10">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-5xl mb-4 opacity-40">🔮</div>
            <h2 className="text-lg font-semibold text-slate-400 mb-1">知识探求模式</h2>
            <p className="text-sm text-slate-600 max-w-md">向系统提问，LLM 将检索本地知识库与互联网资源，合成结构化回答。</p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {['Transformer 核心原理', 'RAG 系统如何工作', 'RLHF 训练流程'].map(q => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="px-3 py-1.5 text-xs rounded-full border border-slate-700/50 text-slate-400 hover:border-emerald-500/40 hover:text-emerald-400 transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <ChatBubble key={i} message={msg} />
            ))}
            {isTyping && (
              <div className="flex items-center gap-2 text-slate-500 text-xs animate-pulse ml-2">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                <span>系统正在分析中...</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Input bar */}
      <div className="px-6 pb-5 relative z-10">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="输入你的问题，系统将检索知识库并合成回答..."
            className="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500/40 focus:glow-emerald transition-all font-light"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isTyping}
            className={`px-5 py-3 rounded-xl text-sm font-medium transition-all ${
              input.trim() && !isTyping
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 glow-emerald'
                : 'bg-slate-800/30 text-slate-600 border border-slate-700/30 cursor-not-allowed'
            }`}
          >
            发送 ↵
          </button>
        </div>
      </div>
    </div>
  )
}
