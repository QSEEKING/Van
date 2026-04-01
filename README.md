# CoPaw Code

> 一个类 Claude Code 的 AI 编码助手系统

[![CI](https://github.com/copaw-team/copaw-code/workflows/CI/badge.svg)](https://github.com/copaw-team/copaw-code/actions)
[![Coverage](https://codecov.io/gh/copaw-team/copaw-code/branch/main/graph/badge.svg)](https://codecov.io/gh/copaw-team/copaw-code)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)

## 特性

- 🤖 **智能代理引擎**: ReAct 循环实现，支持多步推理
- 🔧 **工具系统**: 文件操作、搜索、Shell 执行
- 🔒 **安全架构**: 多层安全防护，权限控制，沙箱隔离
- 💾 **存储系统**: 异步数据库，会话记忆，长期记忆
- 🖥️ **CLI 界面**: 交互式 REPL，斜杠命令，丰富格式化
- 🌐 **API 服务**: FastAPI REST API，支持远程调用

## 快速开始

### 安装

```bash
# 从源码安装
git clone https://github.com/copaw-team/copaw-code.git
cd copaw-code
pip install -e ".[dev]"
```

### 配置

```bash
# 设置 API Key
export ANTHROPIC_API_KEY=sk-ant-xxx
export OPENAI_API_KEY=sk-xxx

# 或使用配置文件
cp config/default.yaml config/local.yaml
# 编辑 local.yaml 设置你的配置
```

### 使用

```bash
# CLI 模式
copaw cli

# API 服务
copaw api

# 或直接使用 uvicorn
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
# 使用 Docker Compose
docker-compose up -d

# 仅 API 服务
docker-compose up copaw-api

# CLI 模式
docker-compose run copaw-cli
```

## 项目结构

```
copaw-code/
├── core/
│   ├── agent/          # 代理引擎
│   │   ├── main_agent.py       # 主代理 (ReAct)
│   │   ├── coordinator.py      # 协调器
│   │   └── sub_agents/         # 子代理
│   ├── llm/            # LLM 接口
│   │   ├── base.py             # 抽象基类
│   │   ├── anthropic.py        # Claude API
│   │   └── openai.py           # OpenAI API
│   └── config.py       # 全局配置
├── tools/              # 工具系统
│   ├── base.py                 # 工具基类
│   ├── file/                   # 文件操作
│   └── shell/                  # Shell 执行
├── security/          # 安全模块
│   ├── monitor/                # 安全监控
│   ├── permission/             # 权限管理
│   └── sandbox/                # 沙箱隔离
├── storage/          # 存储模块
│   ├── database.py             # 数据库
│   └── models.py               # 数据模型
├── cli/              # CLI 界面
│   ├── commands/               # 命令处理
│   └── formatter/              # 输出格式化
├── api/              # API 服务
│   └── main.py                 # FastAPI 应用
├── tests/            # 测试
│   └── unit/                   # 单元测试
├── config/           # 配置
│   └── default.yaml            # 默认配置
├── docs/             # 文档
├── .github/          # GitHub 配置
│   └ workflows/                # CI/CD
├── Dockerfile        # Docker 构建
├── docker-compose.yml # Docker Compose
├── Makefile          # 构建脚本
├── pyproject.toml    # 项目配置
├── LICENSE           # MIT 许可证
├── CHANGELOG.md      # 变更日志
└── CONTRIBUTING.md   # 贡献指南
```

## 开发

### 测试

```bash
# 运行测试
make test

# 覆盖率报告
make coverage

# 类型检查
make typecheck
```

### 代码质量

```bash
# 格式化
make format

#  linting
make lint

# 全部检查
make all
```

## API 使用示例

```python
from core.agent.main_agent import MainAgent
from core.llm.adapter import create_llm_provider
from tools import register_default_tools

# 初始化
llm = create_llm_provider()
agent = MainAgent(llm=llm, working_dir="/your/project")
register_default_tools()

# 执行请求
import asyncio

async def main():
    result = await agent.process("帮我查看当前目录的 Python 文件")
    print(result.content)

asyncio.run(main())
```

## 安全架构

CoPaw Code 实现多层安全防护：

- **SecurityMonitor**: 操作验证，路径检查，命令过滤
- **PermissionManager**: 角色权限控制
- **SandboxIsolator**: 沙箱隔离执行

详见 [docs/security.md](docs/security.md)。

## 文档

- [文档首页](docs/index.md)
- [安全架构](docs/security.md)
- [贡献指南](CONTRIBUTING.md)
- [变更日志](CHANGELOG.md)

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE)。

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 状态

| 模块 | 状态 | 覆盖率 |
|------|------|--------|
| Agent Engine | ✅ | 83% |
| LLM Interface | ✅ | 66% |
| Tool System | ✅ | 100% |
| Security | ✅ | 73% |
| Storage | ✅ | 100% |
| CLI | ✅ | 75% |
| **总计** | ✅ | **85%** |