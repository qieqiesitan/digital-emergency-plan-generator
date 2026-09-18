# LLM 供应商故障注入 / 并发压测（零真实额度）

2026-09-19 补测「供应商侧超时、限流、流中断」与「并发（连接池/SSE）」时用的装置。
**全部走本地 Mock 供应商，不消耗任何真实模型额度**（唯一例外见最后一节）。

## 组件

| 文件 | 作用 |
| --- | --- |
| `mock_llm_server.py` | 假供应商：按请求体 `model` 名模拟故障 |
| `kill_mock.py` | 停掉容器里的 mock（容器内没有 `ps`/`pkill`） |
| `probe_client_faults.py` | 直接压 `llm_client` 层：429 退避/用尽、500、挂起超时、流截断、慢流 → **15 项断言** |
| `probe_ai_endpoints.py` | 18 个 AI 端点冒烟（用 `mock-json`），验证端点未被改坏 |
| `probe_pool_stress.py` | 并发压测：N 个聊天请求 + 每秒采样 `pg_stat_activity` + 同时打只读控制接口 |

## Mock 的故障模式（写在请求体的 `model` 字段）

| model | 行为 |
| --- | --- |
| `mock-ok` | 正常非流式 |
| `mock-ok-once-429` | 第一次 429，之后正常（验证退避重试） |
| `mock-429` / `mock-500` | 一直失败 |
| `mock-hang` | 挂起 600s（验证超时映射） |
| `mock-truncate` | 流式发 3 个分片后断开、不发 `[DONE]` |
| `mock-slow-stream` | 流式每片间隔 2s，共 5 片 |
| `mock-slow-nonstream` | 非流式但先睡 6s（并发压测用） |
| `mock-json` | 返回"字段齐全但为空"的 JSON（AI 端点冒烟用） |

## 用法（在 backend 容器内执行）

```bash
# 1) 起 mock（容器内）
docker cp backend/scripts/llm_fault_tests/mock_llm_server.py <容器>:/tmp/
docker exec -d <容器> sh -c "cd /tmp && nohup python mock_llm_server.py 18098 /tmp/mock_llm.jsonl > /tmp/mock.log 2>&1"

# 2) 客户端层 15 项断言（不需要改系统配置）
docker exec <容器> sh -c "cd /app && MOCK_BASE=http://127.0.0.1:18098/v1 python /tmp/probe_client_faults.py"

# 3) 需要走真实 HTTP 链路的（AI 端点冒烟 / 并发压测）：先把系统 AI 配置临时指向 mock
#    安全做法：把原系统配置降级（is_system=false），另插一行 is_system=true 指向 mock，
#    测完删除该行并还原原配置。具体 SQL 见本目录 probe 脚本头部的说明或 git 历史。

# 4) 停 mock
docker exec <容器> python /tmp/kill_mock.py
```

## 注意事项（踩过的坑）

1. **先指向 mock 再跑探针**：`probe_ai_endpoints.py` / `probe_pool_stress.py` 会真实调用系统 AI 配置，
   若此时配置指向线上供应商，就会消耗真实额度（本目录 2026-09-19 首次使用时因此消耗了 4 次 deepseek 调用）。
2. 后端 `docker restart` 会**连带杀死容器内的 mock**，重启后需要重新起 mock。
3. 并发压测依赖 DB 直连采样：`PG_DSN` 默认 `postgresql://postgres:postgres@postgres:5432/emergency_plan`。
4. `mock-hang` 的 600s 挂起会让探针等满超时；客户端层用 `payload_overrides={"max_retries": 0}` + 小 timeout 才快。
