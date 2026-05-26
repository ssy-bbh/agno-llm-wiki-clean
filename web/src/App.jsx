import { useState, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import QueryMode from './components/QueryMode'
import ForgeMode from './components/ForgeMode'

export default function App() {
  const [mode, setMode] = useState('query') // 'query' | 'forge'
  const [selectedSandbox, setSelectedSandbox] = useState(0)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-900 text-slate-100">
      <Sidebar
        mode={mode}
        onModeChange={setMode}
        selectedSandbox={selectedSandbox}
        onSandboxSelect={setSelectedSandbox}
      />
      <main className="flex-1 overflow-hidden relative">
        {/* 💡 修复：把 selectedSandbox 传给两个主画布，让它们知道当前在哪个知识库里 */}
        {mode === 'query' ? (
          <QueryMode selectedSandbox={selectedSandbox} />
        ) : (
          <ForgeMode selectedSandbox={selectedSandbox} />
        )}
      </main>
    </div>
  )
}
