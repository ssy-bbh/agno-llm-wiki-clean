import { useState, useEffect, useRef } from 'react'
import { marked } from 'marked' // 💡 换成更健壮、对流式输出极度宽容的 marked 引擎

export default function QueryMode({ selectedSandbox }) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef(null)

  // 💡 核心会话隔离：一旦在左侧边栏切换了沙箱隔离区，强制重置当前对话，防止记忆跨库交叉污染
  useEffect(() => {
    setMessages([])
    setInput('')
  }, [selectedSandbox])

  // 自动平滑滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const handleSend = async () => {
    if (!input.trim() || isTyping) return

    const currentInput = input.trim()
    const userMsg = { role: 'user', content: currentInput }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)

    // 初始化 AI 气泡与思维轨迹日志数组
    const assistantMsg = { role: 'assistant', content: '', logs: [] }
    setMessages(prev => [...prev, assistantMsg])

    // 💡 记忆提纯：在发送前提取当前的有效聊天记录，过滤掉报错和空信息
    const chatHistory = messages
      .filter(m => m.role && m.content && !m.content.includes('❌'))
      .map(m => ({ role: m.role, content: m.content }))

    try {
      // 🚀 双端连接：将问题、当前隔离区沙箱标识、历史上下文捆绑发往后端
      const response = await fetch('http://127.0.0.1:8888/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: currentInput,
          workspace: selectedSandbox || "",
          history: chatHistory
        })
      })

      if (!response.ok) throw new Error(`HTTP 错误! 状态码: ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      // 💡 工业级防线：声明数据流缓冲区，完美解决网络碎片折断 JSON 的问题
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()

        if (value) {
          buffer += decoder.decode(value, { stream: true })
        }

        const parts = buffer.split('\n\n')

        // 如果流未结束，最后一个包可能不完整，弹出并留到下一轮循环拼接
        if (!done) {
          buffer = parts.pop() || ''
        }

        for (const line of parts) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '')
            if (!dataStr.trim()) continue

            try {
              const data = JSON.parse(dataStr)

              if (data.type === 'log') {
                setMessages(prev => {
                  const newMsgs = [...prev]
                  const lastIdx = newMsgs.length - 1
                  newMsgs[lastIdx] = {
                    ...newMsgs[lastIdx],
                    logs: [...(newMsgs[lastIdx].logs || []), { text: data.content }]
                  }
                  return newMsgs
                })
              } else if (data.type === 'text') {
                setMessages(prev => {
                  const newMsgs = [...prev]
                  const lastIdx = newMsgs.length - 1
                  newMsgs[lastIdx] = {
                    ...newMsgs[lastIdx],
                    content: newMsgs[lastIdx].content + data.content
                  }
                  return newMsgs
                })
              }
            } catch (err) {
              console.warn("解析 SSE 数据包失败:", dataStr, err)
            }
          }
        }

        if (done) break
      }
    } catch (e) {
      console.error("流式通信断开:", e)
      setMessages(prev => {
        const newMsgs = [...prev]
        const lastIdx = newMsgs.length - 1
        newMsgs[lastIdx] = {
          ...newMsgs[lastIdx],
          content: "❌ 链路发生严重故障，无法获取本地知识引擎响应，请检查后端网关状态。"
        }
        return newMsgs
      })
    } finally {
      setIsTyping(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-slate-900 relative">
      {/* 沙箱隔离雷达指示器 */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 px-4 py-1.5 rounded-full bg-slate-800/90 border border-slate-700/60 backdrop-blur-sm flex items-center gap-2 shadow-lg">
        <div className={`w-2 h-2 rounded-full ${selectedSandbox ? 'bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.6)]' : 'bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)]'}`}></div>
        <span className="text-xs font-mono text-slate-300">
          {selectedSandbox ? `[隔离区激活] 正在定向检索: ${selectedSandbox}` : '[全局漫游] 广域知识检索'}
        </span>
      </div>

      {/* 消息历史画布 */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 scrollbar-thin pt-16">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 font-mono space-y-2">
            <span className="text-3xl animate-bounce">🗣️</span>
            <p className="text-sm">知识库探求中心已就绪，请输入你的提问...</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              {msg.role === 'user' ? (
                <div className="max-w-[80%] bg-slate-800 border border-slate-700/60 rounded-2xl px-4 py-3 text-slate-200 text-sm shadow-md">
                  {msg.content}
                </div>
              ) : (
                <div className="max-w-[85%] w-full space-y-3">
                  {/* 物理思维轨迹 (Terminal 日志推流) */}
                  {msg.logs && msg.logs.length > 0 && (
                    <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 font-mono text-[11px] text-slate-400 max-h-[160px] overflow-y-auto space-y-1 shadow-inner">
                      <p className="text-[10px] text-cyan-500/80 border-b border-slate-800/60 pb-1 mb-1 font-semibold uppercase tracking-wider">⚡ Thinking Process & Action Stream</p>
                      {msg.logs.map((log, lIdx) => (
                        <div key={lIdx} className="text-emerald-400/90 whitespace-pre-wrap">{log.text}</div>
                      ))}
                    </div>
                  )}

                  {/* 回答正文气泡 */}
                  {msg.content && (
                    <div className="bg-slate-800/40 border border-slate-800/60 rounded-2xl px-5 py-4 text-slate-200 text-sm shadow-sm leading-relaxed">
                      {/* 💡 核心修复：使用 marked 渲染流式文本，配合 Tailwind 自动格式化图片和链接 */}
                      <div
                        className="prose prose-invert max-w-none prose-sm prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700 prose-img:max-w-full prose-img:h-auto prose-img:rounded-lg prose-img:my-2 prose-img:border prose-img:border-slate-700/50 prose-img:shadow-sm prose-a:text-cyan-400 hover:prose-a:text-cyan-300 prose-a:underline"
                        dangerouslySetInnerHTML={{
                          __html: marked.parse(msg.content || '')
                        }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {/* 打字机加载状态 */}
        {isTyping && messages[messages.length - 1]?.content === '' && (
          <div className="flex items-center gap-1.5 px-4 text-xs text-slate-500 font-mono">
            <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
            <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
            <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce"></span>
            <span className="ml-1">本地知识引擎正在提取并解析文件实体...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 底部指令输入台 */}
      <div className="p-4 bg-slate-950/40 border-t border-slate-800/80 backdrop-blur-md">
        <div className="max-w-4xl mx-auto flex gap-2 bg-slate-900 border border-slate-700/50 rounded-xl p-1.5 focus-within:border-cyan-500/50 transition-all duration-200 shadow-lg">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={selectedSandbox ? `在 [${selectedSandbox}] 隔离区中发起深度探求...` : "向所有知识库广域探求..."}
            className="flex-1 bg-transparent text-slate-200 text-sm px-3 focus:outline-none placeholder-slate-500"
            disabled={isTyping}
          />
          <button
            onClick={handleSend}
            disabled={isTyping || !input.trim()}
            className={`px-4 py-2 rounded-lg text-xs font-mono font-semibold transition-all duration-200 ${
              isTyping || !input.trim()
                ? 'bg-slate-800 text-slate-600 cursor-not-allowed'
                : 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950 shadow-[0_0_10px_rgba(34,211,238,0.2)] hover:opacity-90'
            }`}
          >
            {isTyping ? "RUNNING" : "EXECUTE"}
          </button>
        </div>
      </div>
    </div>
  )
}