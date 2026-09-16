# API 概览

后端默认运行于 `http://localhost:8000`，业务前缀为 `/api/v1`。交互式 OpenAPI 文档位于 `/docs`，健康检查位于 `/health`。

本文列出当前实现的路由；请求字段和响应 Schema 以运行中的 OpenAPI 文档为最终准则。

## 认证与响应格式

需要登录的接口使用：

```http
Authorization: Bearer <access_token>
```

除 `204 No Content` 和文件下载外，成功响应统一为：

```json
{
  "success": true,
  "data": {},
  "message": null,
  "code": null
}
```

错误响应设置 `success: false`，并通过 `message`、`code` 和可选 `data` 描述错误。校验错误返回 `422`；资源版本冲突返回 `409`；缺少或无效登录返回 `401`；权限不足或资源归属不匹配由服务端拒绝。

## 路由清单

下表路径均省略 `/api/v1` 前缀。

### 账户与管理

| 方法 | 路径 | 访问 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | 公开 | 注册创作者账户 |
| `POST` | `/auth/login` | 公开 | 使用账号或邮箱与密码登录 |
| `GET` | `/auth/me` | 登录 | 当前账户 |
| `PATCH` | `/auth/me` | 登录 | 修改显示名称 |
| `PUT` | `/auth/me/password` | 登录 | 修改密码并注销全部会话 |
| `POST` | `/auth/logout` | 登录 | 注销当前会话 |
| `GET/POST` | `/admin/users` | 管理员 | 分页查询或创建用户 |
| `PATCH/DELETE` | `/admin/users/{user_id}` | 管理员 | 修改、停用并匿名化用户 |
| `PUT` | `/admin/users/{user_id}/password` | 管理员 | 重置密码并注销目标用户会话 |
| `GET` | `/admin/publications` | 管理员 | 兼容用审核列表 |
| `GET` | `/admin/publications/page` | 管理员 | 分页审核列表 |
| `GET` | `/admin/publications/{publication_id}` | 管理员 | 审核详情 |
| `POST` | `/admin/publications/{publication_id}/review` | 管理员 | 通过或驳回；通过需完成全部检查 |
| `DELETE` | `/admin/publications/{publication_id}` | 管理员 | 填写原因并下架作品 |

### 图片、预设与图纸

| 方法 | 路径 | 访问 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/images/upload` | 登录 | `multipart/form-data` 上传图片 |
| `GET` | `/images/{image_id}` | 所有者 | 图片元数据与媒体 URL |
| `POST` | `/images/preprocess` | 所有者 | 生成新的预处理图片资源 |
| `GET` | `/presets/grids` | 公开 | 网格尺寸预设 |
| `GET` | `/presets/templates` | 公开 | 内置图案模板 |
| `GET` | `/presets/boards` | 公开 | 矩形底板模板 |
| `POST` | `/patterns/blank` | 登录 | 创建空白图纸 |
| `POST` | `/patterns/template` | 登录 | 从内置模板创建图纸 |
| `POST` | `/patterns/text` | 登录 | 从短文本创建图纸 |
| `POST` | `/patterns/preview` | 图片所有者 | 无落盘转换预览 |
| `POST` | `/patterns/generate` | 图片所有者 | 生成并持久化图纸 |
| `POST` | `/patterns/{pattern_id}/regenerate` | 图纸与图片所有者 | 原地重新生成并递增 revision |
| `GET` | `/patterns/{pattern_id}` | 所有者 | 获取图纸 |
| `PUT` | `/patterns/{pattern_id}` | 所有者 | 提交单元格差异 |
| `DELETE` | `/patterns/{pattern_id}` | 所有者 | 删除图纸 |
| `GET` | `/patterns/{pattern_id}/assembly-plan` | 所有者 | 自定义底板宽高与重叠的拼接计划 |
| `GET` | `/patterns/{pattern_id}/production-plan` | 所有者 | 底板模板、顺序、工时与物料计划 |

### 色卡、项目、版本与分享

| 方法 | 路径 | 访问 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/palettes` | 登录 | 系统色卡和当前用户色卡 |
| `GET` | `/palettes/{palette_id}` | 登录/所有者 | 获取色卡详情 |
| `POST` | `/palettes` | 登录 | 创建自定义色卡 |
| `PUT/DELETE` | `/palettes/{palette_id}` | 所有者 | 修改或删除自定义色卡；系统色卡只读 |
| `GET/POST` | `/projects` | 登录 | 当前用户项目列表或创建项目 |
| `GET` | `/projects/page` | 登录 | 搜索、标签、收藏和分页 |
| `GET/PUT/DELETE` | `/projects/{project_id}` | 所有者 | 获取、更新或删除项目 |
| `POST` | `/projects/{project_id}/duplicate` | 所有者 | 复制项目及图纸 |
| `GET/POST` | `/projects/{project_id}/versions` | 所有者 | 列出或创建版本快照 |
| `GET` | `/projects/{project_id}/versions/{version_id}` | 所有者 | 获取版本 |
| `POST` | `/projects/{project_id}/versions/{version_id}/restore` | 所有者 | 恢复版本并更新项目引用 |
| `POST` | `/projects/{project_id}/shares` | 所有者 | 创建客户分享链接 |
| `GET` | `/shares/{token}` | 持有链接 | 获取分享快照和确认状态 |
| `POST` | `/shares/{token}/confirmation` | 持有链接 | 确认或要求修改 |
| `POST` | `/shares/{token}/comments` | 持有链接 | 添加整体或格子批注 |

