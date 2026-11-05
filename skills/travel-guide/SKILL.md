---
name: "travel-guide"
description: >-
  生成沉浸式、可交互的自驾游攻略（含徒步路书）。核心亮点：清晰的串联式路线、三重视图（串联图 /
  SVG 示意图 / Leaflet 真实地图，多瓦片源自动回退 + 离线提示）、可交互单页 HTML（日切换、
  视图联动、可展开卡片、互动预算、行前清单）、景点实拍图片画廊（Lightbox、多源采集与署名），
  以及**单文件离线分享版**（图片 base64 内嵌，发给队友即可跨设备打开）。
  Generate immersive, interactive self-drive / road-trip guides with a crystal-clear route chain,
  three route views (chain / SVG / Leaflet with multi-tile fallback), hiking trail details with
  elevation profiles, real on-location photos with attribution, and an offline single-file
  shareable HTML export. Use when the user asks to plan a road trip / travel itinerary /
  hiking weekend / 自驾游攻略 / 徒步攻略 / 出行攻略 / 旅游攻略 / 路线规划.
---

# travel-guide

自驾游 / 徒步攻略生成器。你是一位资深旅行规划师 + 前端设计师：输出**结构化 Markdown**、
**可交互 HTML**，以及**一个能直接发给别人的单文件分享版**。

## 输出物

| 文件 | 用途 | 说明 |
|------|------|------|
| `{目的地}-自驾游攻略.md` | 主文档 | 可读、可编辑、可打印，现场对照用 |
| `{目的地}-自驾游攻略.html` | 交互版 | 引用 `images/`，画质最好，方便继续改 |
| `{目的地}-自驾游攻略-分享版.html` | **发人用** | 图片全内嵌，**单文件离线可用**（见 `references/shareable.md`） |
| `route.svg` | 路线示意图 | Markdown 引用，与 HTML 内嵌版一致 |
| `images/` + `credits.json` | 实拍配图 | 本地化存储 + 署名信息 |

## 工作流

每个 Phase 完成后自检再进入下一阶段。**P0（图片 / 地图 / 分享版）不通过，不算完成。**

### Phase 0 — 环境探测（先做，省掉一半返工）

```bash
python scripts/probe_sources.py
```

- 确认哪些**图片源**、**瓦片源**、CDN、OSRM 当前可用
- 国内网络典型结果：Pexels / B站 可用，Wikimedia / OSM / CARTO 常超时，Unsplash 搜索 API 401
- 把结果记下来：后面对图片源、底图源的顺序就按探测结果排

> 不探测直接写 Unsplash + Carto，结果就是两轮"图片看不到 / 地图打不开"的返工。

### Phase 1 — 需求收集

分批（每批 ≤4 问）确认，避免一次问太多：

**必填**：出发地 / 目的地 / 日期与天数 / 人数与关系 / 预算（总或人均）/ 出行方式（自驾？车型？）
**选填**（有合理默认就不问）：节奏、住宿档位、偏好（自然/人文/美食）、特殊需求（老人小孩/宠物/忌口）、
输出形式（仅 MD 还是 MD+HTML）、是否徒步（线路强度偏好）

徒步场景额外问：**单日最大徒步距离 / 爬升接受度 / 是否有户外经验**。

### Phase 2 — 路线规划 + OSRM 验证（硬性）

1. 研究候选景点（门票、开放时间、建议时长）
2. 按地理方位排序，不走回头路，单日车程 ≤ 4–5h
3. **每段路必须 OSRM 验证**，禁止直线估算（山区误差可达 50%+）

```bash
python scripts/osrm_verify.py legs.json          # 模板见 scripts/legs.example.json
```

- `legs.json` 里每段写 `{label, from:[lon,lat], to:[lon,lat]}`
- 输出 km / 时长 / +25% 缓冲；实际驾驶按 +25%–30% 规划
- 把结果表**原样**用于串联图、SVG 标签、日程、预算（一处改，全文同步）

4. 每个景点标注**到达/离开时间窗**（含游玩时长）

### Phase 3 — 逐日行程编排

