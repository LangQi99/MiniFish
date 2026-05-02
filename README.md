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

### Step 01

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/graph/ontology/generate` | 上传文件 + 模拟需求 → 创建项目 + 生成本体 |
| POST | `/api/graph/build` | 异步构建图谱 |
| GET | `/api/graph/task/<task_id>` | 查询构建任务进度 |
| GET | `/api/graph/data/<graph_id>` | 拉取图谱节点和边（前端轮询绘制） |
| GET | `/api/graph/project/<project_id>` | 项目详情 |
| GET | `/api/graph/project/list` | 项目列表 |
| DELETE | `/api/graph/project/<project_id>` | 删除项目 |

### Step 02

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/personas/generate` | 启动人设生成（异步、并行） |
| GET | `/api/personas/task/<task_id>` | 任务进度 |
| GET | `/api/personas/<project_id>` | 拉取已生成的人设（实时增量） |

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
│   │   ├── api/        # graph.py + personas.py
│   │   ├── models/     # project.py + task.py
│   │   ├── services/   # ontology / graph / persona 生成器
│   │   └── utils/      # llm_client / file_parser / logger / retry
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── api/        # graph.js + personas.js
│   │   ├── components/ # GraphPanel + Step1GraphBuild
│   │   └── views/      # Home / MainView / PersonasView
│   └── package.json
├── docker-compose.yml  # Neo4j + Qdrant
└── .env.example
```
