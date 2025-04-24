# 工作监控系统（Work Monitor System）

## 项目简介
本系统是一套面向企业或团队的工作监控与管理平台，包含客户端自动采集工作时长、屏幕截图、摄像头画面及应用进程信息，并定时上传至服务器。服务器端提供数据存储、用户管理、权限控制和可视化统计分析，支持管理员通过网页界面集中管理和查看所有用户的工作数据。

## 目录结构
```
project_root/
│
├── client/                # 客户端相关代码
│   ├── monitor.py         # 监控主程序，定时采集与本地保存
│   ├── auth_client.py     # 客户端API认证与上传逻辑
│   ├── auth_gui.py        # 客户端登录/注册GUI
│   ├── gui_monitor.py     # 客户端监控主界面GUI
│   └── monitoring_data/   # 客户端本地采集数据（自动生成）
│
├── server/                # 服务器端代码
│   ├── server.py          # Flask主服务，API与Web管理
│   ├── models.py          # SQLAlchemy数据模型
│   ├── create_admin.py    # 管理员用户创建脚本
│   ├── templates/         # Web管理界面HTML模板
│   └── uploads/           # 用户上传的文件（自动生成）
│
├── doc.md                 # 详细开发需求与设计文档
├── README.md              # 本说明文档
└── ...
```

## 系统架构说明
- **客户端**：定时采集本地工作时长、屏幕截图、摄像头画面、应用进程等，保存为本地JSON和图片文件，并通过API上传到服务器。
- **服务器端**：基于Flask，负责用户注册/登录、数据接收与存储、权限校验、统计分析、Web管理界面。
- **Web管理界面**：管理员可通过浏览器查看所有用户的工作时长、截图、摄像头画面、应用记录等，支持筛选、导出、批量操作。
- **数据库**：使用SQLite，存储用户、文件、工作时长等信息。

## 主要功能
### 客户端
- 用户注册、登录、认证（JWT）
- 定时采集：
  - 工作时长自动统计（区分工作日/周末）
  - 屏幕截图（PNG）、摄像头画面（WebP）
  - 活动应用进程列表（JSON）
- 本地数据存储与断点续传
- 支持GUI操作与状态显示
- 自动上传采集数据到服务器

### 服务器端
- 用户注册、登录、权限管理（普通用户/管理员）
- API接口：数据上传、查询、文件下载
- 数据库存储：用户、文件、工作时长、统计
- 管理员Web界面：
  - 仪表盘（用户数、记录数、文件数、服务器状态）
  - 用户管理（增删改查、权限分配）
  - 文件管理（筛选、预览、批量操作）
  - 工作时长统计（可视化、导出CSV）
- 权限控制：普通用户仅能访问自己的数据，管理员可管理所有数据

## 安装与运行
### 1. 环境准备
- Python 3.8+
- 推荐使用虚拟环境（venv）
- 依赖库：Flask、Flask-CORS、Flask-SQLAlchemy、Werkzeug、Pillow、opencv-python、psutil、requests、tkinter（GUI）等

### 2. 安装依赖
```bash
pip install flask flask-cors flask-sqlalchemy werkzeug pillow opencv-python psutil requests
```

### 3. 初始化数据库与管理员
```bash
cd server
python create_admin.py <管理员用户名> <密码>
```

### 4. 启动服务器
```bash
python server.py
# 默认监听 0.0.0.0:5000
```

### 5. 启动客户端
```bash
cd client
python auth_gui.py  # 图形界面
# 或
python monitor.py   # 命令行模式
```

## API接口简要说明
- `/api/register`  用户注册（POST）
- `/api/login`     用户登录（POST，返回JWT）
- `/api/upload/weekly_stats`  上传周工作时长（POST，需认证）
- `/api/upload/file`          上传文件（POST，需认证）
- `/api/stats/weekly`         查询本用户周统计（GET，需认证）
- `/api/admin/users`          管理员获取所有用户（GET，需认证+管理员）
- `/api/admin/stats/weekly`   管理员获取所有用户周统计（GET，需认证+管理员）
- `/api/files/<filename>`     下载文件（GET，需认证）

详细接口参数、返回格式见`server/server.py`和`doc.md`。

## 权限与安全
- 密码加密存储（Werkzeug）
- JWT认证，所有API需带Token
- 管理员/普通用户权限隔离
- 上传/下载建议使用HTTPS部署
- 数据库唯一性约束，防止重复数据
- 详见`doc.md`第6节安全性设计

## 常见问题
- **如何添加新管理员？**
  运行`python create_admin.py <用户名> <密码>`
- **客户端无法上传？**
  检查服务器地址、网络连通性、Token有效性
- **如何更换服务器端口？**
  修改`server.py`最后的`app.run`参数
- **数据存储在哪里？**
  - 服务器端：`server/uploads/`（文件）、`server/database.db`（数据库）
  - 客户端：`client/monitoring_data/`（本地缓存）

