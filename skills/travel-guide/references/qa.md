# 质检（QA Gate）

> 交付前**逐项跑完**，不通过不交付。每一条都要有可复现的检查手段，不靠"我觉得没问题"。

---

## A. 内容与数据

| # | 检查项 | 通过标准 |
|---|-------|---------|
| 1 | 里程来源 | 每段都来自 OSRM（`scripts/osrm_verify.py`），无估算 |
| 2 | 里程一致性 | 串联图 / SVG / 日程 / 汇总 / 预算五处数字完全一致（grep 全文） |
| 3 | 时间线 | 出发 + 车程 + 游玩 = 到达，逐日无矛盾 |
| 4 | 坐标 | 每个点有坐标表 + 来源；东→右、西→左、北→上、南→下 |
| 5 | 方位合理性 | 同地级市的两镇若相距 60km，图上不能贴在一起 |
| 6 | 徒步数据 | 分段累计连续；最高海拔与剖面一致；有撤退方案 |

---

## B. 图片

```javascript
// 1) 破图数量（应为 0）
[...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute('src')).length

// 2) 非 data 的图片（本地版允许相对路径；分享版应为 0 个 http）
[...document.images].filter(i => /^https?:/.test(i.getAttribute('src')||'')).map(i => i.src)

// 3) 缺 alt
[...document.images].filter(i => !i.getAttribute('alt')).length
```

- [ ] 破图 = 0
- [ ] 每张景点图肉眼确认与文字描述**对应**（不是"差不多"
- [ ] 每张图有图注 + 来源（B站标注 UP 主）
- [ ] Hero 背景图可用（`backgroundImage` 非空）

---

## C. 地图

```javascript
// 切到「真实地图」后等 3 秒
document.querySelectorAll('#map .leaflet-tile').length                                  // 应 > 0
[...document.querySelectorAll('#map .leaflet-tile')].filter(t => t.complete && t.naturalWidth > 0).length  // 应 ≥ 8
document.querySelectorAll('#map .leaflet-overlay-pane path').length                    // = 车程段 + 徒步段
document.getElementById('mapOffline').hidden                                          // 正常联网时应为 true
```

- [ ] 瓦片加载成功 ≥ 8
- [ ] 折线数量正确
- [ ] 手动切 5 个底图源都能出图（或显示提示）
- [ ] 点位方向正确

---

## D. SVG 示意图

```javascript
// 先点开「行程示意图」tab，等 300ms（隐藏状态测出来全是 0，会假通过）
```

跑 `references/svg-map.md` §4 的检测脚本：

- [ ] `overlaps` = `[]`
- [ ] `circleHits` = `[]`
- [ ] 距离标签有白描边（`paint-order: stroke`）
- [ ] `route.svg` 与内嵌版内容一致

---

## E. 交互

- [ ] Day 切换：高亮 + 滚动 + 折线过滤正常
- [ ] 逐日卡片：**默认展开**，点标题可收起
- [ ] 三视图联动：点串联图站点 → 滚到卡片；hover 地图标记 → SVG 节点高亮
- [ ] 筛选 chips 生效，地图标记同步
- [ ] 预算勾选后合计/人均实时变化
- [ ] 清单勾选后刷新页面仍保留（localStorage）
- [ ] 灯箱：打开/左右切换/ESC/遮罩关闭；图片加载正常
- [ ] 打印预览：三视图全部可见、交互控件隐藏

---

## F. 健壮性

```javascript
// 模拟 localStorage 被禁用
Object.defineProperty(window, 'localStorage', { get(){ throw new Error('blocked'); } });
// 刷新后：页面仍可用、控制台只有预期内的报错、地图不白屏
```

- [ ] 禁用 localStorage 后页面功能不回退（清单不记忆但不报错）
- [ ] 禁用网络后：图片正常（分享版）、地图显示离线提示、其余功能正常
- [ ] 控制台 **0 error**（警告可接受）
- [ ] 手机宽度（375px）无横向滚动条、文字不溢出

---

## G. 分享版

```bash
python scripts/build_shareable.py --src guide.html --out guide-分享版.html
```

- [ ] 脚本输出 `OK: no unresolved image reference left.`
- [ ] 文件 ≤ 10MB
- [ ] 浏览器打开：破图 = 0
- [ ] 所有图片 `src` 以 `data:` 开头
- [ ] 页面内无 `http` 图片引用（瓦片模板除外）
- [ ] Hero 背景是 data URI
- [ ] 地图 / 灯箱 / 预算 / 清单 全部正常
- [ ] 把文件单独拷到另一个目录（不带 `images/`）打开仍完整 —— **这是最关键的验证**

---

## H. Markdown

- [ ] 章节齐全（概览/路线/逐日/景点/住宿/美食/预算/贴士/交付文件/参考）
- [ ] 表格对齐、无断行
- [ ] 里程数字与 HTML 一致
- [ ] 「交付文件与分享方式」章节写明两个 HTML 的用途
- [ ] 图片来源与版权说明

---

## 常见故障速查

| 症状 | 大概率原因 | 修法 |
|------|-----------|------|
| 地图整块白 | 瓦片源被墙 / localStorage 抛异常中断脚本 | 多源 + 看门狗 + try/catch |
| 地图有标记无底图 | 瓦片 403/防盗链 | 换 Esri，检查 Referer |
| 地图点偏移 500m | 高德瓦片(GCJ-02) + WGS84 坐标 | 换 Esri 或做坐标转换 |
| 图片全裂（分享后） | 相对路径未内嵌 | 跑 `build_shareable.py` |
| Hero 图裂但正文正常 | Hero 是 CSS 背景，未被图片扫描覆盖 | 检查 `background:url(...)` 是否替换 |
| SVG 文字重叠 | 节点太近 / 标签压在线上 | 引线偏移 + 白描边 + 拉大间距 |
| 测重叠结果全 0 | tab 隐藏时测量 | 先切 tab 再等 300ms |
| 清单勾选不保存 | 隐私模式 localStorage 抛错 | try/catch + 内存兜底 |
| 打包后文件过大 | 原图未压缩 | `--max-width 720 --quality 76` |
| PowerShell 脚本中文乱码 | 脚本以 GBK 保存/解析 | 脚本纯 ASCII，路径走参数/环境变量 |