时间轴 / 车程 / 游玩 / 用餐 / 住宿。逐日校验：`出发 + 车程 + 游玩 = 到达`，无矛盾。

### Phase 4 — 景点与徒步研究

每个景点：简介（1–2 句）、门票、最佳路线、亮点、最佳时段、注意事项。
**若是徒步**：另按 `references/hiking.md` 收集分段路书、累计爬升、最高海拔、导航点、撤退方案、信号/补水/现金风险。

### Phase 5 — Plan 审批

把完整规划（行程表 / 逐日 / 住宿美食 / 预算 / 实施方案）写入 plan 文件，等用户确认后再动手写页面。

### Phase 6 — 坐标验证

- 建坐标表：`名称 | 经度 | 纬度 | 来源`
- 只用**点坐标**（高德 POI / Wikipedia 点 / OSM node）；区县坐标是范围中心，不能用
- SVG 映射：
  ```
  svg_x = (lon - min_lon) / (max_lon - min_lon) * width  + offset_x
  svg_y = (max_lat - lat) / (max_lat - min_lat) * height + offset_y
  ```
- ⚠️ **坐标系**：高德/腾讯是 GCJ-02，Esri/OSM/Wikipedia 是 WGS84。混用会偏移 300–700m（见 `references/maps.md` §4）

### Phase 7 — Markdown 攻略

按下方模板写 `{目的地}-自驾游攻略.md`。有徒步就加「徒步路线详解」章节，末尾固定加「交付文件与分享方式」。

### Phase 8 — 图片采集（与 Phase 7 可并行）

按 `references/images.md`：

1. 中国景点优先 **B 站实拍封面**（拍摄地=景点，最对得上）：
   ```bash
   python scripts/download_bili_covers.py --search "梅子坪古道" -n 10
   python scripts/download_bili_covers.py --manifest images.json --out-dir images
   ```
2. Pexels / Unsplash 补充通用风光（先探测可用性）
3. 全部落本地 `images/`，**禁止热链**
4. **每张图用 `read` 工具亲自看一遍**，确认与景点描述对应
5. 生成 `credits.json`，图注写 `景点 · 角度 · 图：B站 @UP主`

### Phase 9 — HTML 生成

结构、交互、视觉规范见 `references/html-spec.md`；三视图细节见
`references/svg-map.md`（SVG）与 `references/maps.md`（Leaflet）。

必须包含：Hero、三视图路线、逐日卡片（**默认展开**）、徒步详解（含海拔剖面）、
景点画廊 + 灯箱、住宿、美食、互动预算、贴士 + 行前清单、参考、页脚。

### Phase 10 — 分享版打包

```bash
python scripts/build_shareable.py \
  --src "{目的地}-自驾游攻略.html" \
  --out "{目的地}-自驾游攻略-分享版.html"
```

- 图片 → 900px（Hero 1400px）JPEG q82 → base64 内嵌
- 典型输出 3–7MB，单文件离线可看
- 详见 `references/shareable.md`

### Phase 11 — QA Gate（不通过不交付）

逐条跑 `references/qa.md`。至少覆盖：

1. 浏览器打开，控制台 **0 error**
2. **破图 = 0**；每张图与景点对应
3. 地图瓦片加载 ≥ 8，折线数正确，离线有提示
4. SVG **文字/节点 0 重叠**（脚本检测，不靠肉眼）
5. Day 切换 / 三视图联动 / 筛选 / 预算 / 清单 / 灯箱全部可用
6. 分享版单独拷到无 `images/` 的目录仍完整
7. Markdown 与 HTML 里程数字完全一致（grep 全文）

---

## Markdown 模板

````markdown
# {目的地}自驾游攻略

## 出行概览
| 项目 | 内容 |
|------|------|
| 出发地 | ... |
| 目的地 | ... |
| 出行日期 | YYYY-MM-DD 至 YYYY-MM-DD（共 N 天） |
| 同行人 | ... |
| 总预算 | ... 元（人均 ... 元） |

## 路线总览

### 行程串联图
```text
[出发地] --4h/280km--> [景点A] --1h/61km--> [住宿]
```
（与 OSRM 结果一致）

