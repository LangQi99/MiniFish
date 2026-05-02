# MiniFish

**长文本 → GraphRAG → Agent 人设** 的两步精简版 Demo，从 [MiroFishOpt](../MiroFishOpt) 抽取并裁剪而来。

## 流程

| 步骤 | 名称 | 说明 |
| --- | --- | --- |
| **01** | 模拟实例初始化 | 上传一份长文本 + 一段模拟需求 → LLM 生成本体 → 并行抽取实体/关系写入 Neo4j → 前端实时绘制 |
| **02** | 生成 Agent 人设 | 基于图谱节点并行调用 LLM 生成详细 Agent 人设（个人 / 群体两套模板），实时落盘 + 流式上屏 |

两步均使用 `ThreadPoolExecutor` 并行加速，并发数可在 `.env` 中调节。

## 端口

| 服务 | 端口 |
| --- | --- |
| Neo4j Browser | 7474 |
| Neo4j Bolt | 7687 |
| Qdrant HTTP | 6333 |
| Backend (Flask) | 5101 |
| Frontend (Vite) | 3100 |

> 注意：与 MiroFishOpt 共用相同的 Neo4j / Qdrant 端口，**不能同时运行两个项目的 docker compose**。

## 快速开始

```bash
# 1. 准备配置
cp .env.example .env
# 填入 LLM_API_KEY 等

# 2. 启动依赖
docker compose up -d

# 3. 后端
cd backend
pip install -r requirements.txt
python run.py
# → http://localhost:5101/health

# 4. 前端（另开终端）
cd frontend
npm install
npm run dev
# → http://localhost:3100
```

## API

所有响应均为 `{ "success": bool, "data": ..., "error": ... }` 形式;前端 baseURL 默认 `http://localhost:5101`。

### Step 01 · 图谱

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/graph/ontology/generate` | `multipart/form-data`:`files[]` + `simulation_requirement` (+ 可选 `project_name`、`additional_context`)。创建项目并返回本体 |
| POST | `/api/graph/build` | JSON:`{ project_id, graph_name?, chunk_size?, chunk_overlap?, force? }`。异步启动图谱构建,返回 `task_id` |
| GET | `/api/graph/task/<task_id>` | 查询图谱构建任务进度 |
| GET | `/api/graph/data/<graph_id>` | 拉取节点和边,前端 3s 轮询绘制 |
| DELETE | `/api/graph/delete/<graph_id>` | 删除 Neo4j 中的图谱 |
| GET | `/api/graph/project/<project_id>` | 项目详情(含 status / task_id 引用) |
| GET | `/api/graph/project/list?limit=50` | 项目列表(按创建时间倒序) |
| DELETE | `/api/graph/project/<project_id>` | 删除项目目录 + 元数据 |

### Step 02 · 人设

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/personas/generate` | JSON:`{ project_id, parallel?, use_llm?, entity_types?, force? }`。异步启动并行人设生成,返回 `task_id` + `expected_count` |
| GET | `/api/personas/task/<task_id>` | 查询人设生成任务进度(含 `progress_detail.current/total`) |
| GET | `/api/personas/<project_id>` | 拉取已生成的人设(实时增量,前端 1.5s 轮询) |

### 任务总览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/tasks/list` | 所有任务(图谱构建 + 人设生成),按 `updated_at` 倒序。每条含 `task_id / task_type / status / progress / message / metadata.project_id`,供前端历史侧栏按项目聚合 |

### 任务持久化

每次 `TaskManager.update_task` 都会原子写到 `backend/uploads/tasks/<task_id>.json`。后端启动时会扫描该目录恢复任务;`pending` / `processing` 状态的任务会被改写为 `failed`,error 设为 `"interrupted by backend restart"`。

### 健康检查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | `{ status: "ok", service: "MiniFish Backend" }` |

## 本地落盘路径

```
backend/uploads/
├── tasks/<task_id>.json              # 任务进度快照,每次 update 同步写
└── projects/<project_id>/
    ├── project.json                  # 项目元信息 + 本体 + status + 子任务引用
    ├── extracted_text.txt            # 抽取的原文
    ├── files/                        # 上传的源文件
    ├── graph.json                    # 图谱节点/边冷备(Step1 完成时写)
    └── personas.json                 # 人设列表,生成过程中增量更新
```

> Neo4j 仍是图谱的运行时主存;`graph.json` 是脱离 Neo4j 也能直接读的快照备份。

## 与 MiroFishOpt 的差异

- 移除了 Step03 模拟运行 / Step04 报告 / Step05 互动
- 图谱后端固定为 Neo4j + Qdrant（不依赖 Zep Cloud）
- `OasisProfileGenerator` → `PersonaGenerator`，去掉 Zep 检索路径与 OASIS Reddit/Twitter 输出适配
- 不再有 SimulationManager / SimulationRunner / IPC / ReportAgent

## 目录

```
MiniFish/
├── backend/
│   ├── app/
│   │   ├── api/        # graph.py + personas.py + tasks.py
│   │   ├── models/     # project.py + task.py（task 自带落盘 / 启动恢复）
│   │   ├── services/   # ontology / graph / persona 生成器
│   │   └── utils/      # llm_client / file_parser / logger / retry
│   ├── uploads/        # 运行时落盘(tasks/ + projects/)
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── api/        # graph.js + personas.js + tasks.js
│   │   ├── components/ # GraphPanel + HistorySidebar + PersonaCard
│   │   └── views/      # Home(输入) + Dashboard(图谱+人设+历史侧栏)
│   └── package.json
├── docker-compose.yml  # Neo4j + Qdrant
└── .env.example
```
