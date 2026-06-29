-- ============================================================
-- 天机学堂 AI 智能助手 - MySQL 六张核心表 DDL
-- 数据库: tj_aigc
-- 设计依据: RAG项目_MySQL六张表设计文档.md
-- ============================================================

-- 1. 知识库文档主表
CREATE TABLE IF NOT EXISTS knowledge_document (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    doc_id VARCHAR(64) NOT NULL COMMENT '文档业务唯一标识',
    doc_name VARCHAR(255) NOT NULL COMMENT '文档名称',
    source_type VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '文档来源: pdf/word/web/excel/txt/manual',
    source_path VARCHAR(500) DEFAULT NULL COMMENT '原始文件路径或来源地址',
    version VARCHAR(32) NOT NULL DEFAULT '1.0' COMMENT '文档版本号',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '状态: 0待处理, 1已入库, 2禁用, 3删除',
    priority INT NOT NULL DEFAULT 0 COMMENT '文档优先级',
    file_hash VARCHAR(64) DEFAULT NULL COMMENT '文件内容哈希, 用于去重/变更检测',
    remark VARCHAR(500) DEFAULT NULL COMMENT '备注',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_doc_id (doc_id),
    KEY idx_status (status),
    KEY idx_source_type (source_type),
    KEY idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库文档主表';


-- 2. 文档分片表
CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    chunk_id VARCHAR(64) NOT NULL COMMENT '分片业务唯一标识',
    doc_id VARCHAR(64) NOT NULL COMMENT '所属文档ID, 关联 knowledge_document.doc_id',
    chunk_index INT NOT NULL COMMENT '文档内的分片顺序',
    chunk_text MEDIUMTEXT NOT NULL COMMENT '分片原文内容',
    token_count INT DEFAULT NULL COMMENT '分片Token数',
    content_hash VARCHAR(64) DEFAULT NULL COMMENT '分片文本哈希, 可用于去重',
    chroma_doc_id VARCHAR(128) DEFAULT NULL COMMENT 'Chroma中对应的向量记录ID',
    start_offset INT DEFAULT NULL COMMENT '原文起始偏移(可选)',
    end_offset INT DEFAULT NULL COMMENT '原文结束偏移(可选)',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1有效, 0无效',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_chunk_id (chunk_id),
    KEY idx_doc_id (doc_id),
    KEY idx_doc_chunk_index (doc_id, chunk_index),
    KEY idx_content_hash (content_hash),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档分片表';


-- 3. 会话主表
CREATE TABLE IF NOT EXISTS chat_session (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    session_id VARCHAR(64) NOT NULL COMMENT '会话唯一标识',
    user_id VARCHAR(64) NOT NULL COMMENT '用户ID',
    title VARCHAR(255) DEFAULT NULL COMMENT '会话标题',
    summary TEXT DEFAULT NULL COMMENT '当前最新摘要',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1进行中, 2已结束, 3归档',
    message_count INT NOT NULL DEFAULT 0 COMMENT '会话消息数',
    last_message_at DATETIME DEFAULT NULL COMMENT '最后发言时间',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    creater VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    updater VARCHAR(64) DEFAULT NULL COMMENT '更新人',
    UNIQUE KEY uk_session_id (session_id),
    KEY idx_user_id (user_id),
    KEY idx_last_message_at (last_message_at),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话主表';


-- 4. 消息明细表
CREATE TABLE IF NOT EXISTS chat_message (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    message_id VARCHAR(64) NOT NULL COMMENT '消息唯一标识',
    session_id VARCHAR(64) NOT NULL COMMENT '所属会话ID',
    user_id VARCHAR(64) NOT NULL COMMENT '用户ID',
    role VARCHAR(16) NOT NULL COMMENT '角色: user/assistant/system/tool',
    content LONGTEXT NOT NULL COMMENT '消息正文',
    params_json JSON DEFAULT NULL COMMENT '附加参数(JSON)',
    message_order INT NOT NULL DEFAULT 0 COMMENT '会话内消息顺序',
    token_count INT DEFAULT NULL COMMENT '消息Token数',
    input_tokens INT DEFAULT NULL COMMENT '输入Token数(可选)',
    output_tokens INT DEFAULT NULL COMMENT '输出Token数(可选)',
    model_name VARCHAR(64) DEFAULT NULL COMMENT '生成该消息所用模型',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1有效, 0删除',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_message_id (message_id),
    KEY idx_session_id (session_id),
    KEY idx_session_order (session_id, message_order),
    KEY idx_session_created (session_id, created_at),
    KEY idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息明细表';


-- 5. 摘要快照表
CREATE TABLE IF NOT EXISTS session_summary_snapshot (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    snapshot_id VARCHAR(64) NOT NULL COMMENT '摘要快照唯一标识',
    session_id VARCHAR(64) NOT NULL COMMENT '所属会话ID',
    summary_text TEXT NOT NULL COMMENT '摘要内容',
    message_count INT NOT NULL COMMENT '覆盖消息数量',
    version INT NOT NULL COMMENT '摘要版本号',
    start_message_id VARCHAR(64) DEFAULT NULL COMMENT '覆盖的起始消息ID',
    end_message_id VARCHAR(64) DEFAULT NULL COMMENT '覆盖的结束消息ID',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1有效, 0失效',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_snapshot_id (snapshot_id),
    KEY idx_session_id (session_id),
    KEY idx_session_version (session_id, version),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='摘要快照表';


-- 6. RAG 检索日志表
CREATE TABLE IF NOT EXISTS rag_query_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    query_log_id VARCHAR(64) NOT NULL COMMENT '日志唯一标识',
    session_id VARCHAR(64) NOT NULL COMMENT '所属会话ID',
    message_id VARCHAR(64) NOT NULL COMMENT '对应的用户消息ID',
    user_query TEXT NOT NULL COMMENT '用户原始问题',
    rewritten_query TEXT DEFAULT NULL COMMENT '查询改写后的问题',
    retrieved_chunk_ids JSON DEFAULT NULL COMMENT '召回chunk ID列表',
    retrieved_scores JSON DEFAULT NULL COMMENT '召回相似度分数列表',
    top_k INT DEFAULT NULL COMMENT '粗召回TopK',
    final_top_n INT DEFAULT NULL COMMENT '最终送入Prompt的片段数',
    prompt_snapshot LONGTEXT DEFAULT NULL COMMENT '最终Prompt快照(可选)',
    answer_text LONGTEXT DEFAULT NULL COMMENT '最终回答',
    retrieval_status TINYINT NOT NULL DEFAULT 1 COMMENT '检索状态: 1成功, 0失败',
    answer_status TINYINT NOT NULL DEFAULT 1 COMMENT '生成状态: 1成功, 0失败',
    latency_ms INT NOT NULL DEFAULT 0 COMMENT '本次总耗时(毫秒)',
    error_msg VARCHAR(1000) DEFAULT NULL COMMENT '异常信息',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_query_log_id (query_log_id),
    KEY idx_session_id (session_id),
    KEY idx_message_id (message_id),
    KEY idx_created_at (created_at),
    KEY idx_session_created (session_id, created_at),
    KEY idx_retrieval_status (retrieval_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RAG检索日志表';