### 社区发布

| 方法 | 路径 | 访问 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/projects/{project_id}/publications` | 所有者 | 提交固定图纸快照审核 |
| `GET` | `/publications` | 公开 | 搜索和分页浏览已审核作品 |
| `GET` | `/publications/{public_token}` | 公开 | 已审核作品详情 |
| `GET` | `/publications/mine` | 登录 | 兼容用个人发布列表 |
| `GET` | `/publications/mine/page` | 登录 | 分页个人发布记录 |
| `DELETE` | `/publications/{publication_id}` | 所有者 | 撤回发布 |
| `DELETE` | `/publications/{publication_id}/record` | 所有者 | 删除个人发布记录 |
| `POST` | `/publications/{publication_id}/resume` | 所有者 | 回到源项目或从快照恢复可编辑项目 |
| `GET` | `/publications/favorites/mine` | 登录 | 兼容用收藏列表 |
| `GET` | `/publications/favorites/mine/page` | 登录 | 搜索和分页收藏 |
| `GET` | `/publications/favorites/mine/tokens` | 登录 | 收藏作品 token 集合 |
| `POST/DELETE` | `/publications/{public_token}/favorite` | 登录 | 收藏或取消收藏 |
| `POST` | `/publications/{public_token}/remix` | 登录 | 复制公开快照为新图纸和项目 |

### 导出与任务

| 方法 | 路径 | 访问 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/exports/png` | 项目或图纸所有者 | 位图图纸 |
| `POST` | `/exports/pdf` | 项目或图纸所有者 | 单页、分页或制作说明书 PDF |
| `POST` | `/exports/svg` | 项目或图纸所有者 | 原生矢量图纸 |
| `POST` | `/exports/csv` | 项目或图纸所有者 | 材料统计 |
| `POST` | `/exports/project` | 项目或图纸所有者 | JSON 工程文件 |
| `GET` | `/exports/{export_id}` | 所有者 | 导出元数据 |
| `GET` | `/exports/{export_id}/download` | 所有者 | 下载文件 |
| `GET` | `/tasks/{task_id}` | 所有者 | 读取预留的异步任务契约 |

当前转换和导出同步执行；任务读取路由是未来启用 Celery 时的稳定契约，并不表示当前已经运行 Worker。

## 图纸生成关键字段

`POST /patterns/preview`、`/patterns/generate` 和 `/{id}/regenerate` 使用同一个请求模型：

- `resize_mode`：`stretch`、`contain`、`cover`、`pixel`。
- `sampling_mode`：`adaptive`（默认）、`edge_aware`、`smooth`。
- `distance_method`：`ciede2000`（默认）、`fidelity`、`rgb`、`cie76`、`cie94`。
- `max_colors` 与 `auto_color_limit`：颜色生产上限及是否按 `target_p95_delta_e_00` 提前停止。
- `cleanup_level`：`off`、`light`、`medium`（默认）。
- `include_special_colors`：默认 `false`；MARD 特殊材质色默认不进入自动匹配。
- `disabled_colors`、`locked_colors`：不能重叠。
- `inventory_mode`：`report` 或 `only`；严格库存至少需要一种正库存色号。
- `conversion_preset`：`custom`、`portrait`、`illustration`、`pixel_art`、`landscape`。
- `structure_aware`、焦点和细节优先级：用于确定性的结构重点保护，不代表语义识别。

响应的 `color_report` 会报告质量依据、实测覆盖率、ΔE00、清理调整、重点结构、库存缺口、替代建议和 Oracle 下界。详细含义见[色卡说明](palettes.md)。

## 差异更新与媒体

`PUT /patterns/{pattern_id}` 接收 `changes` 和可选 `base_revision`。每个差异包含单元索引、预期旧值 `before` 和新值 `after`。服务端在 revision 或旧值不匹配时返回 `409`，客户端应重新加载后合并，而不是覆盖远端状态。

媒体通过 `/media/{asset_path}` 提供，不属于 `/api/v1`。私有媒体要求 Bearer token 或 `access_token` 查询参数；分享和公开发布预览只接受与目标资源匹配的 `share_token` 或 `publication_token`。
