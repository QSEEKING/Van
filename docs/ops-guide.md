# 运维阶段指南

## 概述

项目已成功发布到 GitHub (QSEEKING/Van)，现在进入运维阶段。
运维阶段的核心目标是确保系统稳定运行、持续改进和快速响应问题。

---

## 运维阶段检查清单

### 1. 监控系统 ✅/❌

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 应用健康监控 | ❌ | 需配置 Prometheus/Grafana |
| 日志聚合 | ❌ | 需配置 ELK/Loki |
| 告警系统 | ❌ | 需配置 AlertManager |
| 性能监控 | ❌ | 需配置 APM (如 Jaeger) |

### 2. CI/CD 完善 ✅/❌

| 检查项 | 状态 | 说明 |
|--------|------|------|
| GitHub Actions | ⚠️ | Workflow 已移除，需重新添加 |
| 自动测试 | ✅ | pytest 配置完成 |
| 自动部署 | ❌ | 需配置部署流水线 |
| Docker 构建 | ❌ | 需配置自动构建推送 |

### 3. 环境管理 ✅/❌

| 环境 | 状态 | 说明 |
|------|------|------|
| 开发环境 | ✅ | 本地开发环境已配置 |
| 测试环境 | ❌ | 需搭建独立测试环境 |
| 生产环境 | ❌ | 需搭建生产服务器 |

### 4. 安全运维 ✅/❌

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 依赖漏洞扫描 | ⚠️ | Safety 配置待启用 |
| 秘密管理 | ❌ | 需配置 Secrets 管理 |
| SSL/TLS | ❌ | 需配置 HTTPS |
| 访问控制 | ✅ | 权限系统已实现 |

### 5. 数据管理 ✅/❌

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 数据库备份 | ❌ | 需配置自动备份 |
| 数据恢复 | ❌ | 需编写恢复流程 |
| 数据迁移 | ❌ | 需配置迁移脚本 |

---

## 运维工作流程

### 日常运维

```
┌─────────────────────────────────────────────────────────┐
│                    运维日常工作                           │
├─────────────────────────────────────────────────────────┤
│  09:00 - 检查系统健康状态                                │
│  10:00 - 查看日志和告警                                  │
│  12:00 - 处理用户反馈                                    │
│  14:00 - 代码审查和合并                                  │
│  16:00 - 性能分析和优化                                  │
│  18:00 - 每日总结和报告                                  │
└─────────────────────────────────────────────────────────┘
```

### 发布流程

```
┌─────────────────────────────────────────────────────────┐
│                    版本发布流程                          │
├─────────────────────────────────────────────────────────┤
│  1. 代码合并到 main 分支                                 │
│  2. 自动运行测试 (pytest)                                │
│  3. 构建 Docker 镜像                                     │
│  4. 部署到测试环境                                       │
│  5. 验证测试环境                                         │
│  6. 部署到生产环境                                       │
│  7. 监控生产环境                                         │
│  8. 创建发布标签                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 运维工具配置

### 1. Docker 部署

```bash
# 构建镜像
docker build -t qseeking/van:latest .

# 运行容器
docker run -d \
  --name van-api \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  qseeking/van:latest

# 使用 Docker Compose
docker-compose up -d
```

### 2. Kubernetes 部署 (可选)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: van-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: van-api
  template:
    metadata:
      labels:
        app: van-api
    spec:
      containers:
      - name: van-api
        image: qseeking/van:latest
        ports:
        - containerPort: 8000
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: van-secrets
              key: anthropic-api-key
```

### 3. 监控配置

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'van-api'
    static_configs:
      - targets: ['van-api:8000']
```

### 4. 日志配置

```python
# 在 core/config.py 中添加
class LoggingConfig:
    level: str = "INFO"
    format: str = "json"  # JSON 格式便于聚合
    output: str = "stdout"
```

---

## 运维命令速查

### 服务管理

```bash
# 启动服务
copaw-code api --host 0.0.0.0 --port 8000

# 或使用 Docker
docker-compose up -d

# 查看服务状态
curl http://localhost:8000/health

# 查看日志
docker-compose logs -f van-api
```

### 数据库管理

```bash
# 备份数据库
sqlite3 copaw.db ".backup copaw.db.bak"

# 或使用脚本
python scripts/backup_db.py

# 恢复数据库
cp copaw.db.bak copaw.db
```

### 性能调优

```bash
# 运行性能测试
python -m pytest tests/benchmarks/ -v

# 查看内存使用
docker stats van-api

# 分析慢请求
curl http://localhost:8000/metrics
```

---

## 运维阶段下一步

1. **完善 CI/CD** - 重新添加 GitHub Actions workflow
2. **搭建监控** - 配置 Prometheus + Grafana
3. **配置日志** - 添加结构化日志输出
4. **部署测试环境** - 搭建独立测试服务器
5. **安全加固** - 配置 HTTPS 和 Secrets 管理
6. **编写运维手册** - 详细操作文档

---

## 运维联系人

- **CTO**: aEqajC (架构决策)
- **Developer**: JhPSku (代码维护)
- **QA**: M6VzK2 (质量保证)
- **DevOps**: YaPoNj (运维部署)

---

*文档版本: 1.0*
*更新日期: 2026-04-01*