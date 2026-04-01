# 发布检查清单

## 正式发布前检查

### 代码质量 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 单元测试通过 | ✅ | 535 tests passed |
| 测试覆盖率 ≥ 85% | ✅ | 85% coverage |
| 代码格式化 | ✅ | black, isort |
| Linting | ✅ | ruff |
| 类型检查 | ⚠️ | mypy (部分通过，需补充类型注解) |
| 安全扫描 | ✅ | bandit (已修复关键问题) |

### 文档完整性 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| README.md | ✅ | 完整的项目介绍 |
| LICENSE | ✅ | MIT License |
| CHANGELOG.md | ✅ | 版本变更记录 |
| CONTRIBUTING.md | ✅ | 贡献指南 |
| SECURITY.md | ✅ | 安全策略文档 |
| docs/index.md | ✅ | 文档首页 |
| docs/security.md | ✅ | 安全架构文档 |
| docs/release-checklist.md | ✅ | 发布检查清单 |

### 项目配置 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| pyproject.toml | ✅ | 项目配置完整，含入口点 |
| Makefile | ✅ | 构建脚本 |
| mypy.ini | ✅ | 类型检查配置 |
| .gitignore | ✅ | Git 忽略规则 |
| .pre-commit-config.yaml | ✅ | 预提交钩子配置 |

### CI/CD 配置 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| .github/workflows/ci.yml | ✅ | CI 流程配置 |
| .github/dependabot.yml | ✅ | 依赖自动更新 |
| .github/release-drafter.yml | ✅ | Release 自动生成 |
| .github/CODEOWNERS | ✅ | 代码所有权定义 |

### GitHub 模板 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Bug Report 模板 | ✅ | .github/ISSUE_TEMPLATE/bug_report.md |
| Feature Request 模板 | ✅ | .github/ISSUE_TEMPLATE/feature_request.md |
| PR 模板 | ✅ | .github/PULL_REQUEST_TEMPLATE.md |

### 部署支持 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Dockerfile | ✅ | Docker 镜像构建 |
| docker-compose.yml | ✅ | Docker Compose 编排 |
| scripts/release.sh | ✅ | 发布脚本 |

### REST API ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| API 主应用 | ✅ | api/main.py |
| 健康检查端点 | ✅ | /health, /version, /config |
| Agent 路由 | ✅ | /agents/* |
| Tool 路由 | ✅ | /tools/* |
| Session 路由 | ✅ | /sessions/* |
| OpenAPI 文档 | ✅ | /docs, /redoc |

### CLI 入口点 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| CLI 主入口 | ✅ | copaw/cli.py |
| 版本命令 | ✅ | copaw version |
| 配置命令 | ✅ | copaw config |
| API 服务 | ✅ | copaw api |
| Shell 模式 | ✅ | copaw shell |

### 性能测试 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 基准测试 | ✅ | tests/benchmarks/test_performance.py |

### 安全检查 ✅

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 无敏感信息泄露 | ✅ | .gitignore 配置 |
| 安全模块测试 | ✅ | SecurityMonitor 测试通过 |
| 权限控制测试 | ✅ | PermissionManager 测试通过 |
| 沙箱隔离测试 | ✅ | SandboxIsolator 测试通过 |
| 命令执行安全 | ✅ | 已添加 SecurityMonitor 验证 |

---

## 发布步骤

### 1. 准备发布

```bash
# 确保在 main 分支
git checkout main
git pull origin main

# 运行所有检查
make all
```

### 2. 更新版本

```bash
# 更新版本号
# - pyproject.toml
# - config/default.yaml
# - CHANGELOG.md
```

### 3. 构建和测试

```bash
# 清理旧构建
make clean

# 构建
python -m build

# 检查构建产物
ls dist/
```

### 4. 发布到 PyPI

```bash
# 安装 twine
pip install twine

# 上传到 TestPyPI (测试)
twine upload --repository testpypi dist/*

# 上传到 PyPI
twine upload dist/*
```

### 5. 创建 GitHub Release

```bash
# 创建标签
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0

# 在 GitHub 上创建 Release
```

### 6. 发布 Docker 镜像

```bash
# 构建 Docker 镜像
docker build -t copaw-team/copaw-code:0.1.0 .
docker build -t copaw-team/copaw-code:latest .

# 推送到 Docker Hub
docker push copaw-team/copaw-code:0.1.0
docker push copaw-team/copaw-code:latest
```

---

## 发布后验证

```bash
# 验证 PyPI 安装
pip install copaw-code

# 验证命令
copaw --version

# 验证 Docker
docker run copaw-team/copaw-code:latest --version
```

---

## 版本号规则

遵循 [语义化版本](https://semver.org/):

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的功能新增
- **PATCH**: 向后兼容的问题修复

示例:
- `0.1.0` - 初始发布
- `0.1.1` - Bug 修复
- `0.2.0` - 新功能
- `1.0.0` - 正式版本