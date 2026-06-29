# 智能云学习平台

## 概述

智能云学习平台是一个基于 **Python + FastAPI + LangChain** 构建的 AI 微服务，为天机学堂在线教育平台提供智能对话、课程咨询、学习推荐等 AI 能力。该模块逐步替代原有的 Java `tj-aigc` 模块，兼容现有项目接口契约。

本项目的 AI 改造工作是基于 `天机学堂AI课程` 中整理的基础功能要求继续推进的；当前实际改造范围主要集中在 **AI 模块**，包括 Python 微服务、AI 对话链路、RAG、日志落库以及与前端 AI 弹层的本地联调。

该项目支持 AI 模型的调用，包括向量检索、关键词检索、文档导入、文件上传等功能。启动前端点击 AI 助手，即可与模型进行对话。

---
## 快速参考

### 前端启动

```bash
cd tj-portal-src-master && npm run dev
```

### 前端关闭

```
Ctrl + C
```

### 后端启动

```bash
cd tj-aigc-py && python -m uvicorn app.main:app --host 127.0.0.1 --port 8094
```

### 后端关闭

```
Ctrl + C
```

### Redis 启动

流式聊天 `/chat` 依赖 Redis stop 标记，默认读取 `.env` 中的：

- `AIGC_REDIS_URL`
- `AIGC_REDIS_HOST`
- `AIGC_REDIS_PORT`
- `AIGC_REDIS_DB`
- `AIGC_REDIS_PASSWORD`

本地默认可直接启动：

```bash
redis-server --port 6379
```

### 本地知识库重载

项目根目录提供 `_reload.py`，可批量重载本地 `.txt/.md` 知识文档到 MySQL + Chroma：

```bash
cd tj-aigc-py && python _reload.py
```

脚本会自动扫描项目根目录下的知识文档，跳过 `README.md`、`AI模块开发文档.md`、`AI模块介绍.md` 等工程说明文件。

### 文档导入接口

```
POST http://127.0.0.1:8094/document/import
```

### 文件上传接口

```
POST http://127.0.0.1:8094/document/upload
```

## 核心能力

### 1. 智能对话

- **流式对话**：SSE（Server-Sent Events）真实流式输出，直接转发模型生成片段，支持客户端逐字展示与停止生成
- **非流式问答**：兼容传统接口风格的一次性返回
- **对话停止**：用户可随时中断 AI 生成过程（基于 Redis）
- **上下文理解**：自动携带历史对话信息，保持多轮对话连贯性

### 2. 长上下文处理

- **历史摘要压缩**：当对话超过一定轮数（默认 6 条消息），自动对历史内容生成摘要
- **摘要 + 最近消息**：将摘要与最近几轮完整消息拼接输入模型，兼顾上下文质量与 token 成本
- **完整消息可追溯**：摘要仅作为压缩手段，原始对话完整保存在数据库中，不丢失任何信息
- **摘要快照版本管理**：通过 `session_summary_snapshot` 表记录每次摘要快照，支持版本追溯

### 3. 知识库检索（RAG）

- **向量检索**：将知识文档切分后通过 Embedding 模型向量化，存入 Chroma 向量数据库，支持语义检索
- **多路融合检索**：已支持“向量检索 + MySQL 关键词检索 + chunk_id 去重 + 加权融合排序”，用于补强课程名、技术词、专有名词等场景下的召回效果
- **文档导入接口**：支持通过 API 导入文档，自动完成三步处理：文本标准化（清洗空白/统一换行）→ SHA256 整篇文档级去重 → 切片 + Embedding + 入库全流程。MySQL 元数据表 + Chroma 向量库双写，异常时自动事务回滚（删除 Chroma 文档 → 失效分片记录 → 标记失败状态），返回结构化结果
- **文件上传接口**：支持 UTF-8/GBK 编码的 `.txt` 文件上传，读取后走相同三步入库流程
- **检索日志**：通过 `rag_query_log` 表记录每次检索链路，便于排障与效果分析

### 4. 课程智能服务

通过对接后端微服务，AI 可自主完成以下操作：

| 能力 | 说明 |
|------|------|
| **课程查询** | 根据课程名称或关键词查询课程详情 |
| **课程推荐** | 基于热门、最新等维度推荐课程 |
| **精品推荐** | 推荐精选优质课程 |
| **新课推荐** | 推荐最新上架课程 |
| **预下单** | 确认课程购买意向，返回订单信息 |

