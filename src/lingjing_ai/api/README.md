# api

对外接口目录，用于放置 FastAPI 路由，让游客端和管理端调用 RAG、Agent 和实时数字人能力。

- `app.py`：应用装配、兼容的 HTTP/SSE 接口及会话接口。
- `realtime_routes.py`：`WS /api/visitor/realtime`，连接浏览器与 Qwen-Audio 实时会话。
- `attraction_routes.py`、`analytics_routes.py`：景点和分析接口。

实时协议与部署配置见 `docs/qwen_audio_realtime.md`。
