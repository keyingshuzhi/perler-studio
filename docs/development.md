# 本地开发

## 前置条件

- Python 3.11+（Docker 与 CI 使用 3.12）
- Node.js 22+ 与 npm
- Docker Compose v2（仅容器工作流需要）

## 首次安装

在仓库根目录执行：

```bash
make backend-install
make frontend-install
```

等价的手动命令为：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env

cd ../frontend
npm ci
```

不要把真实密钥写入受版本控制的文件。`backend/.env` 用于本地后端，根目录 `.env` 用于 Docker Compose 插值。

## 启动开发服务

终端一：

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

终端二：

```bash
cd frontend
npm run dev
```

- 前端：`http://localhost:5173`
- OpenAPI：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

开发环境的 `VITE_API_BASE_URL` 为 `/api/v1`；Vite 把 `/api` 和 `/media` 代理给本地后端。若要连接其它 API 地址，应同时考虑媒体同源代理，而不只是修改 API 基址。

## 验证

```bash
make test
make build
```

`make test` 包含：

- `ruff format --check app tests`
- `ruff check app tests`
- `pytest -q`
- `vitest run`

`make build` 运行 `vue-tsc --noEmit` 和 Vite 生产构建。与 CI 一致的独立命令是 `make backend-test` 与 `make frontend-test`。

## 本地数据

默认数据根目录为仓库的 `data/`：SQLite 保存用户、会话、资源归属、收藏和审核数据；图片、图纸、项目、版本、分享、导出和任务记录保存在同一目录下的文件中。

修改或清理数据前先备份：

```bash
sh deploy/scripts/backup-data.sh
```

脚本默认把压缩包写入根目录 `backups/`，也可把目标目录作为第一个参数传入。恢复时应在服务停止后整体恢复 `data/`，避免 SQLite 与文件资源归属不一致。

## 常见问题

- Compose 报 `AUTH_SECRET` 缺失：复制根目录 `.env.example` 为 `.env` 并替换密钥；Compose 默认是生产模式，会拒绝空值。
- Compose 后端无法读写 `data/`：核对 `.env` 中的 `DATA_UID` / `DATA_GID` 与宿主机目录所有者；使用 Colima 时还需确认项目目录已共享到虚拟机，详见[部署指南](deployment.md)。
- 本地后端找不到数据：确认从 `backend/` 启动，或把 `DATA_DIR`、`DATABASE_PATH` 改为绝对路径。
- 前端 API 正常但图片打不开：确认 `/media` 也被代理到后端，并检查登录 token 是否仍有效。
- 图纸保存返回 `409`：本地 revision 已落后；重新读取图纸并合并差异。
- 首次管理员无法登录：内置账号和初始密码均为 `admin`；登录后立即修改密码。