AI 会**自主判断**何时调用这些工具。例如用户说"推荐几门 Java 课程"，AI 会自动调用搜索推荐工具，而不是给出笼统的回答。

### 5. 模型灵活切换

- 支持千问（DashScope Qwen）和 DeepSeek 等兼容 OpenAI 接口的模型
- 聊天模型与 Embedding 模型独立配置，可自由组合
- 默认配置为千问 `qwen-plus` + `text-embedding-v3`

### 6. 会话管理

- 会话创建与标题自动生成
- 历史会话列表查询（按时间分组：当天/30天/1年/1年以上）
- 热门问题推荐
- 完整的消息历史回溯（按 message_order 排序）

---

## 架构设计

### 技术栈

| 层 | 技术 |
|------|------|
| 框架 | FastAPI |
| AI 编排 | LangChain |
| 数据库 | MySQL（主存储 — 6 张核心表） |
| 向量库 | Chroma（本地文件持久化） |
| 缓存 | Redis（运行态辅助：stop 标记） |
| 配置中心 | Nacos（可选） |

### MySQL 六张核心表

| 表名 | 职责 |
|------|------|
| `knowledge_document` | 知识库文档元数据（来源、版本、状态） |
| `knowledge_chunk` | 文档分片（内容、顺序、Chroma ID 关联） |
| `chat_session` | 会话主信息（标题、摘要、状态、消息计数） |
| `chat_message` | 消息明细（角色、内容、顺序、Token 统计） |
| `session_summary_snapshot` | 摘要快照（版本管理、覆盖范围） |
| `rag_query_log` | RAG 检索日志（召回、分数、耗时、排障） |

### 交互流程

```text
用户请求
    │
    ▼
  网关 (/ais/**) ──→ tj-aigc-py (FastAPI, port 8094)
                            │
                    ┌───────┼───────┐
                    │       │       │
                    ▼       ▼       ▼
                 Agent   Chroma   MySQL
               (LLM编排)  (知识库)  (6张核心表)
                    │
            ┌───────┼───────┐
            │       │       │
            ▼       ▼       ▼
       course-  search-  trade-
       service  service  service
       (8086)   (8083)   (8088)
```

### 一次对话的完整流程

1. **接收请求** → 用户发送问题，携带会话 ID
2. **加载上下文** → 从 MySQL 查询历史消息和摘要
3. **RAG 检索** → 从 Chroma 知识库检索相关知识
4. **消息组装** → 拼装：系统 Prompt + 摘要 + 检索结果 + 历史 + 当前问题
5. **模型调用** → 调用大模型，模型可自主决定是否调用课程/下单工具
6. **工具执行** → 若模型调用了工具，执行并返回结果给模型
7. **最终回答** → 模型生成最终回答，SSE 真流式输出给用户
8. **持久化** → 用户消息和 AI 回答存入 `chat_message`，同时写入 `rag_query_log`
9. **摘要检查** → 如对话轮数达到阈值，自动生成摘要快照

---

## 模块结构

```
tj-aigc-py/
├─ app/api/               # HTTP 接口层（9 个路由）
│   ├─ chat.py            #   POST /chat/text 非流式问答
│   ├─ chat_stream.py     #   POST /chat（流式）, POST /chat/stop
│   ├─ session.py         #   POST /session, GET /session/hot
│   ├─ session_history.py #   GET /session/{id}, GET /session/history
│   └─ document.py        #   POST /document/import 文档导入
├─ app/clients/           # 微服务 HTTP 客户端（course/search/trade）
├─ app/core/              # 配置、鉴权、响应包装、Nacos
├─ app/domain/            # DTO/VO 模型（含 6 张表对应 VO）
├─ app/memory/            # Redis 运行态辅助（stop 标记）
├─ app/providers/         # LLM 和 Embedding 模型接入（可切换）
├─ app/rag/               # RAG 检索层
│   ├─ vector_retriever.py    # Chroma 向量检索
│   ├─ keyword_retriever.py   # 关键词检索（骨架）
│   └─ hybrid_retriever.py    # 多路融合检索（骨架）
├─ app/repositories/      # 数据访问层（6 个 Repository）
│   ├─ chat_session_repo.py
│   ├─ chat_message_repo.py
│   ├─ summary_snapshot_repo.py
│   ├─ knowledge_document_repo.py
│   ├─ knowledge_chunk_repo.py
│   └─ rag_query_log_repo.py
├─ app/services/          # 核心业务逻辑（8 个 Service）
│   ├─ chat_text_service.py   # 非流式问答
│   ├─ stream_chat_service.py # 流式聊天（SSE + stop + 摘要触发）
│   ├─ agent_service.py       # Agent 编排（RAG + Tool Calling）
│   ├─ session_service.py     # 会话管理
│   ├─ history_service.py     # 历史消息/会话查询
│   ├─ summary_service.py     # 摘要生成
│   ├─ prompt_service.py      # Prompt 管理
│   └─ document_service.py    # 文档导入（MySQL + Chroma 双写）
└─ app/tools/             # Tool Calling 工具
    ├─ course_tools.py    # 课程查询/推荐（5 个工具）
    └─ order_tools.py     # 预下单工具
```

