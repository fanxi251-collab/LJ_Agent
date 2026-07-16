# LingJing AI 问答评测

评测集包含120个版本化用例，覆盖事实问答、景点解释、路线建议、地图工具、多轮对话、拒答安全和鲁棒性。默认评测不设置质量门禁，先用于建立可复现基线。

## 常用命令

在项目根目录执行：

```powershell
python scripts\evaluate_qa.py --mode validate
python scripts\evaluate_qa.py --mode offline
python scripts\evaluate_qa.py --mode benchmark
python scripts\evaluate_qa.py --mode benchmark --judge-llm
python scripts\evaluate_qa.py --mode smoke
```

- `validate` 只检查题库结构、证据和固定分布。
- `offline` 使用题库内固定答案和高德回放，完全离线验证评分及报告。
- `benchmark` 使用当前千问、Embedding、Qdrant和Neo4j，高德数据固定回放；运行前应停止占用本地Qdrant目录的后端进程。
- `smoke` 只执行8个 `online-smoke` 用例，并调用真实千问及高德接口。

可通过 `--case-id` 重复指定用例，或用 `--limit` 限制数量。`benchmark` 和 `smoke` 需要 `LJAPI_KEY`，`smoke` 还需要 `MAP_API`。

报告默认写入 `reports/qa_eval/`，该目录不会提交Git。首次完整 `benchmark` 会在本地生成 `baseline.json`，但不会因分数较低而阻断测试。

## 双重事实口径

`groundedness_score` 衡量答案是否符合本地知识资料；`freshness_score` 仅评价已通过官网核验且仍在30天有效期内的动态事实。票价、开放时间和演出安排过期后会显示为待重新核验，不继续作为现实正确答案。

修改题目定义后，使用下面的命令重新生成JSON并立即校验：

```powershell
python scripts\build_qa_eval_dataset.py
python scripts\evaluate_qa.py --mode validate
```
