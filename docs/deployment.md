# 部署

当前推荐单机部署方式是 Docker Compose：后端和前端各一个容器，`./data` 作为持久化数据卷。Compose 直接从 GHCR 拉取已发布镜像，不在部署主机编译源码；前端 Nginx 同源代理 `/api` 和 `/media` 到后端。本仓库的 GitHub Actions 发布 `linux/amd64` 与 `linux/arm64` 多架构镜像，拉取时 Docker 会自动选择与主机匹配的架构。

## Docker Compose

首次部署：

```bash
cp .env.example .env
# 编辑 .env，替换 AUTH_SECRET，设置 DATA_UID/DATA_GID，并确认 IMAGE_TAG
docker compose pull
docker compose up -d
docker compose ps
```

- Web 应用：`http://localhost:8080`
- API：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`

Compose 默认把后端设为 `APP_ENV=production`，并通过 `${AUTH_SECRET:?...}` 强制要求密钥。仓库提供的 `.env.example` 只是模板；其中的示例密钥不能用于公网环境。

默认 `IMAGE_TAG=0.3.1`，对应 Git 标签 `v0.3.1` 发布的镜像；GHCR 镜像标签不含前导 `v`。每个标签都是同时包含 amd64 与 arm64 的多架构清单，`docker-compose.yml` 不再固定 `platform`，由 Docker 按部署主机架构自动选择；如需强制单架构，可在 compose override 中为该服务显式设置 `platform`。升级时先将 `IMAGE_TAG` 改为目标发布版本，例如 `0.4.0`，再执行 `docker compose pull` 和 `docker compose up -d`。若 GHCR 软件包设为私有，请先执行 `docker login ghcr.io`。

`data/` 是宿主机绑定挂载，不属于镜像；根目录 `.env` 只由 Compose 读取并作为环境变量传给后端，不挂载为文件。后端以非 root 身份运行，部署前用 `stat` 或 `id -u` / `id -g` 核对数据目录所有者，并将对应数值写入 `.env` 的 `DATA_UID` / `DATA_GID`。Compose 禁止自动创建缺失的绑定源目录；但若虚拟机中已经存在同名空目录，仍须人工核对挂载内容。

在 macOS 上使用 Colima 时，必须先确认 Colima 虚拟机共享了项目所在目录（尤其是外置卷 `/Volumes/...`）。若未共享，容器看不到真正的 `data/`；请在 Colima 的挂载配置中加入项目目录并重启 Colima，然后在虚拟机或一次性容器内确认挂载内容，再启动业务服务。不要在未确认共享的情况下运行迁移或初始化。

## 生产检查清单

- 使用高熵、独立的 `AUTH_SECRET`，并保护根目录 `.env` 的读取权限。
- 首次登录内置管理员 `admin` 后立即修改默认密码 `admin`。
- 将 `CORS_ORIGINS` 限制为实际域名；不要保留不需要的开发来源。
- 在外层反向代理启用 HTTPS、请求体限制、登录和上传限流及安全响应头。
- 只让外层代理访问 8080；如无运维需要，不要向公网暴露后端 8000 端口。
- 持久化并定期备份整个 `data/`，同时测试恢复。
- 核对 `data/` 的绑定挂载确实指向宿主机目录且后端运行 UID/GID 有写权限。
- 对上传、网格和导出上限做容量验证；当前重型转换和导出在请求内同步运行。
- 如使用 `INITIAL_ADMIN_EMAILS` 引导额外管理员，完成初始化后从配置中移除。
- 升级旧文件数据时显式设置 `LEGACY_DATA_OWNER_EMAIL`，避免错误账户接管历史资源。

## 数据备份与升级

备份脚本会把整个 `data/` 打包：

```bash
sh deploy/scripts/backup-data.sh
docker compose pull
docker compose up -d
```

默认备份目录是仓库根目录 `backups/`，也可传入独立挂载盘：

```bash
sh deploy/scripts/backup-data.sh /srv/perler-backups
```

恢复时先停止服务，再整体恢复数据目录。不要单独恢复 `perler-studio.db`，否则文件资源与归属记录可能不一致。

## 反向代理与 TLS

容器内 Nginx 已处理 SPA 回退，并代理 `/api` 和 `/media`。服务器外层的 Caddy、Traefik 或 Nginx 只需把公网域名转发到 `127.0.0.1:8080`；Nginx 示例位于 `deploy/nginx/perler-studio.conf.example`。

真实域名、证书、私钥和生产环境变量不应提交到仓库。若部署在多代理之后，还应明确可信代理和客户端 IP 传递策略，再配置限流和审计。

## 发布镜像

推送 `v*` Git 标签或手动触发工作流会先运行前后端验证，再发布 `linux/amd64` 与 `linux/arm64` 镜像：

```text
ghcr.io/<owner>/perler-studio-backend:<version>
ghcr.io/<owner>/perler-studio-frontend:<version>
```

仓库必须允许 GitHub Actions 使用 `GITHUB_TOKEN` 写入 Packages。工作流发布完整语义版本、主次版本和提交 SHA 标签；生产部署优先固定完整版本或镜像 digest，避免使用浮动标签。根目录 `docker-compose.yml` 已直接引用 GHCR 的前后端镜像，并保留运行时 `environment`、`user` 与 `data` 绑定挂载；部署不需要源码目录中的 Dockerfile、前后端依赖或任何 `.env*` 文件进入镜像。

## 当前扩展限制

单机部署依赖一个共享数据目录，不能直接横向扩展多个后端副本。若需要多实例或长耗时任务隔离，应先把 SQLite/JSON 迁移到数据库、媒体迁移到对象存储，并接入任务队列；这些组件目前尚未集成。
