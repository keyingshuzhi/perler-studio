# Perler Studio Frontend

Perler Studio 的 Vue 3 单页应用，覆盖图片转换、空白/模板/文字创作、Canvas 编辑、项目管理、生产规划、导出、客户确认和社区发布。

## 技术栈

- Vue 3.5、TypeScript 5.8、Vite 7
- Pinia 3、Vue Router 4、Axios
- 原生 Canvas 网格渲染
- Vitest、vue-tsc

## 本地运行

```bash
cd frontend
npm ci
npm run dev
```

开发服务器位于 `http://localhost:5173`。Vite 会把 `/api` 与 `/media` 代理到 `http://localhost:8000`，因此请同时启动后端。

可用脚本：

```bash
npm run dev       # 开发服务器
npm test          # Vitest 单次运行
npm run build     # vue-tsc 检查并生产构建
npm run preview   # 本地预览 dist/
```

## 页面

| 路径 | 页面 | 访问条件 |
| --- | --- | --- |
| `/` | 首页 | 公开 |
| `/auth` | 登录/注册 | 仅未登录 |
| `/gallery` | 审核通过的作品社区 | 公开 |
| `/p/:token` | 公开作品详情 | 公开 |
| `/share/:token` | 客户确认与批注 | 持有链接 |
| `/account` | 账户资料与密码 | 登录 |
| `/convert` | 图片转换工作台 | 登录 |
| `/create` | 空白、模板、文字创作 | 登录 |
| `/templates` | 社区模板与再创作入口 | 登录 |
| `/editor/:projectId` | 专业编辑器 | 登录且拥有项目 |
| `/projects` | 项目库 | 登录 |
| `/export/:projectId` | 导出中心 | 登录且拥有项目 |
| `/admin` | 用户与发布审核 | 管理员 |

路由守卫只负责交互体验；真正的鉴权和资源归属检查由后端执行。

## 代码结构

```text
frontend/src/
├── api/                    按资源拆分的 HTTP 客户端
├── assets/styles/          全局视觉样式
├── components/
│   ├── bead-editor/        Canvas、工具栏、图层、选区、生产与报价面板
│   ├── color-palette/      色卡、库存和质量报告
│   ├── conversion/         转换预览
│   ├── export-panel/       导出表单
│   └── image-upload/       上传与预处理
├── router/                 页面路由和登录/管理员守卫
├── stores/                 应用、认证、编辑器、色卡和项目状态
├── types/                  与 API 契约对应的 TypeScript 类型
├── utils/                  token、颜色、网格、统计和主题工具
└── views/                  页面级组件
```

## 编辑器

编辑器用单个 Canvas 批量绘制成品网格、草稿层、原图参考、坐标和选区，避免为每个格子创建 DOM。正式保存和导出只使用成品层；草稿层可以独立试色、清空或合并。

已实现工具和操作：

- 画笔、橡皮、吸管、油漆桶、矩形选择。
- 同色、连续区域和相似色智能选区。
- 批量填色、清除、复制/粘贴、上下左右移动、水平/垂直镜像和顺时针旋转。
- 撤销/重做、缩放、平移、网格/坐标/色号显示与悬停信息。
- 自动保存项目编辑器状态；图纸差异携带 `base_revision`，服务端以 `409` 拒绝过期版本。

快捷键：

| 按键 | 操作 |
| --- | --- |
| `B` / `E` / `I` / `F` / `V` | 画笔 / 橡皮 / 吸管 / 填充 / 选择 |
| `Ctrl/Cmd + S` | 保存 |
| `Ctrl/Cmd + Z` | 撤销 |
| `Ctrl/Cmd + Shift + Z` 或 `Ctrl/Cmd + Y` | 重做 |
| `Ctrl/Cmd + C/V` | 复制/粘贴选区 |
| `Alt + 方向键` | 移动选区 |
| `Delete` / `Backspace` | 清空选区 |
| `Esc` | 取消选区 |

## 状态与持久化

- `auth`：Bearer token、当前用户和管理员状态。token 保存在浏览器本地存储。
- `project`：项目列表、当前项目、版本与保存流程。
- `editor`：成品单元格、草稿、选择、历史记录、视口和工具状态。
- `palette`：当前色卡和颜色索引。
- 转换页库存按色卡保存在浏览器本地存储，并随生成请求提交；服务端图纸仍保存本次库存快照与报告。

## API 与媒体

唯一前端环境变量是：

```dotenv
VITE_API_BASE_URL=/api/v1
```

本地 Vite 可读取 `.env.development` / `.env.production`；Docker 构建上下文排除所有 `.env*` 文件。当前镜像使用 `src/api/http.ts` 中的同源 `/api/v1` 默认值，不需要把配置文件打包进静态站点。

`src/api/http.ts` 统一处理响应包装和 Bearer token。私有 `/media` URL 会附加当前访问令牌；公开分享和发布预览分别使用分享或发布 token。生产 Nginx 与本地 Vite 都代理 `/api` 和 `/media`，保持同源访问。

接口详情见[API 概览](../docs/api.md)，开发与构建要求见[本地开发](../docs/development.md)。

## 浏览器与性能边界

大型网格仍受 Canvas 绘制、历史快照和浏览器内存限制。后端允许的网格上限并不意味着所有设备都适合交互编辑到该上限；生产使用应先在目标设备验证网格尺寸、导出分辨率和自动保存体验。
