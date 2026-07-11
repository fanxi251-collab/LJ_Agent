# scripts

脚本目录。后续用于初始化知识库、导入资料和运行 RAG 评测。

## 导入单个资料文件

```powershell
python scripts\import_document.py "data\uploaded\景区资料.md" --workspace "."
```

脚本会读取一个明确的资料文件，复制到 `data/uploaded/`，切片并写入 `qdrant_db/`。
