# HTML 页面规格（结构 + 交互 + 视觉）

> 交付物：`{目的地}-自驾游攻略.html`，单页、所有 CSS 内联、无构建步骤。
> 设计基调：**每份攻略都要有独立风格**，禁止模板感（用户对"一看就是模板"极敏感）。

---

## 1. 外部依赖白名单

只允许：

- Google Fonts（≤2 个：1 个展示字体 + 1 个正文字体），必须写中文回退栈
- Leaflet 1.9.x（`leaflet.css` + `leaflet.js` via unpkg）

其他一律内联。不要引入 UI 框架、图标库、图表库（图表用内联 SVG）。

---

## 2. 页面结构（顺序固定，缺一不可）

1. **Hero** — 全幅主图 + 渐变遮罩 + 眉标 + 主标题 + 副标题（日期/天数/出发地）+ 4 个关键数据（天数/打卡点/总里程/人均预算）+ 粘性导航
2. **路线总览** — 三重视图 tab：`行程串联` / `行程示意图` / `真实地图`
3. **逐日行程** — Day 切换 + 可展开卡片（**默认展开**，详见 §4）
4. **徒步路线详解**（有徒步时）— 概览徽章 + 分段路书 + 内联海拔剖面
5. **景点详情** — 卡片网格 + 画廊 + 灯箱 + 门票/亮点/时段/外链
6. **住宿推荐** — 按天分组卡片
7. **美食推荐** — 按地区分组
8. **预算估算** — 可勾选类别、实时重算
9. **出行贴士 + 行前清单** — 图标网格 + 可勾选（localStorage）
10. **参考资料** — 分类列出（含图片版权）
11. **页脚** — 结语 + 免责声明

---

## 3. 路线三重视图

### 3.1 行程串联图（默认视图）

```
[深圳] ──4h · 280km──▶ [①梅子坪古道] ──1h · 61km──▶ [③九龙镇]
```

- 站点 = 编号圆点（1/2/3…），按天配色
- 线段上标 `时长 · 里程`，数据必须与 OSRM 一致
- 站点下一行：一句话亮点
- 点击站点 → 高亮地图标记 + 滚动到对应景点卡片
- 移动端自动转纵向

### 3.2 SVG 行程示意图

见 `references/svg-map.md`（重点：0 重叠、引线偏移、白描边、坐标方向正确）。

### 3.3 Leaflet 真实地图

见 `references/maps.md`（重点：多源回退、看门狗、离线提示、GCJ-02 偏移）。

---

## 4. 交互规范

### 日切换（Day Stepper）
- 粘性导航内 `◀ Day N ▶` + 每日圆点
- 切换时：高亮当日卡片、路线只显示当日折线（其余淡化）、平滑滚动

### 逐日卡片
- **默认全部展开**（用户明确要求过；折叠只在内容极长时才考虑）
- 展开后显示：完整时间轴、车程明细、住宿、美食
- 标题可点击收起/展开；`open` 类名控制

### 三视图联动（核心）
- 统一 `data-stop-id` 绑定 串联图 / SVG / 地图标记 / 景点卡片
- hover → 其他视图同步高亮；click → 滚动定位 + 高亮

```javascript
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
function highlightStop(id) {
  $$('[data-stop-id]').forEach(n => n.classList.toggle('is-active', n.dataset.stopId === id));
}
function focusStop(id) {
  const card = document.querySelector(`.attraction-card[data-stop-id="${id}"]`);
  card?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  highlightStop(id);
  highlightMarker(id);
}
```

### 分类筛选
- chips：`全部 / 自然 / 人文 / 美食 / 夜景`
- 过滤卡片 + 同步地图标记显隐

### 互动预算
- 类别条形（油费/门票/住宿/餐饮/其他），点击勾选/取消
- 合计 + 人均实时重算；低于/接近/超出目标用颜色区分

### 行前清单
- 可勾选；`localStorage` 记忆（**必须 try/catch**，隐私模式会抛异常）

### 灯箱
- 点击画廊图 → 全屏；左右箭头切换（按当前景点分组）；ESC 关闭；点击遮罩关闭
- 键盘 ←/→ 导航；`aria-modal="true"`

---

## 5. 图片画廊

- 每景点 1 张主图（16:9，≥800w）+ 2–4 张缩略图（4:3）
- `object-fit: cover` + `aspect-ratio` + 圆角，禁止变形
- `loading="lazy" decoding="async"`
- hover `transform: scale(1.06)` + 柔和阴影
- 图注：`景点 · 角度/时段 · 来源`
- 主图叠加时段徽章（日出/日落/夜景/季节）

---

## 6. 视觉要求（反模板）

- 先定一个**风格方向**再写 CSS：如"山野手账（米黄纸感 + 墨绿/赭石 + 手绘线）"、"暗色越野（炭黑 + 荧光橙 + 等宽字）"
- 用 CSS 变量集中管理：`--paper / --ink / --day1 / --day2 / --line`
- 标题字体可有个性（书法/衬线），正文保证可读（16–17px，行高 1.7）
- 装饰元素要克制：等高线底纹、细描边、编号、图钉，不用大色块渐变糊一脸
- 禁止：紫蓝渐变、Inter/Roboto 默认感、卡片一律白底圆角阴影、emoji 当图标

---

## 7. 响应式与打印

```css
@media (max-width: 760px){
  .day-stepper{ margin-left:0; width:100%; justify-content:flex-start }
  .nav-links{ order:3; width:100% }
  .ac-info{ grid-template-columns:1fr }
}
@media print{
  nav, .filters, .view-tabs, .ac-links, .day-stepper, #lightbox{ display:none !important }
  .view-panel{ display:block !important }
  section{ break-inside:avoid; padding:1rem 0 }
  body{ background:#fff }
  .day-card, .attraction-card, .budget-box, .simple-card, .tip, .checklist{ box-shadow:none }
}
```

打印时三视图要**全部展开**（`display:block`），否则只能打印到当前 tab。

---

## 8. JS 健壮性铁律

1. `localStorage` 所有读写包 try/catch（统一 `store` 工具对象）
2. 地图 / 清单 / 预算 / 灯箱 各自 try/catch 隔离，一个模块挂不拖垮全页
3. 所有 `querySelector` 结果判空（`?.`）
4. tab 切换后调用 `requestAnimationFrame(() => map.invalidateSize())`
5. 事件用委托，避免动态内容丢监听
6. 控制台必须 0 error（交付标准）
