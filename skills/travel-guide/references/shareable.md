# 单文件分享版（自包含 HTML）

> 用户场景：攻略做好后**发给队友 / 换设备打开**。
> 事故：HTML 里写 `images/foo.jpg`，只发 HTML 过去 → 对方手机上一片空白。
> 目标：产出**一个 HTML 文件**，双击即看，图文完整，无需文件夹、无需联网。

---

## 1. 为什么必须单独做一版

| 依赖 | 只发 HTML 时的结果 |
|------|------------------|
| `images/*.jpg` 相对路径 | ❌ 图片全丢 |
| Pexels/Unsplash 远程 URL | ⚠️ 可能被墙/防盗链/过期 |
| CSS `background:url(远程图)` | ❌ 更容易被忽略（`<img>` 扫描不到） |
| Leaflet CDN / Google Fonts | ⚠️ 离线降级（可接受） |
| 地图瓦片 | ❌ 必须联网（不可内嵌，需提示） |

结论：**图片必须内嵌；地图给出离线提示；字体/CDN 允许降级。**

---

## 2. 一键打包

```bash
python scripts/build_shareable.py \
  --src "清远梅子坪-英西峰林自驾游攻略.html" \
  --out "清远梅子坪-英西峰林自驾游攻略-分享版.html"
```

脚本做的事：
1. 扫描 HTML 中**所有**远程 `http(s)` 图片（含 `?auto=compress...` 查询串）→ 下载
2. 扫描所有本地图片相对路径 → 读文件
3. 统一**高质量双三次重采样 + JPEG q82（progressive）**：
   - 正文图 `--max-width 900`
   - Hero/封面 `--hero-width 1400`（靠 token 或 CSS 上下文里的 `hero/cover/banner` 识别）
   - 只缩不放；压完比原图大则保留原图
4. 转 `data:image/jpeg;base64,...` 就地替换（同一路径多处引用会全部替换，包括 JS 里的弹窗缩略图）
5. 输出单文件 + 打印每张图的压缩明细和"未解析引用"清单

参数：
- `--quality 78` 想更小
- `--max-width 720` 手机分享极简版
- `--no-download` 不抓远程图（纯本地图源时用）

---

## 3. 体积预算

| 内容 | 经验值 |
|------|-------|
| 正文图 20 张 @900px q82 | 2.5–4 MB |
| Hero 1 张 @1400px | 0.15–0.3 MB |
| HTML/CSS/JS | < 0.15 MB |
| **合计** | **通常 3–7 MB**，微信/邮件无压力 |

超过 10MB 时：降到 `--max-width 720 --quality 76`，或减少画廊张数（每景点 2 张足够）。

---

## 4. 双版本交付（必须两个都留）

| 文件 | 用途 | 特点 |
|------|------|------|
| `{目的地}-自驾游攻略.html` | 本地编辑版 | 引用 `images/`，画质最好，方便改 |
| `{目的地}-自驾游攻略-分享版.html` | **发给别人** | 单文件、离线、跨设备 |

命名固定带 `-分享版` 后缀，Markdown 的"交付文件"章节里写清楚哪个用来发人。

---

## 5. Hero 背景图的坑（必查）

CSS 里的背景图不在 `document.images` 里，脚本按 `url(...)` 文本替换可以覆盖，但**必须验证**：

```javascript
getComputedStyle(document.querySelector('.hero-bg')).backgroundImage.startsWith('url("data:image')
```

如果 Hero 是 `background:url('https://images.pexels.com/...')`，要确认打包后变成 `data:image/jpeg;base64,...`。

---

## 6. 剩下的远程依赖与降级

| 依赖 | 离线表现 | 兜底 |
|------|---------|------|
| 地图瓦片 | 白底 + 标记 | 7 秒看门狗换源，全失败显示 `#mapOffline` 提示，引导看「行程示意图」 |
| Leaflet CDN | 地图不可用 | `typeof L === 'undefined'` 时输出友好文案 |
| Google Fonts | 回退系统字体 | `font-family` 里必须写中文回退栈（`"PingFang SC","Microsoft YaHei",sans-serif`） |

---

## 7. 分享版 QA（必跑）

- [ ] `document.images` 中 `naturalWidth === 0` 的数量 = 0（排除灯箱未设 src 的占位 `<img>`）
- [ ] 非瓦片图片全部 `src.startsWith('data:')`
- [ ] 页面内**无 http 图片引用残留**（瓦片模板 URL 除外）
- [ ] Hero 背景 `backgroundImage` 为 data URI
- [ ] 地图仍能出图 / 无网时显示离线提示
- [ ] 灯箱、清单、预算、日切换全部正常，控制台 0 error
- [ ] 文件大小 ≤ 10MB

检查"残留远程图片"：

```javascript
[...document.images].filter(i => /^https?:/.test(i.getAttribute('src') || '')).length  // 期望 0
```
