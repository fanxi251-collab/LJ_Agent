# scripts

脚本目录。后续用于初始化知识库、导入资料和运行 RAG 评测。

## 导入单个资料文件

```powershell
python scripts\import_document.py "data\uploaded\景区资料.md" --workspace "."
```

脚本会读取一个明确的资料文件，复制到 `data/uploaded/`，切片并写入 `qdrant_db/`。

## 生成游客分析快照

```powershell
python scripts\build_tourism_analytics_snapshot.py `
  --input "景点景区旅游数据行为分析数据.xlsx" `
  --output "data\tourism_analytics_snapshot.json"
```

脚本会校验17个必需字段并生成脱敏的年度固定统计快照。原始 Excel、游客昵称、游客 ID
和景点长正文不会进入 Git；快照生成失败时会保留上一次有效输出，避免管理端读取半成品。

## 刷新景点种子封面

```powershell
python scripts\refresh_attraction_seed_covers.py --workspace "."
```

把 `src/lingjing_ai/assets/attractions/seed-*.webp` 同步到本机已有 `data/attractions.db`。
本地库非空时不会自动重新播种；用本脚本即可，无需删除数据库。
