# 变更控制（日期 / 航班 / 城市改动）

> 用户中途改日期或航班时，不要局部修补；按「重新编号 + 重新打包」处理。
> 变更前先备份 HTML。

## 1. 重算

```
nights = 返程日 - 到达日
days   = nights + 1
```

例：1/5 到达、1/16 返程 → 11 晚、12 天。文件名、标题、chips、卡片数全部用 12。

## 2. 必须同步的 12 处

| # | 位置 | 检查 |
|---|------|------|
| 1 | `<title>` / `<h1>` / brand / footer | 「N 日」一致 |
| 2 | 文件名 | `{目的地}{N}日-旅行攻略.*` |
| 3 | 正文 / SVG / footer 日期 | 无旧日期残留 |
| 4 | Day 卡片与 `id="dayN"` | 连续、数量 = N |
| 5 | 导航 chips + JS `Math.min(N)` | 数量与上限 |
| 6 | 所有 `href="#dayN"` | 目标存在 |
| 7 | 串联图 `data-goto` | 指向正确 Day |
| 8 | 地图 `legs[].days` | 与日程一致 |
| 9 | 预算 | 晚数、天数、日游交通/门票 |
| 10 | 预订时间线 | 新日期对应的放票窗口 |
| 11 | 分享版 | 重新打包 |
| 12 | README / 交付表 | 文件名、天数、预算 |

## 3. 重编号

- 用**逆序替换**，避免级联：
  - `day9 → day11`
  - `day7 → day8`
  - `day6 → day7`
  - `day5 → day6`
- 同时替换 `href="#dayN"`、`data-goto="dayN"`、`data-day="N"`、`id="dayN"`。
- **可见标签**也要跟着走：`D5 行程` → `D6 行程`。只改 href 会出现「点 D5 跳到 Day 6」。

## 4. 变更后检查

```js
// 1) 失效锚点，期望 []
[...document.querySelectorAll('a[href^="#day"]')]
  .filter(a => !document.querySelector(a.getAttribute('href')))

// 2) 天数一致
({
  chips: document.querySelectorAll('#dayChips button').length,
  cards: document.querySelectorAll('.day-card').length,
  title: document.title
})

// 3) 旧日期残留（替换为旧日期）
document.body.innerText.includes('2027-01-08')
```

再跑一次 `references/qa.md`，并重新生成分享版、做干净目录测试。

## 5. 命名

- 自驾：`{目的地}-自驾游攻略.md/html/-分享版.html`
- 非自驾：`{目的地}{N}日-旅行攻略.md/html/-分享版.html`
- N = 实际天数，不是原计划；变更后必须重命名。
