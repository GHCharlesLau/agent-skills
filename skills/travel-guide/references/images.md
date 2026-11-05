# 图片来源与配图规范

> 核心原则：**图片必须与该景点的描述文字对应**。用户最容易反感的不是画质，而是"图上是一片雪山、文字写的是溶洞"。
> 图源"能连上"≠"图片对得上"，两道关口都要过。

---

## 1. 开工前：探测图源可用性

```bash
python scripts/probe_sources.py
```

输出会告诉你当前网络里哪些图源真的可用。典型结果（国内网络/Agent 沙箱）：

| 图源 | 常见状态 | 说明 |
|------|---------|------|
| Pexels CDN `images.pexels.com` | ✅ 稳定 | 只有 CDN 通，站点搜索页需用 webfetch 工具抓 |
| Unsplash CDN `images.unsplash.com` | ✅ 多半可用 | 搜索 API `napi` 常返回 **401** |
| Wikimedia `upload.wikimedia.org` | ❌ 常超时 | 国内网络经常不通 |
| Bilibili `api.bilibili.com` + `i0.hdslb.com` | ✅ 稳定 | **中国景点最可靠的实拍来源** |
| picsum.photos | ⚠️ 通但随机 | 只适合兜底，绝不能用来说明"这是某景点" |

**结论：中国境内景点，优先 B 站实拍封面；境外/通用风光用 Pexels；Unsplash/Wikimedia 仅备用。**

---

## 2. 图源优先级

```
① 本地实拍（用户提供 / 已下载到 images/）        —— 最真实
② B 站旅行 vlog 封面（拍摄地即景点本身）          —— 中国景点首选
③ Pexels / Unsplash（按英文关键词搜索）           —— 通用风光，必须核对是否像
④ Wikimedia Commons                              —— 国外景点、地标建筑
⑤ picsum（随机图）                                —— 仅占位，且必须标注"示意图"
```

### 判断 B 站封面是否"对得上"

- 标题含地名 + 「徒步 / 实拍 / 航拍 / vlog / 一日游」→ 可信度高
- 播放量 ≥ 1000、时长 ≥ 2min → 大概率是真实探访而非搬运
- 下载后**必须亲自看图**（用 read 工具读图，不要凭标题下结论）
- 一张图只能配一个景点，禁止"一张图复用到多个不相关景点"

---

## 3. B 站封面采集流程（推荐）

```bash
# 1) 找候选视频（无需登录，bili CLI）
python scripts/download_bili_covers.py --search "梅子坪古道" -n 10
python scripts/download_bili_covers.py --search "英西峰林 徒步" -n 10

# 2) 挑 BV 号写进 manifest（每景点 2-4 个不同镜头）
#    images.json:
#    [{"name":"meiziping-1","bv":"BV1ecrKB3Ezm"},
#     {"name":"meiziping-2","bv":"BV19Hz4B8EYM"}]

# 3) 批量下载封面 + 生成 credits.json（含标题/UP主/来源链接）
python scripts/download_bili_covers.py --manifest images.json --out-dir images
```

要点：
- Windows 控制台中文乱码时设 `$env:PYTHONIOENCODING="utf-8"`（或直接写文件看）
- B 站封面接口是 `api.bilibili.com/x/web-interface/view?bvid=`，返回的 `data.pic` 就是封面图
- 下载时带 `Referer: https://www.bilibili.com/`，否则可能 403
- **必须署名 UP 主**：图注写成 `图：B站 @UP主 · 视频标题`，页面"参考资料"里再统一说明
- 图片全部落到本地 `images/`，**不要热链**（防盗链 + 过期 + 跨设备失效）

---

## 4. Pexels 采集（CDN 可用时）

- 搜索页 `https://www.pexels.com/search/{keyword}/` 用 webfetch 工具抓（PowerShell 直连常被拦）
- 从页面里提取 `images.pexels.com/photos/{id}/pexels-photo-{id}.jpeg`
- 直接下载到 `images/`，不要只存远程 URL（分享会失效）
- 关键词用英文：`karst mountain`、`rice field`、`ancient bridge`、`tofu dish`

## 5. Unsplash 采集（备用）

- CDN 直链可用，但搜索 API 常 401 → 只能靠已知 photo id
- 只作补充，不要作为唯一图源

---

## 6. 图片落地与命名

```
images/
  meiziping-1.jpg     # 景点名-序号
  meiziping-2.jpg
  zhaozhou-1.jpg
  heshunyan-1.jpg
  yingxi-1.jpg        # 可作 Hero / 通用峰林
  jiulong-1.jpg       # 九龙镇街景
  credits.json        # 由脚本生成，含 title/author/url
```

规则：
- 命名 `{spot-slug}-{n}.jpg`，与 HTML 里的 `data-stop-id` 一致，便于排查
- 每张图 800–2000px 宽、单张 ≤ 2.5MB
- 保留原始文件；压缩在**打包分享版**时统一做（见 `shareable.md`），不要反复压原图（GDI+/System.Drawing 重编码曾把文件压成 0 字节）
- 用 `read` 工具直接看图确认内容，别只信文件名

---

## 7. 图注与署名（每张图都要有）

```html
<figure>
  <img src="images/meiziping-1.jpg" alt="梅子坪古道黑色石林与古道" loading="lazy" decoding="async">
  <figcaption>梅子坪古道 · 黑石林段 · 图：B站 @留了个白了</figcaption>
</figure>
```

- 图注格式：`{景点} · {拍摄角度/地段} · {来源}`
- 主图叠加**最佳观赏时段徽章**（日出 / 日落 / 夜景 / 季节限定）
- alt 必须描述画面内容（无障碍 + 图片加载失败时兜底）

---

## 8. Hero 主图规则

- Hero 用于**氛围**，不必与具体景点对应；用户通常更在意"好看"而不是"对应"
- 但正文景点图**必须对应**
- 建议 1600px 宽、横版、有留白（便于叠标题）、暗部不要太重
- Hero 若是远程 URL，**分享版必须单独内嵌**（CSS `url()` 里的图不会被 `img` 扫描到，要单独处理）

---

## 9. 交付前必查

- [ ] 浏览器实测：所有 `document.images` 中 `complete && naturalWidth===0` 的数量为 **0**
- [ ] 每张景点图肉眼确认与文字描述一致
- [ ] 每张图有图注 + 来源/UP 主
- [ ] 所有图在本地 `images/`（无 http 图片引用残留）
- [ ] 分享版（单文件）中图片全部为 `data:` URI
- [ ] 参考资料里有统一版权说明（"版权归原作者，仅作行程参考"）
