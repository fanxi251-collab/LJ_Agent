# Redis 缓存配置

当前时间：2026-07-09 Asia/Shanghai

## 安装依赖

在项目使用的 conda 环境中安装 Python Redis 客户端：

```powershell
python -m pip install redis
```

## 配置

当前项目从 `config.yml` 读取 Redis 配置：

```yaml
REDIS_ENABLED: true
REDIS_URL: redis://:523@localhost:6379/0
REDIS_CACHE_PREFIX: lingjing
REDIS_ANSWER_CACHE_TTL_SECONDS: 1800
REDIS_WEATHER_CACHE_TTL_SECONDS: 600
REDIS_ROUTE_CACHE_TTL_SECONDS: 1800
REDIS_PLACE_CACHE_TTL_SECONDS: 1800
```

## 缓存范围

- 问答缓存：相同知识版本、检索模式和问题命中缓存。
- 天气缓存：按城市缓存。
- 路线缓存：按起点、终点和出行方式缓存。
- 地点缓存：按关键词和城市缓存。

Redis 是性能增强层，不是强依赖。Redis 未安装或连接失败时，项目会自动退回内存缓存。
