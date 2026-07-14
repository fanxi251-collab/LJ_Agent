# 景点种子封面图

供首次启动 `AttractionStore` **仅在空库时**播种（复制到运行时目录 `data/attraction_images/`）。

| 文件 | 景点 |
|------|------|
| seed-1.webp | 灵山大照壁 |
| seed-2.webp | 五明桥 |
| seed-3.webp | 佛足坛 |
| seed-4.webp | 五智门 |
| seed-5.webp | 九龙灌浴 |
| seed-6.webp | 灵山大佛 |
| seed-7.webp | 灵山梵宫 |
| seed-8.webp | 五印坛城 |

## 同事拉代码后封面不更新？

播种逻辑是：`data/attractions.db` 里**没有任何景点**时才写入种子数据和封面。  
本地已经跑过服务 → 库非空 → **不会**自动覆盖你（或旧版）已有封面。这是刻意设计，避免把管理端手动上传的图冲掉。

### 推荐做法（不必删库）

在项目根目录执行：

```bash
python scripts/refresh_attraction_seed_covers.py --workspace .
```

然后强制刷新游客端：http://127.0.0.1:8000/visitor/explore

### 备选做法（整库重置）

仅在本地演示数据可以丢掉时：

```bash
rm -f data/attractions.db
rm -rf data/attraction_images
# 再启动 uvicorn，空库会重新播种
```

## 哪些目录不要提交 Git

| 路径 | 说明 |
|------|------|
| `src/lingjing_ai/assets/attractions/` | **要提交**（种子图） |
| `data/attraction_images/` | 运行时，已 gitignore |
| `data/attractions.db` | 运行时，已 gitignore |
| `frontend/data/` | 不是景点封面目录 |
