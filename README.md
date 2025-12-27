# Zai2API

Zai2API 是一个功能完整的 OpenAI 兼容 API 服务网关。它允许你管理 Discord Token，自动将其转换为 zai.is 的访问凭证，并提供标准的 OpenAI 接口供第三方客户端调用。

## 功能特性

*   **多 Token 管理**：支持批量添加、删除、禁用 Discord Token。
*   **自动保活**：后台调度器自动检测并刷新过期的 Zai Token。
*   **OpenAI 兼容**：提供 `/v1/chat/completions` 和 `/v1/models` 接口。
*   **负载均衡**：API 请求会自动轮询使用当前活跃的 Token。
*   **WebUI 面板**：
    *   **Token 列表**：实时查看 Token 状态、剩余有效期。
    *   **系统配置**：修改管理员密码、API Key、代理设置、错误重试策略等。
    *   **请求日志**：详细记录 API 调用的耗时、状态码和使用的 Token。
*   **Docker 部署**：提供 Dockerfile 和 docker-compose.yml，一键部署。

## 项目结构

```text
/
├── core/               # 核心逻辑 (Models, Services, Extensions)
├── tests/              # 测试脚本
├── app.py              # API 主入口 (Port: 5003)
├── browser_server.py   # 浏览器自动化服务 (Port: 5005)
├── start.sh            # 一键启动脚本
└── ...
```

## 快速开始

### 1. 获取 Discord Token

随便在一个群组中发消息，复制其中的 Authorization 作为 Discord Token。
![获取discord token](png/获取doscordtoken.png)

### 2. 启动服务

**方式一：使用一键脚本 (推荐)**

本项目提供了一个智能启动脚本，会自动处理依赖安装和端口配置：

```bash
chmod +x start.sh
./start.sh
```

**方式二：Docker Compose 部署**

```bash
docker-compose up -d
```

### 3. 使用

服务启动后：

*   **管理面板**: `http://localhost:5003` (默认账号/密码: `admin` / `admin`)
*   **API 接口**: `http://localhost:5003/v1/chat/completions`

### API 调用示例

**Endpoint**: `http://localhost:5003/v1/chat/completions`

**curl**:

```bash
curl http://localhost:5003/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-default-key" \
  -d '{
    "model": "gemini-3-flash-preview",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

## 配置说明

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `DATABASE_URI` | `sqlite:///zai2api.db` | 数据库连接字符串 |
| `SECRET_KEY` | `your-secret-key...` | Flask Session 密钥，建议修改 |
| `BROWSER_SERVICE_URL` | `http://localhost:5005` | 浏览器服务地址 |

## 免责声明

本项目仅供逆向学习和研究使用。使用者应自行承担使用本工具产生的所有风险和责任。请遵守相关服务条款。