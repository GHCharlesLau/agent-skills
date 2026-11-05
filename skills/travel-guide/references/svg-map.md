# SVG 行程示意图规范

> 目标：**要素绝不重叠**。这是用户最容易一眼看出的低级问题，必须用代码验证，不能靠肉眼。

---

## 1. 布局原则

- **画布先放大再排布**：起点用 `viewBox="0 0 820 940"`（竖向行程）或 `0 0 1100 620`（横向行程），给标签留空间
- **节点间距**：视觉半径 13–15px 的节点，圆心间距建议 ≥ 90px；同一小区域内两个节点（如"黄花镇"和"九龙镇"只差 3km）必须**手动拉开**
- **真实比例 vs 可读性**：允许适度压缩/拉伸，但**方向必须正确**（东→右、西→左、北→上、南→下）
- **区域标题**（"清远·阳山/英德"）放**顶部居中**，不要放左上角压住第一个节点标签
- **图例**放右上角，与北向箭头错开（北向箭头右边缘，图例左侧 40px 起）

---

## 2. 标签防重叠：四种手段（按优先级使用）

1. **引线外移**：节点标签用短引线引到空白区
   ```svg
   <line x1="183" y1="300" x2="195" y2="300" stroke="#c4bba6" stroke-width="1.5"/>
   <text x="198" y="296" font-size="14" font-weight="700">② 黄花镇 · 小赵州桥</text>
   <text x="198" y="311" font-size="10.5" fill="#6b6455">英西峰林精华徒步起点</text>
   ```
2. **上下错位**：一个标签在上、一个在下，中间留出节点圆的高度
3. **白描边衬底**（线压字时必用）：让文字压线也清晰
   ```svg
   <text ... stroke="#FBF6EA" stroke-width="4" paint-order="stroke">4h · 280km</text>
   ```
4. **Bezier 绕行**：两条路线交叉时改曲线，避免直穿节点标签

> 禁止：靠减小字号挤进去（手机上根本看不清）。

---

## 3. 距离标签

- 位置在**线段中点**，沿线段方向旋转（`transform="rotate(deg cx cy)"`）
- 文案格式统一：`{时长} · {里程}`，如 `4h · 280km`、`30min · 9km`
- 必须带 `paint-order: stroke` 白色衬底
- 数值必须与 OSRM 验证结果完全一致（一处改，全文同步）

---

## 4. 重叠检测（交付前必跑）

在浏览器里两两比较 `getBoundingClientRect()`，阈值 2px：

```javascript
const svg = document.querySelector('.svg-panel svg');
const sr = svg.getBoundingClientRect();
const texts = [...svg.querySelectorAll('text')].map(t => {
  const r = t.getBoundingClientRect();
  return { t: t.textContent.trim().slice(0,16),
           x: r.left - sr.left, y: r.top - sr.top, w: r.width, h: r.height };
});
let overlaps = [];
for (let a = 0; a < texts.length; a++)
  for (let b = a + 1; b < texts.length; b++) {
    const A = texts[a], B = texts[b];
    const ox = Math.min(A.x + A.w, B.x + B.w) - Math.max(A.x, B.x);
    const oy = Math.min(A.y + A.h, B.y + B.h) - Math.max(A.y, B.y);
    if (ox > 2 && oy > 2) overlaps.push([A.t, B.t, Math.round(ox), Math.round(oy)]);
  }
// 文字 vs 节点圆
const circles = [...svg.querySelectorAll('circle')].map(c => {
  const r = c.getBoundingClientRect();
  return { cx: r.left - sr.left + r.width/2, cy: r.top - sr.top + r.height/2, r: r.width/2 };
});
const circleHits = [];
for (const t of texts) for (const c of circles) {
  const ox = Math.min(t.x + t.w, c.cx + c.r) - Math.max(t.x, c.cx - c.r);
  const oy = Math.min(t.y + t.h, c.cy + c.r) - Math.max(t.y, c.cy - c.r);
  if (ox > 2 && oy > 2) circleHits.push([t.t, Math.round(ox), Math.round(oy)]);
}
return { overlaps, circleHits };
```

**通过标准：`overlaps` 与 `circleHits` 均为空数组。**
（注意：切换 tab 后要等 300ms 再测，隐藏状态下 `getBoundingClientRect()` 全是 0，会假通过）

---

## 5. 常见重叠成因速查

| 现象 | 原因 | 修法 |
|------|------|------|
| 两个节点标签互相压 | 两景点实际距离近，比例映射后重叠 | 手动拉开节点 + 引线外移 |
| 标签压路线线 | 标签放在节点正上/正下，路线穿过 | 引线侧移 + 白描边 |
| 区域标题压第一个节点 | 标题在左上角 | 标题移到顶部居中 |
| 图例压北向箭头 | 都在右上 | 图例左移，箭头右移 |
| 手机端全乱 | 只按桌面宽度排版 | `viewBox` + `max-width:560px;width:100%`，用相对单位 |
| 测出来 0 重叠但看着重叠 | 测的时候 tab 是隐藏的 | 先 click 切 tab，再等 300ms 测 |

---

## 6. 与路线串联图的关系

- 「行程串联图」用 HTML/CSS 做（自适应更好），「SVG 示意图」保持纯静态但精致
- 两者与 Leaflet 地图共用 `data-stop-id`，实现三视图联动
- SVG 的独立文件 `route.svg` 供 Markdown 引用，**内容必须与 HTML 内嵌版一致**（改一处改两处）