---

## 设计原则

### 存储分层

| 数据 | 存储位置 | 作用 |
|------|----------|------|
| 完整对话消息 | MySQL（chat_message） | 永久存储，按 message_order 排序 |
| 会话元数据 | MySQL（chat_session） | 会话列表、标题、状态、消息计数 |
| 摘要快照 | MySQL（session_summary_snapshot） | 长上下文压缩、版本管理 |
| 文档元数据 | MySQL（knowledge_document） | 原始文档溯源、版本、状态 |
| 文档分片 | MySQL（knowledge_chunk） | 分片内容、Chroma ID 关联 |
| RAG 检索日志 | MySQL（rag_query_log） | 排障、效果分析 |
| 知识库向量 | Chroma（本地 persist） | 语义检索 |
| Stop 标记 | Redis | 运行时控制 |

### 关键设计决策

- **MySQL 是主存储**：完整消息、摘要、元数据以 MySQL 为主，Redis 不承担主存储职责
- **消息顺序**：通过 `message_order` 字段保证顺序，不依赖时间戳排序
- **摘要版本化**：`session_summary_snapshot` 保存历史摘要版本，`chat_session.summary` 存最新摘要用于快速读取
- **文档双写**：文档导入同时写 MySQL 元数据 + Chroma 向量库，通过 `chroma_doc_id` 双向关联；支持异常自动回滚（清理 Chroma → 删除分片 → 标记失败状态），文本内容 SHA256 哈希记录
- **模型可切换**：聊天模型与 Embedding 模型独立配置，不硬编码厂商

### 接口兼容

完全兼容天机学堂现有项目约定：

- 服务名 `aigc-service`，网关路由 `/ais/**`
- 所有现有接口签名不变
- 鉴权头 `user-info`、`token-info`、`requestId` 等保持一致
- 网关响应包装格式兼容

---

## API 接口列表

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/chat/text` | 非流式问答 | ✅ 已实现 |
| POST | `/chat` | 流式对话（SSE） | ✅ 已实现 |
| POST | `/chat/stop` | 停止生成 | ✅ 已实现 |
| POST | `/session` | 创建会话 | ✅ 已实现 |
| GET | `/session/hot` | 热门问题 | ✅ 已实现 |
| GET | `/session/{sessionId}` | 历史消息 | ✅ 已实现 |
| GET | `/session/history` | 历史会话列表 | ✅ 已实现 |
| POST | `/document/import` | 文本导入（三步架构：标准化→去重→入库） | ✅ 已实现 |
| POST | `/document/upload` | 文件上传导入（支持 UTF-8/GBK） | ✅ 已实现 |
| GET | `/health` | 健康检查 | ✅ 已实现 |

---

## 部署

### 环境要求

- Python 3.11+
- MySQL 8.0+（需先执行 `init_db.sql` 建 6 张表）
- Redis（`/chat` 流式聊天依赖 stop 标记；现已支持通过 `.env` 显式配置 Redis 连接，建议使用 Redis 6+/7+/8+；本地已验证 Redis 8.8.0 可用）
- Chroma（首次启动自动创建项目根目录 `chroma_db/` 目录）
- 兼容 OpenAI 接口的大模型（千问 / DeepSeek 等）

### 快速启动

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置 .env（模型 API Key、数据库连接、Redis 等）
cp .env.example .env
# 编辑 .env，至少填入 AIGC_DATABASE_URL、AIGC_CHAT_API_KEY、AIGC_EMBEDDING_API_KEY
# 如需显式配置 Redis，可填写 AIGC_REDIS_URL 或 AIGC_REDIS_HOST/AIGC_REDIS_PORT/AIGC_REDIS_DB

# 3. 初始化数据库（MySQL 中执行）
mysql -u root -p tj_aigc < init_db.sql

# 4. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8094 --reload
```

