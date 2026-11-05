# 真实地图（Leaflet）与坐标规范

> 目标：地图**必须真的能渲染**，且在任何网络环境下都不白屏。
> 常见事故：Carto/OSM 瓦片被墙 → 整块地图空白，用户连点两次反馈"地图打不开"。

---

## 1. 底图源优先级

| 优先级 | 源 | URL 模板 | 坐标系 | 备注 |
|-------|----|---------|-------|------|
| 1 | 高德路网（中文标注） | `https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7` | **GCJ-02** | 国内最稳、中文地名 |
| 2 | Esri 卫星影像 | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` | WGS84 | 看地形最直观 |
| 3 | Esri 地形图 | `.../World_Topo_Map/MapServer/tile/{z}/{y}/{x}` | WGS84 | 有等高线，适合徒步 |
| 4 | CARTO Voyager | `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png` | WGS84 | 常被墙，备用 |
| 5 | OpenStreetMap | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | WGS84 | 常被墙，备用 |

```javascript
const tileProviders = [
  { name:'amap',  label:'高德路网',  url:'https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7', subdomains:'1234', attr:'&copy; 高德地图', maxNative:17 },
  { name:'esri',  label:'卫星影像',  url:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', subdomains:'', attr:'&copy; Esri', maxNative:18 },
  { name:'topo',  label:'地形图',    url:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', subdomains:'', attr:'&copy; Esri', maxNative:18 },
  { name:'carto', label:'经典地形',  url:'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', subdomains:'abcd', attr:'&copy; OSM &copy; CARTO', maxNative:19 },
  { name:'osm',   label:'OSM 标准',  url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png', subdomains:'', attr:'&copy; OpenStreetMap', maxNative:19 }
];
```

先跑 `python scripts/probe_sources.py`，把**探测通过的源排在最前**，但始终保留 ≥3 个备用源。

---

## 2. 多源自动回退 + 看门狗（必做）

```javascript
let baseLayer = null, baseFail = 0, watchTimer = null, tileSeen = 0, triedSet = new Set();

function addBase(pid){
  const p = tileProviders.find(x => x.name === pid) || tileProviders[0];
  if(baseLayer) map.removeLayer(baseLayer);
  baseFail = 0; tileSeen = 0;
  if(watchTimer){ clearTimeout(watchTimer); watchTimer = null; }

  baseLayer = L.tileLayer(p.url, {
    attribution: p.attr, maxZoom: 18, maxNativeZoom: p.maxNative,
    detectRetina: false, subdomains: p.subdomains || 'abc'
  }).addTo(map);

  baseLayer.on('tileload', () => {
    tileSeen++; triedSet.clear();
    document.getElementById('mapOffline').hidden = true;
  });
  baseLayer.on('tileerror', () => { baseFail++; if(baseFail >= 3) advance(); });

  // 挂起但不报错（被墙时最典型）→ 7 秒无瓦片即换源
  watchTimer = setTimeout(() => { if(tileSeen === 0) advance(); }, 7000);

  function advance(){
    if(watchTimer){ clearTimeout(watchTimer); watchTimer = null; }
    triedSet.add(p.name);
    if(triedSet.size >= tileProviders.length){           // 全部试过仍失败
      document.getElementById('mapOffline').hidden = false;  // 展示离线提示
      return;
    }
    const idx = tileProviders.findIndex(x => x.name === p.name);
    setBasemap(tileProviders[(idx + 1) % tileProviders.length].name);
  }
}
```

配套 UI：
- 底图切换按钮组（`.basemap-switch`），当前源高亮
- 离线提示文案：**"当前网络无法加载地图瓦片（本页其余内容与全部图片仍可离线查看）→ 请切换到「行程示意图」查看路线。"**（要给出替代方案，不能只说"失败"）

---

## 3. 初始化健壮性（白屏的真正根因）

```javascript
function initMap(){
  if(map) return;                        // 只初始化一次
  if(typeof L === 'undefined'){          // CDN 挂了
    $('#map').innerHTML = '<p style="padding:2rem;text-align:center">地图组件加载失败（需联网），请刷新或查看「行程示意图」。</p>';
    return;
  }
  try {
    map = L.map('map', { scrollWheelZoom:false }).setView([lat, lon], zoom);
    // ... 瓦片、标记、折线
  } catch (e) {
    console.error('[map] init failed', e);
    $('#map').innerHTML = '<p style="padding:2rem;text-align:center">地图初始化失败，请查看「行程示意图」。</p>';
  }
}
```

- **懒加载**：用户第一次切到「真实地图」tab 才初始化（隐藏容器里初始化会算错尺寸 → 瓦片错位）
- 初始化后补一次尺寸重算：
  ```javascript
  requestAnimationFrame(() => map.invalidateSize());
  setTimeout(() => map.invalidateSize(), 300);
  ```
- **`localStorage` 全程 try/catch**：隐私模式/被禁用时会抛异常，一抛就把后面的地图初始化整段中断（这曾经就是"地图白屏"的真凶）
  ```javascript
  const store = {
    get(k, d){ try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }
  };
  ```
- 页面 JS 按功能模块 try/catch 隔离：清单、预算、灯箱、地图互不拖累

---

## 4. 坐标系（最容易出错，必读）

| 底图 | 坐标系 | 后果 |
|------|-------|------|
| 高德 / 腾讯 / 百度（国内） | **GCJ-02**（火星坐标） | 直接用 WGS84 坐标会偏移 **300–700m** |
| Esri / OSM / CARTO / Wikipedia | **WGS84** | 正常 |

处理方式（选一）：
1. **地图默认用 Esri 卫星影像**（WGS84），坐标直接用 Wikipedia/OSM 的 WGS84 → 最省事、最准
2. 若默认用高德瓦片：把点位坐标 WGS84 → GCJ-02 转换后再画，并在图注说明"高德底图已做坐标纠偏"
3. 折中：默认高德（中文地名友好），但在图例注明 **"精确位置请切换卫星影像"**，并在文档里标注偏移量

> 不要混用：高德瓦片 + WGS84 坐标 + 声称"精确" = 用户到现场发现差 500 米。

---

## 5. 坐标采集规则

- 优先 **高德 POI / Wikipedia 点坐标 / OSM node**（明确是"点"而不是"面"）
- **区县坐标是行政范围中心，不能当景点坐标**（偏差可达十几公里）
- 同一地级市的两个镇可能相距 60km+，**不能凭感觉摆点**
- 每个坐标都写进文档坐标表：`名称 | 经度 | 纬度 | 来源`
- 徒步轨迹点至少要 3 个（起点/最高点/垭口或折返点），不要一条直线连过去

---

## 6. 地图上的线路

- 当日自驾路线：按天配色（Day1 橙 / Day2 绿），粗半透明底 + 细实线发光
- 徒步段：**红色虚线**，与车程路线视觉区分；图例必须写"徒步轨迹（示意）"
- 标记：`L.divIcon` 自定义（彩色圆点 + 白边 + 脉冲环 + 站点编号），不要默认 pin
- 弹窗：景点名 + 所属市区 + 第几天 + 一句话亮点 + 缩略图（缩略图也要本地化/内嵌）
- `map.fitBounds(bounds, { padding:[40,40] })` 自适应全部点位

---

## 7. 交付前地图 QA

- [ ] 切到「真实地图」后 `#map .leaflet-tile` 中加载成功的数量 ≥ 8
- [ ] `#map .leaflet-overlay-pane path` 数量 = 车程段数 + 徒步段数
- [ ] 5 个源里手动切换任意一个都能出图（或明确显示离线提示）
- [ ] 断网/被墙时显示离线提示，且页面其他部分正常
- [ ] 控制台 0 error
- [ ] 点位方向核对：东→右、西→左、北→上、南→下
