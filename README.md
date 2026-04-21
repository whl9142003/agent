# CRM营业受理智能体

基于LangChain + MiniMax的CRM营业受理智能体，为电信运营商提供智能化的客户咨询和业务办理服务。

## 功能特性

- ✅ 客户身份认证（短信验证码/服务密码）
- ✅ 产品咨询与查询
- ✅ 个性化产品推荐
- ✅ 订单创建与支付
- ✅ 订单状态查询
- ✅ 敏感信息脱敏保护

## 项目结构

```
├── backend/                 # 后端服务
│   ├── api/                # API路由
│   ├── services/           # 业务服务
│   ├── models/             # 数据模型
│   ├── prompts/           # 提示词模板
│   ├── main.py            # 主应用入口
│   └── requirements.txt   # Python依赖
├── frontend/               # 前端页面
│   └── public/            # 静态资源
│       └── index.html     # 主页面
├── mock-api/              # Mock CRM API
│   └── server.py          # Mock API服务
├── start_mock_api.py      # 启动脚本
└── README.md              # 项目文档
```

## 快速开始

### 1. 环境要求

- Python 3.8+
- 网络环境（访问MiniMax API）

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt

cd ../mock-api
pip install fastapi uvicorn pydantic httpx
```

### 3. 配置环境变量

设置MiniMax API密钥：

```bash
# Windows
set MINIMAX_API_KEY=your_api_key

# Linux/Mac
export MINIMAX_API_KEY=your_api_key
```

### 4. 启动服务

#### 方式一：使用启动脚本

```bash
python start_mock_api.py
```

#### 方式二：手动启动

终端1 - 启动Mock CRM API：
```bash
python mock-api/server.py
```

终端2 - 启动主服务：
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 5. 访问系统

打开浏览器访问：http://localhost:8000

## 使用说明

### 身份认证

1. 输入手机号码（测试号码：13800000000）
2. 选择验证码登录（测试验证码：123456）
3. 认证成功后即可使用服务

### 功能操作

- **查询产品**: 输入"5G套餐"、"流量包"等关键词
- **产品推荐**: 输入"推荐"获取个性化推荐
- **查询订单**: 输入"订单"或"查询订单"
- **办理业务**: 选择产品后输入"订购"
- **支付**: 订单创建后输入"确认支付"

### 测试账号

| 手机号 | 账户余额 | 当前套餐 |
|--------|----------|----------|
| 13800000000 | 256元 | 5G畅享套餐 |
| 13900000000 | 500元 | 4G自由套餐 |

验证码统一为：`123456`

## API接口

### 认证接口

- `POST /api/auth/send-code` - 发送验证码
- `POST /api/auth/login` - 登录认证

### 产品接口

- `GET /api/products` - 获取产品列表
- `GET /api/products/{product_id}` - 获取产品详情
- `GET /api/products/recommend/{customer_id}` - 获取推荐

### 订单接口

- `POST /api/orders` - 创建订单
- `GET /api/orders/{customer_id}` - 获取订单列表
- `GET /api/orders/detail/{order_id}` - 获取订单详情

### 支付接口

- `POST /api/payment` - 处理支付

### 对话接口

- `POST /api/chat` - 发送对话消息
- `POST /api/session/create` - 创建会话
- `GET /api/session/{session_id}/status` - 获取会话状态

## 技术栈

- **后端**: FastAPI + LangChain + MiniMax
- **前端**: HTML5 + CSS3 + JavaScript
- **API**: RESTful
- **AI**: MiniMax-M2.1

## 注意事项

1. 本系统使用Mock API，实际使用时替换为真实CRM系统接口
2. MiniMax API密钥需要自行申请
3. 生产环境请配置HTTPS和Authentication
