# 测试说明

这个目录里的测试分为三类：

- 默认本地测试：验证核心后端逻辑，不主动调用真实 LLM。
- 真实 LLM 测试：会调用外部模型，默认跳过。
- 前端测试：在 `web/` 目录运行。

## 默认后端测试

```powershell
cd E:\Agent_Project
.venv\Scripts\python.exe -m pytest tests -q
```

## 真实 LLM 测试

真实 LLM 测试默认跳过，避免本地全量测试变慢或产生费用。需要手动打开时：

```powershell
cd E:\Agent_Project
$env:RUN_REAL_LLM_TESTS=1
.venv\Scripts\python.exe -m pytest tests -q
```

## 前端测试

```powershell
cd E:\Agent_Project\web
npm run test
npm run build
```
