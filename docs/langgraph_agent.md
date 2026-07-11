# LangGraph 智能体接入说明

当前时间：2026-07-09 Asia/Shanghai

## 作用

LangGraph 用作 Agent 编排层，负责多步骤流程、状态管理、条件分支和轻量反思。它不替代 RAG、Qdrant、Neo4j 或高德工具。

## 安装

在当前 conda 环境中执行：

```powershell
pip install langgraph
```

## 配置

默认仍使用旧执行器：

```yaml
AGENT_EXECUTOR_MODE: legacy
LANGGRAPH_MAX_LOOPS: 1
LANGGRAPH_REFLECTION_ENABLED: true
```

切换到 LangGraph：

```yaml
AGENT_EXECUTOR_MODE: langgraph
```

如果未安装 `langgraph` 且配置为 `langgraph`，项目启动时会提示安装依赖；配置为 `legacy` 时不受影响。

## 流程

LangGraph 执行器节点顺序为：

```text
prepare_context -> plan_tools -> route_tools -> run_tools -> merge_sources -> reflect -> generate_answer
```

第一版反思只做确定性检查：无资料命中时，在 `LANGGRAPH_MAX_LOOPS` 限制内换用候选问题或补充“详细资料”再次检索。

天气、城市级路线和地点查询会优先走高德工具快速通道，命中后跳过 RAG、KG 和文档检索，以减少无效模型与检索调用。