---

## 实现状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 核心接口（8 个） | ✅ 完整实现 | 兼容现有 Java 版接口契约 |
| MySQL 6 张表 Repository | ✅ 完整实现 | 含 CRUD、批量操作、索引 |
| 流式对话（SSE） | ✅ 完整实现 | 已改为真实流式输出，支持 stop 控制、摘要触发 |
| Agent 编排 | ✅ 已实现核心链路 | RAG 检索 + Tool Calling 已集成 |
| 课程/下单 Tool | ✅ 完整实现 | 5 个课程工具 + 1 个下单工具 |
| 文档入库 | ✅ 完整实现 | 三步架构：标准化→SHA256去重→MySQL+Chroma双写+事务回滚 |
| 文件上传 | ✅ 完整实现 | 支持 UTF-8/GBK 编码 txt 文件上传 |
| 长上下文摘要压缩 | ✅ 完整实现 | 自动阈值触发 + 版本管理 |
| 向量检索（Chroma） | ✅ 完整实现 | 语义检索 + Chroma ID 关联 |
| 关键词 / 混合检索 | ✅ 第一版已完成 | 已支持向量召回 + MySQL 关键词召回 + chunk_id 去重 + 加权融合排序 |
| RAG 检索日志写入 | ✅ 已接入 | 已在聊天流程中落 `rag_query_log`，关联 `session_id`、`message_id`、`retrieved_chunk_ids` |
| 本地前端联调 | ✅ 已跑通 | `tj-portal-src-master` 可通过 `/ais-local` 代理联通本地 Python 服务 |
| 语音输入输出 | ❌ 未开始 | 后续规划 |
| 多 Agent 路由分发 | ❌ 未开始 | 后续规划 |

---

## 后续规划

- 继续补充本地知识库文档，提升课程咨询场景下的回答覆盖度
- 工具调用失败时的对话降级策略继续优化（在无实时服务环境下优先基于知识库作答）
- 检索重排序（Reranker）提升 RAG 精度
- 语音输入输出支持
- 多 Agent 路由分发（咨询 Agent / 购买 Agent / 知识 Agent）
- 更多教育场景工具（课程评价查询、学习进度查询等）

---

## 附：原项目来源与联调说明

### 1. 原始项目代码与资料来源

当前 AI 模块改造依赖于天机学堂原始项目环境与功能设计，相关来源如下：

- **AI 课程与基础功能参考资料**：`https://www.yuque.com/zhangzhijun-91vgw/tianji-ai?#
  《天机学堂AI课程》` 访问密码：`yygg`

- **后端原始代码地址**：`https://gitee.com/zhijun.zhang/tjxt.git`
- **前端源码地址**：`https://gitee.com/zhijun.zhang/tj-portal-src.git`
- **虚拟机导入说明**：`https://www.yuque.com/zhangzhijun-91vgw/tianji-ai/mvize74vs7plbe7x`

### 2. 本项目当前改造范围说明

本仓库当前主要改造的是 **AI 模块**，包括：

- Python AI 微服务 `tj-aigc-py`
- AI 助手聊天链路
- RAG 检索与日志落库
- 与前端 AI 助手弹层的本地联调

也就是说，**当前与前端交互的重点主要是 AI 助手功能**。

### 3. 关于其他功能的说明

除 AI 助手相关功能外，天机学堂其他课程、交易、学习、管理端等完整能力，仍然依赖原始项目环境。如果要完整运行和验证原系统全部功能，通常仍需要：

1. 下载并运行原始后端源码
2. 按原说明导入并启动虚拟机环境
3. 按原项目配置启动网关、注册中心、相关微服务和前端资源

因此可以这样理解：

- **只体验和联调 AI 助手**：当前仓库 + 本地前端源码即可完成主要验证
- **体验完整天机学堂全量业务**：仍建议按原项目说明下载虚拟机和原始源码完整搭建环境

---

*天机学堂 AI 智能助手 — 让学习更智能*
