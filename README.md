# 知识点管理系统

基于 Flask 的轻量级知识库管理系统，支持知识点分类、标签管理、备份恢复、Markdown 渲染、移动端适配等功能。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python run.py
```

首次启动会自动进入配置向导，按提示设置密码、备份策略等选项。

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--password <pwd>` | 直接设置登录密码，跳过交互式向导 |
| `--debug` | 开启调试模式，输出完整错误堆栈 |
| `--reset-config` | 重置配置文件，重新运行首次配置向导 |
| `--show-config` | 显示当前配置并退出 |
| `--no-backup` | 本次启动跳过自动备份 |
| `--ssl-cert <path>` | 指定 SSL 证书文件路径 |
| `--ssl-key <path>` | 指定 SSL 私钥文件路径 |
| `--generate-cert` | 自动生成自签名证书（10 年有效期） |

## 功能特性

### 知识管理
- 知识点增删改查，支持分类和标签
- 拖拽知识点到侧边栏分类进行迁移
- 复制知识点（含标题、内容、分类、标签）
- 内容支持 Markdown 渲染（含图片）
- 分类删除时自动将知识点移入「未分类」

### 标签系统
- 自定义标签颜色，同名标签自动使用相同颜色
- 标签形状支持椭圆和矩形
- 按标签多选筛选知识点（OR 逻辑）
- 批量删除标签

### 数据安全
- 启动时自动备份数据库（可配置关闭）
- 手动创建/恢复/删除备份
- 备份恢复前自动保存当前数据库快照
- WAL 模式数据库，支持并发读写
- 操作日志记录，支持撤销操作

### 导入导出
- TXT 导出支持自定义字段（标题、内容、分类、标签）
- JSON 导入/导出，支持 AI 提示词模板
- 数据库自检修复

### 文件上传
- 支持上传图片（自动插入 Markdown 图片语法）
- 支持上传附件（任意文件，自动插入 Markdown 链接语法）
- 图片存储在 `static/uploads/images/`，附件存储在 `static/uploads/files/`

### 安全
- 登录认证，SHA256 密码哈希
- 24 小时会话有效期
- API 速率限制（登录 10 次/分钟，其他 60 次/分钟）
- 支持 HTTPS 加密传输
- 未认证访问自动重定向到登录页

### 移动端适配
- 响应式布局：单列 / 双列 / 多列
- 汉堡菜单，点击分类/遮罩层自动收起
- 触控按钮最小 44px，弹窗 95vw 自适应
- iOS 输入框 16px 防止自动缩放

### 系统设置
- 前端设置页面，可修改密码、启动备份策略、调试模式
- 配置写入 `config.json`，独立于数据库，即时生效

## 配置系统

配置文件 `config.json` 独立于数据库，**不随数据库重置而丢失**。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `password_hash` | 空 | SHA256 密码哈希 |
| `enable_startup_backup` | true | 启动时自动备份 |
| `debug` | false | 调试模式 |
| `host` | 0.0.0.0 | 监听地址 |
| `port` | 5000 | 监听端口 |
| `first_run` | true | 首次运行标志 |

## 项目结构

```
knowledge_base/
├── run.py                  # 应用入口
├── config.json             # 配置文件（独立于数据库）
├── requirements.txt        # 依赖
├── api/                    # API 路由层
│   ├── server.py           # Flask 应用创建、登录检查、速率限制
│   ├── auth_routes.py      # 认证接口（登录/登出）
│   ├── category_routes.py  # 分类 CRUD
│   ├── knowledge_routes.py # 知识点 CRUD
│   ├── tag_routes.py       # 标签管理
│   ├── backup_routes.py    # 备份管理
│   ├── operation_routes.py # 操作日志
│   └── log_routes.py       # 日志查看
├── services/               # 业务逻辑层
│   ├── backup_service.py   # 备份服务
│   ├── category_service.py # 分类服务
│   ├── knowledge_service.py# 知识点服务
│   ├── operation_service.py# 操作记录服务
│   └── tag_service.py      # 标签服务
├── models/                 # 数据模型层
│   ├── database.py         # 数据库连接管理（单例、WAL 模式）
│   ├── category.py         # 分类模型
│   ├── knowledge_point.py  # 知识点模型
│   ├── tag.py              # 标签模型
│   └── operation_log.py    # 操作日志模型
├── utils/                  # 工具模块
│   ├── config.py           # 配置管理、首次启动向导
│   ├── logger.py           # 日志模块（彩色输出）
│   └── repair.py           # 数据库自检修复
├── static/                 # 前端静态资源
│   ├── index.html          # 主页面
│   ├── login.html          # 登录页面
│   ├── css/style.css       # 样式
│   └── js/
│       ├── api.js          # API 调用封装
│       └── app.js          # 前端逻辑
├── backups/                # 数据库备份目录
└── logs/                   # 运行日志
```

## 依赖

- Python 3.8+
- Flask >= 2.0.0
- SQLite 3（内置）

附带依赖（已打包在 `lib/` 目录）：Werkzeug、Jinja2、Click、Blinker、ItsDangerous、MarkupSafe、Colorama