# 报告可视化图表问题清单

**记录时间：** 2026-06-09（首次）/ 2026-06-09（追加 Demo2）
**场景：**
- **Demo 1**：企业微信 / 钉钉 / 飞书（企业协作 IM）
- **Demo 2**：Cursor / GitHub Copilot / Trae（AI 编程工具）
**严重程度：** 🔴 高 — 多个 Demo 主题下复现同类问题，说明是**系统性缺陷**而非数据偶发

---

## ⚠️ 跨 Demo 复现的系统性问题（看这里就够了）

下面 5 大类问题在两个完全不同主题的 Demo 中**全部复现**，证明是底层 agent / 可视化层的设计缺陷：

| 问题类别 | Demo 1 表现 | Demo 2 表现 | 根因层 |
|---------|------------|-------------|--------|
| **维度归一化缺失** | 功能矩阵充满"飞书多维表格"等独家功能名 | 功能矩阵充满"China-Specific Edition with Doubao Model"等独家功能 | feature_analyzer |
| **缺失值用 unknown 占满** | ~70% 灰格 | ~75% 灰格 | feature_analyzer + 前端 |
| **SWOT 数字过度对称** | 优势 15(各5) / 机会 12(各4) / 威胁 15(各5) | 优势 15(各5) / 机会 15(各5) / 威胁 15(各5) | swot_synthesizer prompt |
| **定价图量级失衡** | 飞书 10 万撑爆 | Trae Enterprise ≈40，Pro 档差距悬殊 | pricing_analyst 可视化 |
| **价值分高度同质** | 0.7 / 0.7 / 0.8 | 类似窄分布 | writer / scoring 模板 |
| **某图整块缺失/空态丑陋** | — | **情感分析整块"暂无情感数据"** | sentiment_analyzer 对编程工具场景无适配 |
| **分类标签中英混排** | AI / COLLABORATION / API / ... | AI / UI / INTEGRATION / SECURITY / COLLABORATION | feature_analyzer 输出层 |

---

## Demo 1：企业协作 IM（企业微信 / 钉钉 / 飞书）

### 一、用户情感分析（Sentiment Score 柱状图）

#### 1.1 performance 维度严重缺失
- **现象：** performance 列只有飞书一根柱子（≈-0.2），企业微信/钉钉完全没数据。
- **建议：** sentiment_analyzer 输出契约强制竞品 × 维度笛卡尔积，缺失补 null 并在前端标记"无数据"。

#### 1.2 维度覆盖不一致
- pricing / usability / features 三方都有，performance 仅一方。

### 二、功能成熟度矩阵（Maturity Heatmap）

#### 2.1 🔴 unknown 状态泛滥（核心问题）
- ~70% 格子是 unknown，每行通常只 1 家 ga。
- **根因：** Feature 列直接用产品独有功能名（"飞书多维表格""DING 消息""企微文档协作"）。
- **修复：** Feature 列必须是**通用能力**（"在线表格""强提醒消息""在线文档协作"），由 feature_analyzer 抽取后做"特性归并"。

#### 2.2 状态枚举单一
- 几乎只有 ga / unknown，仅出现一次 beta。

#### 2.3 分类标签中英混排
- AI / COLLABORATION / API / ANALYTICS / INTEGRATION / MOBILE / SECURITY 是英文，子项却是中文。

### 三、SWOT 分析概览

#### 3.1 🟠 四象限计数对称，疑似凑数
- 优势 15（各 5）/ 劣势 15（各 5）/ 机会 12（各 4）/ 威胁 15（各 5）。
- **修复：** 移除"每家强制 N 条"约束，prompt 强调"基于证据自然产出"。

#### 3.2 没有展示具体 SWOT 条目
- 只有数字，无 drill-down。

### 四、定价方案对比（Price Plans）

#### 4.1 🔴 Y 轴被极值撑爆
- 飞书"专属版"100,000 元，其它方案全压成贴地细线。
- **修复：** log 坐标 / 按档位分组 / 改为表格 + 价格区间。

#### 4.2 方案名未对齐
- "基础免费版/商业专业版/免费版/专业版/专属版/数据保障计划"是各产品原名，没归一化。

