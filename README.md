# WeKnora MCP Server

这是一个 Model Context Protocol (MCP) 服务器，提供对 WeKnora 知识管理 API 的访问。

## 快速开始

### 1. 安装依赖

```bash
uv sync --frozen --no-install-project --no-dev
```

### 2. 配置环境变量

```bash
# Linux/macOS
export WEKNORA_BASE_URL="http://localhost:8080/api/v1"

# Windows PowerShell
$env:WEKNORA_BASE_URL="http://localhost:8080/api/v1"

# Windows CMD
set WEKNORA_BASE_URL=http://localhost:8080/api/v1
```

## 安装为 Python 包

### 开发模式安装

```bash
pip install -e .
```

安装后可以使用命令行工具：

```bash
weknora-mcp-server
```

### 生产模式安装

```bash
pip install .
```

### 构建分发包

```bash
uv build
```

## 测试模组

运行测试脚本验证模组是否正常工作：

```bash
uv run pytest
```

## 功能特性

该 MCP 服务器为**只读检索**服务器，提供对 WeKnora 知识库的查询能力（共 8 个工具）。不提供创建、删除、更新及聊天等写操作。

### 知识库管理

- `list_knowledge_bases` - 列出知识库
- `get_knowledge_base` - 获取知识库详情
- `hybrid_search` - 混合搜索

### 知识管理

- `list_knowledge` - 列出知识
- `get_knowledge` - 获取知识详情

### Wiki 检索

- `wiki_search` - 搜索 Wiki 页面
- `wiki_read_page` - 读取 Wiki 页面
- `wiki_index_view` - 获取 Wiki 索引

## 调用效果

<img width="950" height="2063" alt="118d078426f42f3d4983c13386085d7f" src="https://github.com/user-attachments/assets/09111ec8-0489-415c-969d-aa3835778e14" />
