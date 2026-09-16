# 色卡与实体校色

## 默认色卡

新图纸默认使用 `mard-291`，它是包含 291 个原始 MARD 色号的屏幕参考色卡：

| 范围 | 系列 | 数量 | 默认自动匹配 |
| --- | --- | ---: | --- |
| 常规色 | A–H、M | 221 | 是 |
| 扩展/特殊色 | P、Q、R、T、Y、ZG | 70 | 否，需显式启用 |
| 合计 | — | 291 | — |

颜色编码使用 `A1`、`B12`、`ZG8` 等品牌色号，不创建内部转换编号。旧版 39 色 `mard` 仍作为只读兼容色卡保留，已有图纸不会受影响。

色卡服务会从 `mard-291` 确定性派生 `mard-24`、`mard-48`、`mard-72`、`mard-96`、`mard-120`、`mard-144`、`mard-168`、`mard-192`、`mard-221` 和 `mard-264` 等只读工作色阶。派生色卡保留原始色号，并选择感知覆盖较均衡的子集；它们不是新的品牌色号体系。

## 屏幕参考与实体颜色

内置 `mard-291.json` 的 `rgb` 和 `hex` 适用于网页预览和屏幕参考色差计算。系列和数量参考 [MARD 291 色卡页面](https://bitbead.com/products/mard-5mm-fuse-bead-color-chart)，但该页面不是具体生产批次的实体测色证明。

因此：

- 不应把屏幕 Hex 值称为实体豆的绝对色值；显示器、光源、材质和批次都会影响结果。
- 商业成品或大型作品应先制作 1:1 小样，并按当前库存调整禁用色和锁定色。
- 特殊材质色默认不参与自动转换，需要时通过 `include_special_colors` 显式启用。
- 若获得可复核的官方或实物测色数据，应创建版本化自定义色卡，不要直接覆盖内置参考色卡。

## 匹配与质量报告

默认算法是 LAB + CIEDE2000。选色、逐格匹配、空间清理、库存替代、质量报告和热力图优先使用同一组色彩值：色号存在 `measured_lab` 时使用实体值，否则从屏幕 sRGB 转为 D65 LAB。RGB 欧氏距离是兼容模式，仍只使用屏幕 RGB。

自动限色把 `max_colors` 作为生产上限，并按 `target_p95_delta_e_00` 判断是否提前停止。质量报告包括：

- 平均、P95 和最大 ΔE00。
- 实际使用色数、库存覆盖、缺色数量和替代建议。
- 清理调整格数与比例。
- 结构重点覆盖、加权误差和重点区域误差。
- `quality_basis`、`matching_color_basis`、实测格数和覆盖率。

`quality_basis` 可能是：

- `measured_lab`：本次实际使用颜色全部有实体测量值。
- `mixed_lab`：实体 LAB 与屏幕 RGB 回退混用。
- `screen_rgb`：没有实体测量值，ΔE00 仅代表屏幕参考误差。
- `not_applicable`：没有可评估的非透明格。

## Oracle 下界

每次图片转换还会计算当前候选色卡的逐格 Oracle 下界。它忽略作品颜色数和空间清理，让每格从当前全部合格候选色号中独立选择最低色差，但仍遵守特殊色开关、禁用色和严格库存过滤。

报告字段包括：

- `oracle_average_delta_e_00` 和 `oracle_p95_delta_e_00`：当前色卡在一格一色约束下的理论误差下界。
- `p95_oracle_gap`：正式结果与 Oracle P95 的差距。
- `oracle_target_reachable`：Oracle 是否能达到本次 `target_p95_delta_e_00`。
- `oracle_palette_color_count`：参与下界计算的候选色数。

若 `oracle_target_reachable = false`，提高作品颜色上限也无法达到目标，需要扩展色卡、放宽库存限制或取得更准确的实体数据。若 Oracle 达标而正式结果未达标，差距来自限色、锁定色或空间/结构约束。该下界只衡量采样后单格颜色，不包含裁切和网格降采样造成的结构损失。

## 自定义实体 LAB 色卡

`rgb`/`hex` 负责显示，`measured_lab` 负责实体匹配。当前只接受与转换管线一致的 CIELAB D65、2° 标准观察者数据；D50 等数据必须先做有记录的色适应转换。

```json
{
  "id": "my-measured-palette-v1",
  "name": "当前库存实体测色 v1",
  "brand": "My Brand",
  "calibration": {
    "color_space": "CIELAB",
    "illuminant": "D65",
    "observer": "2_degree",
    "source": "2026-08 当前库存样豆",
    "instrument": "分光测色仪型号",
    "measurement_geometry": "d/8 SCI",
    "measured_at": "2026-08-31"
  },
  "colors": [
    {
      "code": "R1",
      "name_zh": "红",
      "hex": "#E9413A",
      "rgb": [233, 65, 58],
      "measured_lab": [52.84, 65.17, 43.92],
      "available": true
    }
  ]
}
```

只要任一颜色包含 `measured_lab`，色卡就必须提供 `calibration.source`。L* 范围为 0–100，a*/b* 范围为 -160–160。接口返回 `colorimetry_status`、`measured_color_count` 和 `measurement_coverage_percent`，避免把部分校准误报为完整实体校准。

## 库存工作流

转换页按色卡在当前浏览器保存库存数量，并支持：

- `report`：按最佳匹配生成图纸，再报告缺色和库存内替代候选。
- `only`：只使用数量大于零的库存色号；至少需要一种正库存色。

替代建议不会自动改写图纸，避免在肤色、阴影和特殊效果上做不可逆替换。图纸会保存本次库存快照和色彩报告，使转换决策在浏览器库存或色卡后续变化时仍可追溯。
