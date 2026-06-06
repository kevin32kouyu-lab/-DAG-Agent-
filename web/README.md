# 竞品分析前端

这是竞品分析 Agent 协作系统的 React 前端。它负责展示预设 Demo、任务进度、分析报告、图表和技术细节。

## 本地运行

```powershell
cd E:\Agent_Project\web
npm install
npm run dev
```

前端默认通过 Vite 代理访问后端 `/api` 和 `/ws`。

## 测试

```powershell
npm run test
npm run build
```

## 当前展示重点

- 首页先展示预设案例和四阶段流程。
- 报告页优先展示正文、图表和证据链。
- 技术细节页保留给需要查看 DAG 和 Trace 的用户。