#### 4.3 企业微信柱子几乎看不到
- 紫色图例存在但无可见柱。

### 五、价值评分对比（Value Score 0-1）

#### 5.1 三家分值同质（0.7 / 0.7 / 0.8）
- 缺打分维度拆解，看不出依据。

#### 5.2 缺少打分维度说明
- 没有 tooltip / 计算公式。

---

## Demo 2：AI 编程工具（Cursor / GitHub Copilot / Trae）

### 六、维度评分对比（Radar 雷达图）

#### 6.1 三个产品轮廓几乎完全重叠
- **现象：** 雷达图上三家的多边形高度重叠，几乎看不出差异（功能丰富度 / AI 代码质量 / 使用成本 / 生态成熟度 / 隐私安全）。
- **影响：** 雷达图核心价值就是"看差异"，重叠等于失效。
- **建议：**
  - 检查 [src/agents/writer.py](src/agents/writer.py) 或评分聚合逻辑是否过度平均
  - 每个维度的打分应当能拉开档次（如 Cursor 应该在 AI 代码质量上明显领先 Copilot 的旧模型）
  - 可考虑改用平行坐标图或差异柱状图

### 七、用户情感分析 —— 🔴 整块空态

#### 7.1 "暂无情感数据"
- **现象：** 整个情感分析区域显示空状态图标 + "暂无情感数据"。
- **根因：** sentiment_analyzer 在 AI 编程工具场景下没有适配数据源（Reddit / HackerNews / Twitter 上的开发者评论没采集，或采了没分类）。
- **影响：** Demo 演示时整块卡片空着非常丑。
- **建议：**
  - 至少要采到 Reddit r/cursor / r/github / HN 的评论
  - 即便没数据，空态文案应改为"该主题暂未采集到足量开发者评论"并给出 collector 重跑入口
  - 或者隐藏该卡片而不是显示空态

### 八、功能成熟度矩阵 —— 🔴 比 Demo 1 还严重

#### 8.1 unknown 比例更高（~75%+）
- **现象：** Feature 列充斥产品独家功能名：
  - "China-Specific Edition with Doubao Model"（Trae 独家）
  - "Composer Multi-File Edits"（Cursor 独家）
  - "Multi-Model Selection (Copilot Extensions)"（Copilot 独家）
  - "Skill System"、"Voice Input Support"（Trae 独家）
- **影响：** 与 Demo 1 同根因——矩阵看起来像三个独立产品功能列表的拼接。
- **典型坏例：**
  - "AI-Powered Code Completion" → Cursor unknown / Copilot unknown / Trae ga（**这是三家都有的核心功能，竟然两家 unknown？？**）
  - "Built-in Git & GitHub Integration" → Cursor unknown / Copilot ga / Trae beta（**Cursor 显然原生支持 Git，但被标 unknown**）

#### 8.2 明显错误数据
- "AI-Powered Code Completion" 三家都有却两家 unknown —— 说明 feature_analyzer **没有从竞品基础能力库回填 ga**，只要 raw 数据里没明确证据就标 unknown。
- **修复：** 对"行业通用核心能力"建立白名单，所有竞品默认 ga，除非有证据表明缺失。

#### 8.3 分类标签顺序怪异
- 顺序为 AI / UI / INTEGRATION / SECURITY / COLLABORATION，且 COLLABORATION 只有一行（Pull Request Review & Summary）。
- **建议：** 按重要性 + 行业惯例排序（AI / IDE 集成 / 协作 / 安全 / 部署），并合并小分类。

### 九、SWOT 分析概览 —— 🟠 数字对称更严重

#### 9.1 三象限正好各 15 条（各 5）
- 优势 15(各 5) / 劣势 15(各 5) / **机会 15(各 5)** / 威胁 15(各 5)
- 比 Demo 1 还要"齐整"（Demo 1 机会还是 12，Demo 2 直接全部一致）。
- **证实：** swot_synthesizer 几乎肯定有"每家产出 5 条 SWOT"的硬模板。

### 十、定价方案对比（Price Plans）

