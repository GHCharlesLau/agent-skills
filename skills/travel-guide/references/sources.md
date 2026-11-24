# 信息源规范（Trip + 小红书/Rednote + 官方）

> 目标：价格有出处、体验有原帖、硬事实有官网。所有引用都要能回到「哪一天、哪个页面、几个人」。

## 1. 优先级

| 级别 | 来源 | 查什么 | 必须记录 |
|------|------|--------|----------|
| **P0** | **Trip.com** | 机票、酒店、接送、部分门票 | 查询日期、币种、人数 |
| **P0** | **小红书 / Rednote**（`agent-reach`） | 排队、闭馆、扒手、机位、真实体验 | 笔记 URL、标题、读取方式 |
| P1 | 官方运营方 / 场馆 | 时刻、票价、闭馆、预约规则 | 页面 + 核对日期 |
| P2 | OSM / Wikimedia / 官方地图 | 坐标、路线、图片 | WGS84 / GCJ-02 |

冲突裁决：

```
硬事实（时间/票价/闭馆）: 官方 > Trip > 小红书 > 博客
体验（排队/安全/机位）:     小红书 > 官方 > 博客
价格（机票/酒店）:          Trip > 官网 > 博客
```

## 2. Trip.com 机票

URL 模板：

```
https://www.trip.com/flights/showfarefirst
  ?dcity=hkg&acity=lis&ddate=2027-01-05&rdate=2027-01-16
  &triptype=rt&class=y&quantity=2&locale=en-US&curr=HKD
```

步骤：

1. 用真实浏览器打开（结果是 JS 渲染），等 `flights found` 与 `HK$` 出现，别用固定 sleep。
2. 读 `document.body.innerText`，从 `Cheapest` / `flights found` 起截取卡片。
3. 提取航司、起降时刻、总时长、转机点/时长、价格、`+1`。
4. 卡片未渲染时：滚动/切前台，或改 `quantity=1` 重新查询。

四个强制校验：

| 校验 | 方法 | 失败模式 |
|------|------|----------|
| 到达日 | `起飞当地时刻 + 总时长 - 时差` | 卡片写 `+1`，实际同日到 |
| 每人/总价 | `quantity=1` 与 `2` 对比，价格不变=每人 | 2 人总价写进人均预算 |
| 转机风险 | <2h 标红；同航站楼+行李直挂才可接受 | 1h35 转机需提示「别逛免税店」 |
| 分开购票 | 国际+境内至少 4h；行李重新托运 | 落地 11:50，转机 16:55 |

回程：结果页选中去程后才显示回程时刻。未确认前写「建议 13:00–16:00，以出票为准」，**不得编造**。

## 3. 小红书 / Rednote（agent-reach）

```bash
agent-reach doctor --json
opencli doctor
opencli xiaohongshu search "关键词" -f yaml
opencli xiaohongshu note "NOTE_URL" -f yaml
```

- OpenCLI 需要 Chrome 运行 + 扩展已连接；未连接先启动 Chrome 再试。
- 用带 `xsec_token` 的完整 URL，不能拿裸 note_id 去读。
- 每次操作间隔 2–3 秒，批量深翻会触发验证码。

登录墙三级降级：

```
L1  OpenCLI 原生搜索/读笔记
L2  AUTH_REQUIRED → handoff，请用户在小红书网页登录一次
L3  用户不登录 → 公开索引检索，标注「公开索引摘要，非站内直读」
```

公开索引：

```bash
curl.exe -s "https://r.jina.ai/https://html.duckduckgo.com/html/?q=site%3Axiaohongshu.com+关键词"
```

规则：

- 不编造内容；不复制大段原文；改写要点。
- 优先近 12 个月、有实拍、评论区有补充的笔记。
- 票价/时刻仍回官网复核。
- References 写清读取方式；用了 L3 必须披露。

## 4. 官方源清单

| 地区 | 交通 | 门票/场馆 |
|------|------|-----------|
| 西班牙 | Renfe、iryo、Ouigo、ALSA | 各教堂/王宫/博物馆官网 |
| 葡萄牙 | CP、ALSA、Rede Expressos | Parques de Sintra、Mosteiro dos Jerónimos、Torre de Belém |
| 欧洲其他 | 各国国铁（DB、SNCF、Trenitalia） | 场馆官网 |

## 5. 引用格式

```
- 航班：Trip.com，2026-11-22，HKD，2 人，HKG–LIS 2027-01-05/16。
- 火车：Renfe，2026-11-24；Barcelona–Madrid 621 km。
- 体验：小红书《标题》，URL，公开索引摘要（登录墙）。
```
