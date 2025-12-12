# Zai2API

Zai2API 是一个功能完整的 OpenAI 兼容 API 服务网关。它允许你管理 Discord Token，自动将其转换为 zai.is 的访问凭证，并提供标准的 OpenAI 接口供第三方客户端调用。

## ✨ 功能特性

*   **多 Token 管理**：支持批量添加、删除、禁用 Discord Token。
*   **自动保活**：后台调度器自动检测并刷新过期的 Zai Token，确保服务高可用。
*   **OpenAI 兼容**：提供 `/v1/chat/completions` 和 `/v1/models` 接口，可直接接入 NextChat, One API 等客户端。
*   **负载均衡**：API 请求会自动轮询使用当前活跃的 Token。
*   **WebUI 面板**：
    *   **Token 列表**：实时查看 Token 状态、剩余有效期、余额类型。
    *   **系统配置**：修改管理员密码、API Key、代理设置、错误重试策略等。
    *   **请求日志**：详细记录 API 调用的耗时、状态码和使用的 Token。
*   **Docker 部署**：提供 Dockerfile 和 docker-compose.yml，一键部署。

## 🚀 快速开始

### 方式一：Docker Compose 部署（推荐）

1.  克隆或下载本项目代码。
2.  确保已安装 Docker 和 Docker Compose。
3.  在项目根目录下运行：

```bash
docker-compose up -d
```

4.  服务启动后，访问 `http://localhost:5000` 进入管理后台。

### 方式二：源码部署

1.  确保已安装 Python 3.10+。
2.  安装依赖：

```bash
pip install -r requirements.txt
```

3.  启动服务：

```bash
python app.py
```

## ⚙️ 配置说明

### 默认账户
*   **管理后台地址**: `http://localhost:5000`
*   **默认用户名**: `admin`
*   **默认密码**: `admin`
*   **默认 API Key**: `sk-default-key`

*请首次登录后务必在“系统配置”中修改密码和 API Key。*

### 环境变量 (Docker)

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `DATABASE_URI` | `sqlite:////app/instance/zai2api.db` | 数据库连接字符串 |
| `SECRET_KEY` | `your-secret-key...` | Flask Session 密钥，建议修改 |
| `TZ` | `Asia/Shanghai` | 容器时区 |

## 🔌 API 调用

### 聊天补全 (Chat Completions)

**Endpoint**: `http://localhost:5000/v1/chat/completions`

**示例 (curl)**:

```bash
curl http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-default-key" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### 获取模型列表

**Endpoint**: `http://localhost:5000/v1/models`

## 🛠️ 管理面板功能

1.  **Token 管理**：
    *   点击“新增 Token”输入 Discord Token (Session Token)。
    *   系统会自动尝试获取 Zai Token。
    *   点击“一键刷新 ZaiToken”可强制刷新所有 Token。
2.  **系统配置**：
    *   设置代理（支持 HTTP/SOCKS5）以解决网络连接问题。
    *   调整“错误封禁阈值”和“错误重试次数”以优化稳定性。
    *   调整 Token 刷新间隔。
3.  **请求日志**：
    *   查看最近的 API 请求记录，便于排查问题。

## ⚠️ 免责声明

本项目仅供学习和研究使用。使用者应自行承担使用本工具产生的所有风险和责任。请遵守相关服务条款。

