# Perler Studio

专业拼豆图纸生成、编辑、统计、协作与打印平台。

Perler Studio 是一个可运行的前后端分离 Web 应用。创作者可以把照片或插画转换为真实品牌色号组成的拼豆网格，也可以从空白画布、内置模板或短文本开始创作；完成后可管理版本、生成生产计划、分享确认、提交社区审核，并导出制作文件。

当前版本为 `0.3.1`。项目统一使用语义化版本号，不再另设产品能力阶段版本。

## 当前能力

- 图片上传与预处理：PNG、JPEG、WebP；裁剪、旋转、亮度、对比度、饱和度、锐化和纯色背景移除。
- 图纸生成：`stretch`、`contain`、`cover`、原像素四种缩放方式，以及平滑、轮廓优先和自适应采样。
- 专业配色：MARD 291 屏幕参考色卡、RGB/CIE76/CIE94/CIEDE2000、自动限色、特殊色开关、禁用/锁定色和库存约束。
- 转换质量分析：ΔE00 平均值、P95、最大值、重点结构指标、色差热点和当前候选色卡的 Oracle 下界。
- 多种创作入口：图片转换、空白图纸、内置图案模板和短文本图案。
- Canvas 编辑器：画笔、橡皮、吸管、填充、矩形选择、复制粘贴、移动/镜像/旋转选区、智能选区、草稿层、撤销/重做和自动保存。
- 生产辅助：材料统计、库存缺口、替代色建议、底板拼接、分板制作顺序、工时与报价估算。
- 项目工作流：搜索、标签、收藏、复制、版本快照与恢复、客户分享确认和格子批注。
- 账户与发布：注册登录、资源归属隔离、管理员用户管理、作品审核、公开社区、收藏、继续编辑和再创作。
- 导出：PNG、PDF（单页、分页或制作说明书）、SVG、CSV 和 JSON 工程文件。

当前不包含 PostgreSQL、Redis、Celery、对象存储、邮件验证或第三方登录。这些属于后续部署演进，不是运行依赖。

## 快速开始

Docker Compose 会以生产模式启动后端，因此必须提供独立的 `AUTH_SECRET`：

```bash
cp .env.example .env
# 编辑 .env，将 AUTH_SECRET 改为长随机值，并将 DATA_UID/DATA_GID 设置为 data/ 的所有者
docker compose pull
docker compose up -d
```

启动后访问：

- Web 应用：`http://localhost:8080`
- OpenAPI 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

首次初始化会创建内置管理员 `admin`，初始密码也是 `admin`。第一次登录后必须立即修改密码。生产部署还应使用 HTTPS、限制管理端访问并在反向代理层配置限流。

完整步骤见[本地开发](docs/development.md)与[部署指南](docs/deployment.md)。GitHub Actions 发布 `linux/amd64` 与 `linux/arm64` 的 GHCR 镜像，并在推送前重新运行前后端验证。

## 典型工作流

1. 注册并登录。
2. 从图片、空白网格、模板或文字创建图纸。
3. 在转换页选择尺寸、色卡、质量目标和库存策略，先预览再生成。
4. 在编辑器修整成品层；需要试色时使用草稿层。
5. 保存项目，按需创建版本快照、分享给客户确认或提交社区审核。
6. 查看材料、底板和生产计划，导出 PNG/PDF/SVG/CSV/JSON。

所有私有创作接口都要求 Bearer token，并在服务端校验资源归属。公开分享页只暴露关联图纸的预览、确认与评论能力；公开社区只读取审核通过的固定快照。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、Axios、原生 Canvas |
| 后端 | Python、FastAPI、Pydantic、Pillow、NumPy、ReportLab |
| 数据 | SQLite 保存身份、会话、归属和审核；数据卷保存工程 JSON 与媒体文件 |
| 质量 | Pytest、Ruff、Vitest、vue-tsc、GitHub Actions |
| 部署 | Docker Compose、Nginx、GHCR `linux/amd64` / `linux/arm64` 镜像 |

## 仓库结构

