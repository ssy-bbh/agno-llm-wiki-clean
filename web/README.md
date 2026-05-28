# LLM-Wiki OS — Web 前端

> 赛博风双模 SPA：探求模式（对话检索）+ 织网模式（知识图谱 + 维护控制台）

---

## 技术栈

| 层 | 选型 |
|---|---|
| 框架 | React 18 (Functional Components + Hooks) |
| 构建 | Vite 6 |
| 样式 | Tailwind CSS 3 (Dark Mode, 毛玻璃 + 发光) |
| 图形 | react-force-graph-2d (力导向物理图) |
| Markdown | marked |

---

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器（自动打开浏览器）
npm run dev
# → http://localhost:3000

# 构建生产包
npm run build

# 预览构建产物
npm run preview
```

---

## 双模布局

```
┌──────────────┬────────────────────────────────────────┐
│              │                                        │
│  Sidebar     │          主画布                         │
│  260px       │                                        │
│              │  ┌─────────────┐  ┌──────────────────┐ │
│  🧠 Logo     │  │             │  │                  │ │
│  探求/织网    │  │  探求模式:   │  │  织网模式:        │ │
│  沙箱雷达    │  │  对话气泡     │  │  70% 力导向图    │ │
│  状态指示    │  │  终端轨迹     │  │  30% 控制台      │ │
│              │  │  Markdown    │  │  熔炉/审批/       │ │
│              │  │  输入框       │  │  雷达/档案        │ │
│              │  └─────────────┘  └──────────────────┘ │
│              │                                        │
└──────────────┴────────────────────────────────────────┘
```

### 探求模式 (Query Mode)
- 底部输入框 + 发送按钮
- 对话气泡：上半部分终端轨迹（执行日志逐步打印），下半部分 Markdown 渲染回答
- 打字机效果 + 模拟思维轨迹

### 织网模式 (Forge Mode)
- **左侧 70%**：全屏力导向图，14+ 节点，发光效果，节点分组着色
- **右侧 30%**：4 个 tab 页签
  - ☁️ **赛博熔炉**：文件拖拽摄入 + 进度条 + 重织死链/填补黑洞按钮
  - ✅ **隔离审批区**：待确认草稿列表，支持预览/入库/废弃
  - 📡 **需求雷达**：用户搜索落空记录，阈值预警
  - 📜 **织网档案室**：操作审计日志

---

## 目录结构

```
web/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── src/
    ├── main.jsx              # React 入口
    ├── App.jsx               # 双模路由
    ├── index.css             # Tailwind + 自定义动画
    ├── data/
    │   └── mockData.js       # Mock 数据（图节点/审批/雷达/日志）
    └── components/
        ├── Sidebar.jsx       # 左侧栏
        ├── QueryMode.jsx     # 探求模式
        ├── ForgeMode.jsx     # 织网模式容器
        ├── ForceGraph.jsx    # 力导向图
        ├── CyberForge.jsx    # 赛博熔炉卡片
        ├── Inbox.jsx         # 隔离审批卡片
        ├── Radar.jsx         # 需求雷达卡片
        └── AuditLog.jsx      # 审计日志卡片
```

---

## 对接后端

当前全部使用 Mock 数据。对接后端时：

1. **探求模式**：`QueryMode.jsx` 中将 `setTimeout` 替换为 `fetch('/api/query', ...)`
2. **力导向图**：`ForceGraph.jsx` 中 `graphData` 从 `fetch('/api/wiki/graph')` 加载
3. **审批 Inbox**：`mockInboxItems` → `fetch('/api/inbox')` + POST 审批操作
4. **需求雷达**：`mockRadarItems` → `fetch('/api/radar')`
5. **审计日志**：`mockAuditLogs` → SSE/WebSocket 实时推送

后端 FastAPI 已配置 CORS，`localhost:3000` 可直接访问。

---

## 授权声明

**无开源许可证。** 仅供项目内部使用，未经授权禁止复制、分发或商用。