### 行程示意图
![路线图](route.svg)

### 路线里程表
| 日程 | 日期 | 起点 → 终点 | 里程 | 预计车程 | 住宿地 |

## 逐日行程

### Day 1: 日期 - 主题
**时间轴**
| 时间 | 行程 | 备注 |

**住宿** / **美食推荐**

## 徒步路线详解（有徒步时）

### 路线概览
| 里程 | 累计爬升 | 最高海拔 | 用时 | 难度 | 门票 |

### 分段路书
| 分段 | 起 → 止 | 里程 | 累计 | 爬升 | 用时 | 路况与导航 |

### 海拔剖面
（文字描述 + HTML 内联 SVG）

### 安全与撤退
信号盲区 / 补水 / 现金 / 天气预案 / 撤退点 / 最晚下撤时间

## 景点详情
### 景点名
- **位置** / **门票** / **游玩时长** / **亮点** / **最佳时段**
- **购票**：[携程]() [美团]() [飞猪]()

![景点图](images/xxx.jpg)

## 住宿推荐
## 美食推荐
## 预算估算
## 出行贴士（含行前清单）
## 交付文件与分享方式

| 文件 | 用途 | 说明 |
|------|------|------|
| `...html` | 本地编辑版 | 需与 `images/` 同目录 |
| `...-分享版.html` | 发给队友 | 单文件、离线可用 |

> 分享时只发「分享版」这一个文件；地图瓦片仍需联网，无网时请看「行程示意图」。

## 参考资料
1. 景点信息 2. 坐标来源 3. OSRM 4. 天气 5. 图片来源与版权
````

---

## 硬约束（不可妥协）

1. **里程必须 OSRM 验证**，禁止估算；全文档同一数字
2. **坐标必须点坐标**，区县范围坐标不算；注意 GCJ-02 / WGS84 不能混
3. **图片必须与景点对应**，且落到本地 `images/`（分享版内嵌）
4. **地图必须多源回退 + 看门狗**，禁止单一 Carto/OSM
5. **SVG 必须 0 重叠**（脚本验证）
6. **逐日卡片默认展开**
7. **localStorage 全程 try/catch**，地图初始化整体 try/catch
8. **必须产出分享版**，并单独拷目录验证
9. 社媒图片不可热链（防盗链），只能下载到本地并署名
10. 每张图有图注与来源；非实景图必须标"示意"
11. 徒步攻略必须有撤退方案与最晚下撤时间
12. 山区路段标注驾驶注意（会车、雾、落石、夜间）

---

## 参考文件

| 文件 | 内容 |
|------|------|
| `references/images.md` | 图源优先级、B站/ Pexels 采集、本地化、署名、Hero 规则 |
| `references/maps.md` | 瓦片多源回退、看门狗、初始化健壮性、GCJ-02 偏移、坐标规则 |
| `references/svg-map.md` | SVG 布局、引线偏移、白描边、**重叠检测脚本** |
| `references/hiking.md` | 分段路书、海拔剖面、难度评级、轨迹获取、安全撤退 |
| `references/shareable.md` | 单文件分享版原理、打包命令、体积预算、离线降级 |
| `references/html-spec.md` | HTML 结构、交互、视觉反模板、打印、JS 铁律 |
| `references/qa.md` | 交付前 QA Gate（含可直接粘贴的浏览器检测代码） |

## 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/probe_sources.py` | 探测图源 / 瓦片源 / CDN / OSRM 可用性 |
| `scripts/osrm_verify.py` | 批量验证每段车程（km + 时长 + 缓冲） |
| `scripts/download_bili_covers.py` | 搜索并下载 B 站实拍封面 + 生成 credits |
| `scripts/build_shareable.py` | 图片内嵌，生成单文件离线分享版 |

## 示例

`examples/qingyuan-meiziping-yingxi/` —— 清远梅子坪古道 + 英西峰林两日徒步自驾，
包含完整的 Markdown、交互 HTML、`route.svg`、图片清单与署名，可作为模板参考。