```text
perler-studio/
├── backend/                 FastAPI 应用、色彩算法、存储和导出
├── frontend/                Vue 单页应用和 Canvas 编辑器
├── data/                    本地运行数据（不要提交业务数据）
├── deploy/                  Nginx 示例与数据备份脚本
├── docs/                    API、架构、开发、部署和色卡说明
├── .github/workflows/       测试与容器镜像发布
├── docker-compose.yml
└── Makefile
```

更细的模块边界见[后端说明](backend/README.md)、[前端说明](frontend/README.md)和[后端架构](docs/backend-architecture.md)。

## 配置

后端从环境变量读取配置。本地直接运行时会加载 `backend/.env`；Compose 从根目录 `.env` 插值并传入容器。

| 变量 | 默认/示例 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | Compose 默认覆盖为 `production` |
| `APP_VERSION` | `0.3.1` | 健康检查和 OpenAPI 中的版本 |
| `IMAGE_TAG` | `0.3.1` | 要拉取的 GHCR 镜像标签；发布标签去掉前导 `v` |
| `DATA_DIR` | `../data` | 后端目录的相对路径，或绝对路径 |
| `DATABASE_PATH` | `<DATA_DIR>/perler-studio.db` | SQLite 文件路径 |
| `DATA_UID/DATA_GID` | `1000/1000` | Compose 后端运行身份，应与宿主机 `data/` 目录所有者一致 |
| `AUTH_SECRET` | 仅开发默认值 | 生产环境必填，不能使用内置开发值 |
| `AUTH_SESSION_DAYS` | `30` | 登录会话有效天数 |
| `CORS_ORIGINS` | `http://localhost:5173` | 逗号分隔来源列表 |
| `MAX_UPLOAD_SIZE_MB` | `20` | 上传大小限制，允许 1–100 |
| `MAX_IMAGE_PIXELS` | `50000000` | 解码后的最大像素数 |
| `MAX_GRID_WIDTH/HEIGHT` | `500` | 服务运行时网格限制 |
| `DEFAULT_PALETTE` | `mard-291` | 默认色卡 |
| `INITIAL_ADMIN_EMAILS` | 空 | 可选的管理员引导邮箱列表 |
| `LEGACY_DATA_OWNER_EMAIL` | 空 | 生产升级时接管旧文件数据的指定邮箱 |

前端只读取 `VITE_API_BASE_URL`，开发与生产配置均为 `/api/v1`；Vite 和 Nginx 分别代理 `/api` 与 `/media`。Docker 构建排除前端 `.env*` 文件，镜像中的前端使用代码内置的 `/api/v1` 默认值。

`docker-compose.yml` 已传入运行环境、CORS、数据路径、上传限制和认证相关变量；未在 Compose `environment` 中列出的后端设置使用代码默认值。如需在容器中覆盖这些设置，应先把对应变量加入 Compose 服务定义。

## 数据与安全边界

- 密码使用 scrypt 派生哈希；数据库只保存会话令牌的 SHA-256 摘要。
- 用户、管理员权限和图片、图纸、项目、版本、色卡、导出的归属均由后端校验。
- 图片按实际内容、尺寸和像素数验证；服务器生成存储 ID，不接受客户端文件路径。
- SQLite 与 `uploads/`、`patterns/`、`projects/`、`versions/`、`shares/`、`exports/`、`tasks/` 必须作为一个数据集合备份。
- 内置 MARD 色卡是屏幕参考数据，不应被描述为实体批次测色。实体生产前请阅读[色卡与实体校色](docs/palettes.md)。

## 开发与验证

```bash
make backend-install
make frontend-install
make test
make build
```

`make test` 运行后端 Ruff/Pytest 和前端 Vitest；`make build` 运行 TypeScript 检查并生成 Vite 生产产物。CI 使用 Python 3.12 和 Node.js 22。

## 文档索引

- [本地开发](docs/development.md)
- [部署指南](docs/deployment.md)
- [API 概览](docs/api.md)
- [后端架构](docs/backend-architecture.md)
- [色卡与实体校色](docs/palettes.md)

## 许可证

仓库当前的 `LICENSE` 文件为空，尚未声明开源许可证。在许可证确定前，不应假定代码已获得复制、修改或再分发授权。
