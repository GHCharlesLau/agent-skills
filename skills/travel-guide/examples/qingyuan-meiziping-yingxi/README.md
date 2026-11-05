# 示例：清远梅子坪古道 + 英西峰林（2 日徒步自驾）

深圳出发，5 人，2026-11-14 ~ 11-15，人均 ≈300 元。
Day 1 深圳 → 阳山江英镇·梅子坪古道（8–9km 环线，+300m）→ 英德九龙镇住宿；
Day 2 九龙镇 → 黄花镇·小赵州桥 → 和顺岩 → 观音谷 → 返深圳。总里程 ≈612km（OSRM 实测）。

## 文件

| 文件 | 说明 |
|------|------|
| `guide.md` | 完整 Markdown 攻略（含徒步路线详解章节、交付文件说明） |
| `guide.html` | 交互版 HTML（三视图 + 徒步卡片 + 画廊灯箱 + 互动预算 + 行前清单） |
| `route.svg` | SVG 行程示意图（0 重叠版式，节点引线外移） |
| `images/` | 17 张配图（**已降采样到 900px / q80，共约 1.8MB**，仅作演示） |
| `images.json` | 17 张配图的来源清单（`name` + B 站 `bv`） |
| `credits.json` | 每张图的标题 / UP 主 / 视频链接 |

> 示例里的图片为**压缩演示版**。真实交付请用原始封面（800–2000px），
> 分享时再交给 `build_shareable.py` 统一压缩内嵌。

## 复现原始图片

```bash
cd skills/travel-guide
python scripts/download_bili_covers.py \
  --manifest examples/qingyuan-meiziping-yingxi/images.json \
  --out-dir examples/qingyuan-meiziping-yingxi/images
```

需要 `bili` CLI（`bili --version` 可自检）。下载完成后重新打开 `guide.html` 即为原始画质。

## 复现分享版

```bash
cd skills/travel-guide/examples/qingyuan-meiziping-yingxi
python ../../scripts/build_shareable.py --src guide.html --out guide-分享版.html
```

输出约 5.8MB 单文件，图片全部 base64 内嵌，拷到任意设备双击可看。

## 这个例子演示了什么

| 技能点 | 位置 |
|--------|------|
| OSRM 逐段验证（280 / 61 / 9 / 262 km） | `guide.md` 路线里程表 |
| 三重视图（串联 / SVG / Leaflet） | `guide.html` 路线总览 |
| SVG 标签引线外移 + 白描边 + 0 重叠 | `route.svg`、`guide.html` |
| 徒步分段路书 + 爬升 + 海拔剖面 | `guide.html` 徒步路线详解 |
| 多瓦片源回退 + 7s 看门狗 + 离线提示 | `guide.html` 地图模块 |
| B 站实拍图 + 本地化 + UP 主署名 | `images.json`、`credits.json` |
| 逐日卡片默认展开 | `guide.html` 逐日行程 |
| 单文件离线分享版 | `build_shareable.py` 输出 |

## 版权

配图来自 B 站公开视频封面，版权归各 UP 主所有，仅作行程参考；
`credits.json` 保留了原始视频链接与作者，转载/再分发请注明来源。
