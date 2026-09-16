# Perler Studio Backend

Perler Studio 的 FastAPI 后端，是账户权限、图纸网格、统计、版本、审核和导出的可信数据源。

当前版本为 `0.3.0`，使用本地文件和 SQLite，无需 PostgreSQL、Redis、Celery 或对象存储即可运行。

Docker 镜像只复制依赖清单和 `app/` 代码，不包含本地 `data/` 或 `.env*`。Compose 在运行时将宿主机 `./data` 绑定到 `/app/data`，并通过环境变量传入配置；后端运行 UID/GID 由 `DATA_UID` / `DATA_GID` 设置。

## 职责

- 校验、保存和预处理 PNG、JPEG、WebP 图片。
- 把图片采样为网格，并匹配系统或用户色卡。
- 创建空白、模板、文字和图片转换图纸。
- 对网格差异做乐观并发更新，重算统计与预览。
- 生成色差诊断、材料统计、底板拼接和制作计划。
- 管理项目、版本、客户分享、社区发布和审核。
- 生成 PNG、PDF、SVG、CSV 与 JSON 导出。
- 管理用户、scrypt 密码、会话、角色和资源归属。

## 技术栈

- Python 3.11+；Docker 与 CI 使用 Python 3.12
- FastAPI、Uvicorn、Pydantic v2
- Pillow、NumPy、ReportLab
- SQLite（Python 标准库）与文件系统 JSON/媒体存储
- Pytest、httpx、Ruff

## 代码结构

```text
backend/
├── app/
│   ├── api/v1/             HTTP 路由、认证依赖和响应状态
│   ├── core/               配置、异常、网格与底板预设
│   ├── palettes/           只读 MARD 色卡数据
│   ├── schemas/            Pydantic 请求与领域约束
│   ├── services/           转换、色彩、项目、生产和导出逻辑
│   └── main.py             应用工厂、异常包装、媒体鉴权和健康检查
├── tests/                  API 与服务测试
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

项目没有 ORM 模型层或 Alembic 迁移目录。SQLite 表由 `auth_service.py` 和 `publication_service.py` 初始化；工程主体仍以 JSON 与媒体文件保存。

## 本地运行

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`
- 健康检查：`http://localhost:8000/health`
- API 前缀：`/api/v1`

测试与静态检查：

```bash
.venv/bin/ruff format --check app tests
.venv/bin/ruff check app tests
.venv/bin/pytest -q
```

## 配置

`Settings` 定义在 `app/core/config.py`，直接运行时读取当前工作目录的 `.env`。路径相对于 `backend/` 解析。

| 变量 | 默认值 | 约束或用途 |
| --- | --- | --- |
| `APP_NAME` | `Perler Studio API` | OpenAPI 标题 |
| `APP_ENV` | `development` | `production` 会强制检查认证密钥 |
| `APP_DEBUG` | `false` | FastAPI debug 开关 |
| `APP_VERSION` | `0.3.0` | API 版本标识 |
| `API_V1_PREFIX` | `/api/v1` | 业务路由前缀 |
| `DATA_DIR` | `../data` | 文件数据根目录 |
| `DATABASE_PATH` | `<DATA_DIR>/perler-studio.db` | 可覆盖 SQLite 路径 |
| `MAX_UPLOAD_SIZE_MB` | `20` | 1–100 MB |
| `MAX_IMAGE_PIXELS` | `50000000` | 最少 1,000,000 |
| `MAX_GRID_WIDTH/HEIGHT` | `500` | 1–2,000；请求 Schema 还有独立上限 |
| `DEFAULT_PALETTE` | `mard-291` | 默认色卡 ID |
| `DEFAULT_DISTANCE_METHOD` | `ciede2000` | 默认匹配方式 |
| `DEFAULT_BEAD_SIZE_MM` | `5.0` | 默认豆径 |
| `DEFAULT_WASTE_RATE` | `0.05` | 默认损耗率 |
| `CORS_ORIGINS` | `http://localhost:5173` | 逗号分隔 |
| `AUTH_SECRET` | 开发专用值 | 生产环境必须覆盖 |
| `AUTH_SESSION_DAYS` | `30` | 1–365 天 |
| `INITIAL_ADMIN_EMAILS` | 空 | 逗号分隔的管理员引导邮箱 |
| `LEGACY_DATA_OWNER_EMAIL` | 空 | 指定旧文件数据接管账户 |

完整示例见 `.env.example`。不要提交真实密钥或生产 `.env`。

## 数据模型与存储

`Pattern` 以一维 `cells` 数组保存网格，索引为 `row * grid_width + column`；单元值是品牌色号或 `null`。图纸设置、统计和色彩报告随图纸保存。

```text
data/
├── perler-studio.db
├── uploads/{image_id}/
├── patterns/{pattern_id}.json + {pattern_id}.png
├── projects/{project_id}.json
├── versions/{project_id}/{version_id}.json
├── shares/{share_token}.json
├── exports/{export_id}.* + {export_id}.json
└── tasks/{task_id}.json
```

JSON 通过临时文件和原子替换写入。备份或迁移时必须整体处理 `data/`，不能只复制 SQLite 文件。

## 认证与响应

除公开作品列表/详情、分享链接和预设外，业务接口通常要求：

```http
Authorization: Bearer <access_token>
```

JSON 成功响应统一包装为：

```json
{"success": true, "data": {}, "message": null, "code": null}
```

错误响应使用同样的顶层字段并设置 `success: false`。`204 No Content` 与文件下载不使用 JSON 包装。完整路由见[API 概览](../docs/api.md)。

## 转换与色彩边界

默认转换使用 `adaptive` 采样、CIEDE2000 和 `medium` 清理。自动限色以作品生产颜色上限和 P95 ΔE00 目标共同决定色号集合；结构重点、禁用色、锁定色、特殊色开关与严格库存会改变候选和优化约束。

色卡的 `rgb`/`hex` 用于显示；存在合规 `calibration` 元数据时，`measured_lab` 优先用于匹配和质量评估。内置 MARD 291 仅是屏幕参考色卡。算法细节与实体校色格式见[后端架构](../docs/backend-architecture.md)和[色卡说明](../docs/palettes.md)。

## 当前扩展边界

`GET /api/v1/tasks/{task_id}` 已保留稳定任务读取契约，但当前转换与导出仍在同步请求内执行。未来可在不改变 Pattern 数据契约的前提下迁移到 PostgreSQL、S3/MinIO 和 Celery；这些组件目前不应写入安装或启动步骤。