#### 10.1 量级失衡（虽不如 Demo 1 极端）
- Trae Enterprise ≈40（美元/月？），其它档位 10-25 之间。
- **现象：** Cursor 在 Free 档没有柱子？Pro 档 Cursor 紫色柱看不清。
- **建议：**
  - 明确单位（USD/month vs CNY/year）
  - 颜色对比度提升（紫色 Cursor 在浅色背景下不清晰）
  - 标注"按 X 用户/X 月" 的归一化口径

#### 10.2 方案名仍未对齐
- "Free / Pro / Individual / Business / Enterprise" 混合了不同产品的档位命名。

### 十一、价值评分对比

#### 11.1 三家分值依然同质
- Trae / Cursor / GitHub Copilot 三条横柱长度接近（≈0.55-0.65 区间）。
- 同 Demo 1 问题 5.1。

### 十二、顶部 KPI / 元信息

#### 12.1 "3 产品 · 5 维度" 元信息
- 维度数（5）应该在雷达图标注，让用户对应得上。

---

## 根因总结（更新版）

跨两个 Demo 复现的问题，可归并为以下**底层缺陷**：

| 缺陷 | 影响层 | 必须修 |
|------|--------|--------|
| **特性归一化缺失** | feature_analyzer | 🔴 |
| **核心能力默认值错误**（不应默认 unknown） | feature_analyzer | 🔴 |
| **极值未处理**（log / 分档） | pricing 可视化 | 🔴 |
| **SWOT 强制 N 条模板** | swot_synthesizer prompt | 🟠 |
| **情感分析场景适配不足** | sentiment_analyzer + collector | 🟠 |
| **维度打分缺乏区分度** | writer / scoring | 🟠 |
| **空态/缺失值处理粗暴** | 前端组件库 | 🟠 |
| **分类标签中英混排** | 输出层规范 | 🟡 |
| **价值分缺解释性** | writer + 前端 tooltip | 🟡 |

---

## 修复优先级（合并版）

| 优先级 | 问题 | 影响 |
|--------|------|------|
| 🔴 P0 | 功能矩阵 unknown 泛滥（2.1 / 8.1 / 8.2） | 两个 Demo 都翻车 |
| 🔴 P0 | 定价图极值/量级问题（4.1 / 10.1） | Demo 当场翻车 |
| 🔴 P0 | 编程工具场景情感分析空态（7.1） | Demo 整块空白 |
| 🟠 P1 | SWOT 数字对称（3.1 / 9.1） | 可信度问题 |
| 🟠 P1 | 情感分维度缺失（1.1） | 误导用户 |
| 🟠 P1 | 雷达图无差异（6.1） | 雷达图失效 |
| 🟡 P2 | 价值分同质化（5.1 / 11.1） | 可解释性弱 |
| 🟡 P2 | 分类中英混排（2.3 / 8.3） | 视觉细节 |

---

## 涉及文件（待修复）

- **数据采集层**：[src/agents/collector.py](src/agents/collector.py)、[src/agents/data_enricher.py](src/agents/data_enricher.py)、[src/agents/source_discovery.py](src/agents/source_discovery.py)
- **分析层**：
  - [src/agents/feature_analyzer.py](src/agents/feature_analyzer.py) ← **重点**：特性归一化 + 核心能力白名单
  - [src/agents/sentiment_analyzer.py](src/agents/sentiment_analyzer.py) ← 场景适配
  - [src/agents/pricing_analyst.py](src/agents/pricing_analyst.py) ← 量级处理
  - [src/agents/swot_synthesizer.py](src/agents/swot_synthesizer.py) ← 去除 N 条硬约束
- **Demo 数据**：[scripts/enrich_demo_data.py](scripts/enrich_demo_data.py)、[data/](data/)
- **前端可视化**：
  - [web/src/pages/Report.tsx](web/src/pages/Report.tsx) ← 空态/缺失值处理
  - [web/src/demoContent.ts](web/src/demoContent.ts) ← Demo 数据归一化
  - [web/src/pages/Monitor.tsx](web/src/pages/Monitor.tsx)
