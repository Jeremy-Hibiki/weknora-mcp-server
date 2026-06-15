# WeKnora MCP Server 使用示例

本文档提供 WeKnora MCP Server 的使用示例。该服务器为**只读检索**服务器，仅暴露查询类工具，不提供创建、删除、更新及聊天等写操作。

## 基本使用

### 1. 启动服务器

```bash
# 推荐方式 - 使用主入口点
python main.py

# 启用详细日志
python main.py --verbose
```

### 2. 环境配置示例

```bash
# 设置环境变量
export WEKNORA_BASE_URL="http://localhost:8080/api/v1"
export WEKNORA_API_KEY="your_api_key_here"

# 或者在 .env 文件中设置
echo "WEKNORA_BASE_URL=http://localhost:8080/api/v1" > .env
echo "WEKNORA_API_KEY=your_api_key_here" >> .env
```

## MCP 工具使用示例

> 所有工具的返回均已剥离 `code`/`message` 协议包裹，直接返回业务数据（`data` 载荷）。

### 知识库发现

#### 列出知识库
```json
{
  "tool": "list_knowledge_bases",
  "arguments": {}
}
```

#### 获取知识库详情
```json
{
  "tool": "get_knowledge_base",
  "arguments": {
    "kb_id": "kb_123456"
  }
}
```

> `kb_id` 既支持 UUID，也支持知识库名称（如 `my-knowledge-base`），服务器会自动解析。

### 检索

#### 混合搜索
```json
{
  "tool": "hybrid_search",
  "arguments": {
    "kb_id": "kb_123456",
    "query": "如何使用API",
    "vector_threshold": 0.7,
    "keyword_threshold": 0.5,
    "match_count": 10
  }
}
```

#### 列出知识 / 获取知识详情
```json
{
  "tool": "list_knowledge",
  "arguments": {
    "kb_id": "kb_123456",
    "page": 1,
    "page_size": 20
  }
}
```
```json
{
  "tool": "get_knowledge",
  "arguments": {
    "knowledge_id": "know_789012"
  }
}
```\n\n### Wiki 检索

#### 搜索 Wiki 页面
```json
{
  "tool": "wiki_search",
  "arguments": {
    "kb_id": "kb_123456",
    "query": "用户认证",
    "limit": 10
  }
}
```

#### 读取 Wiki 页面
```json
{
  "tool": "wiki_read_page",
  "arguments": {
    "kb_id": "kb_123456",
    "slug": "concept/rag"
  }
}
```

#### 获取 Wiki 索引
```json
{
  "tool": "wiki_index_view",
  "arguments": {
    "kb_id": "kb_123456",
    "limit": 50
  }
}
```

## 完整工作流程示例

### 场景：检索并阅读知识库内容

```bash
# 1. 启动服务器
python main.py --verbose

# 2. 在 MCP 客户端中按以下步骤检索
```

#### 步骤 1: 发现可用的知识库
```json
{
  "tool": "list_knowledge_bases",
  "arguments": {}
}
```

#### 步骤 2: 在目标知识库中混合搜索
```json
{
  "tool": "hybrid_search",
  "arguments": {
    "kb_id": "API文档库",
    "query": "如何使用用户认证API？",
    "match_count": 5
  }
}
```

#### 步骤 3: 查看命中的知识
```json
{
  "tool": "get_knowledge",
  "arguments": {
    "knowledge_id": "搜索结果中的 knowledge_id"
  }
}
```

#### 步骤 4: 阅读 Wiki 中的结构化条目
```json
{
  "tool": "wiki_index_view",
  "arguments": {
    "kb_id": "API文档库"
  }
}
```
```json
{
  "tool": "wiki_read_page",
  "arguments": {
    "kb_id": "API文档库",
    "slug": "concept/authentication"
  }
}
```

## 错误处理示例

### 常见错误和解决方案

#### 1. 连接错误
```json
{
  "error": "Connection refused",
  "solution": "检查 WEKNORA_BASE_URL 是否正确，确认服务正在运行"
}
```

#### 2. 认证错误
```json
{
  "error": "Unauthorized",
  "solution": "检查 X-Api-Key 请求头（HTTP/SSE）或 WEKNORA_API_KEY 环境变量（stdio）是否正确"
}
```

#### 3. 资源不存在
```json
{
  "error": "Knowledge base not found",
  "solution": "确认知识库 ID 或名称是否正确，先用 list_knowledge_bases 查看可用知识库"
}
```

## 高级配置示例

### 自定义检索阈值
```json
{
  "tool": "hybrid_search",
  "arguments": {
    "kb_id": "kb_123456",
    "query": "搜索查询",
    "vector_threshold": 0.8,
    "keyword_threshold": 0.6,
    "match_count": 15
  }
}
```

## 性能优化建议

1. **合理设置搜索阈值**：较高的阈值提升精确度但减少结果数量，按场景平衡
2. **分页控制**：`list_*` 类工具使用 `page` / `page_size` 控制返回量
3. **名称解析**：`hybrid_search` 等支持直接传入知识库名称，免去手动查 UUID
4. **监控日志**：使用 `--verbose` 选项监控请求与性能指标

## 集成示例

### 与 Claude Desktop 集成
在 Claude Desktop 的配置文件中添加：
```json
{
  "mcpServers": {
    "weknora": {
      "command": "python",
      "args": ["path/to/main.py"],
      "env": {
        "WEKNORA_BASE_URL": "http://localhost:8080/api/v1",
        "WEKNORA_API_KEY": "your_api_key"
      }
    }
  }
}
```

项目仓库: https://github.com/NannaOlympicBroadcast/WeKnoraMCP

### 与其他 MCP 客户端集成
参考各客户端的文档，配置服务器启动命令和环境变量。

## 故障排除

如果遇到问题：
1. 运行 `python main.py --verbose` 查看详细日志
2. 检查 WeKnora 服务是否正常运行
3. 验证网络连接和防火墙设置
4. 确认 API Key 具有对应资源的只读权限
