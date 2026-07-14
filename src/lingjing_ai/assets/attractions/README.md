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

## 同事拉代码后如何更新？

后端启动时会自动把 Git 中更新过的 seed 同步到运行目录，前提是该景点仍在使用默认的 `seed-*.webp` 封面。因此通常只需：

```bash
git pull
# 重启 uvicorn；如果使用 --reload，代码变化会触发自动重启
```

然后强制刷新游客端：http://127.0.0.1:8000/visitor/explore

管理员在后台上传过自定义封面后，后端不会用 seed 覆盖它。

### 强制恢复为仓库封面

在项目根目录执行：

```bash
python scripts/refresh_attraction_seed_covers.py --workspace .
```

该命令会把八个默认景点的当前封面恢复为仓库 seed，但保留景点数据和其他相册图片。

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
