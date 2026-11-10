# livedead — LIVE/DEAD viability statistics / LIVE/DEAD 存活率统计

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

`livedead` turns tabulated fluorescent LIVE/DEAD counts into **viability percentages**, group summaries and a two-way ANOVA, plus a publication-style bar chart. In LIVE/DEAD BacLight staining, green (SYTO 9) objects are scored as live (membrane-intact) and red (propidium iodide) objects as dead (membrane-compromised); the module works on the resulting per-field counts, not on images. Typical use: comparing antibacterial/anti-adhesive coatings (F-DLC, laser-textured stainless steel) against a control across several time points and repeats. The companion `livedead_cellcounter` produces these counts automatically from fluorescence micrographs.

### Inputs and data formats

A table (Excel `.xlsx`/`.xls`, optional sheet, or CSV) with:

| Column | Required | Meaning |
|---|---|---|
| `live` | yes | Count of live (green) bacteria in one field/sample; non-negative integer |
| `dead` | yes | Count of dead (red) bacteria; non-negative integer |
| `group` | optional | Treatment/coating label, e.g. `Control`, `5%F-DLC` |
| `time` | optional | Sampling time label, e.g. `1h`, `3h`, `5h` |
| `repeat` | optional | Replicate identifier — accepted as a column but **not used in any statistic** |

Column names are configurable through the `LiveDeadAnalyzer` constructor (`live_col`, `dead_col`, `time_col`, `group_col`, `replicate_col`). Rows with NaN in `live`/`dead` are dropped. Bundled example: `data/examples/livedead_example.xlsx` and `examples/example_livedead.xlsx` (3 groups × 3 times × 3 repeats).

### Count validation performed on load

1. **Negative counts → hard error.** Any `live < 0` or `dead < 0` raises `ValueError` (cell counts cannot be negative).
2. **Non-integer counts → warning.** Values that are not within floating tolerance of an integer trigger a `warnings.warn` (normalised data is accepted but flagged).
3. **Derived columns.** `total = live + dead`; `dead_rate = dead / total`; `viability_pct = live / total × 100`; divisions by zero give `NaN` rather than 0 %.
4. **All-zero rows removed.** Rows with `live = dead = 0` ("no cells counted") are warned about and **excluded** from the statistics.

### Outputs

`run(path, sheet=None, output_dir="output")` writes and returns:

| Output | Content |
|---|---|
| `output/livedead_viability.png` | Bar chart: viability (%) for every group × time; groups coloured with `tab10`; error bars are SEM of the per-row viability |
| `output/livedead_summary.csv` | Grouped summary (see below), UTF-8 with BOM |
| `output/livedead_anova.csv` | Two-way ANOVA table from statsmodels (`sum_sq`, `df`, `F`, `PR(>F)` per term, including the intercept row), when the ANOVA succeeds |
| return dict | `{"figure", "anova", "anova_csv", "summary", "summary_csv"}` |

The summary uses the **pooled-count definition** of viability, `Σlive / Σ(live+dead) × 100`, with columns `n` (number of rows), `live_sum`, `dead_sum`; `dead_rate`/`viability_pct` are computed per row first and are available on the loaded data frame, but the summary/plot re-pool the raw counts.

### End-to-end pipeline

1. Load the table (`common.io_utils.load_table`, UTF-8-BOM tolerant CSV; Excel sheet selectable).
2. Validate columns, drop NaNs, cast `live`/`dead` to float.
3. Run the count checks (negative → error, non-integer → warning), add `total`, `dead_rate`, `viability_pct`, drop all-zero rows.
4. **Summary** (`LiveDeadAnalyzer.summary`): group by `group × time` (via a `<group>_<time>` string), compute pooled viability, `n`, `live_sum`, `dead_sum`; if only `group` exists, group by group; if neither exists, a single "all" row.
5. **Two-way ANOVA** (`LiveDeadAnalyzer.anova` → `common.stats.anova_two_way`): OLS of `viability_pct ~ C(group) * C(time)` (Type III sums of squares) on the **per-row viability percentages**; optional log10 transform of the response.
6. **Plot** the pooled viability bars with per-row SEM error bars.
7. Save figure, summary CSV, ANOVA CSV; exceptions from the ANOVA are swallowed (report still succeeds with `anova = None`).

### Algorithms and formulas

Per row:

```
total_i      = live_i + dead_i
viability_i  = 100 · live_i / total_i          (NaN when total_i = 0)
dead_rate_i  = dead_i / total_i
```

Group/time summary (pooled counts — the headline number):

```
viability_pooled = 100 · Σ live / Σ (live + dead)
n                = number of rows in the group/time cell
```

Bar-chart error bar (does **not** match the pooled bar height — it is the SEM of per-row viabilities):

```
SEM = sd(viability_i, ddof=1) / √(number of rows)      (0 for a single row)
```

Two-way ANOVA model:

```
y_ij = μ + α_i(group) + β_j(time) + (αβ)_ij + ε_ij ,    ε ~ N(0, σ²)
```

fit with `statsmodels.formula.api.ols` and `sm.stats.anova_lm(typ=3)`; the returned p-values are `factor1_p` (group), `factor2_p` (time), `interaction_p` (group×time). With `log10=True` the response is `log10(viability)` before fitting. There is no post-hoc test, no multiplicity correction and no normality/homogeneity-of-variance check.

### Parameters and defaults

| Parameter | Default | Meaning |
|---|---|---|
| `path` / `--file` | required | Excel/CSV input |
| `sheet` / `--sheet` | `None` | Excel worksheet name |
| `output_dir` / `--output` | `output` | Output directory |
| `live_col`, `dead_col` | `live`, `dead` | Count column names |
| `time_col`, `group_col` | `time`, `group` | Factor column names |
| `replicate_col` | `repeat` | Accepted, **unused** by any statistic |
| `log10` | `False` | Transform the ANOVA response (not exposed on the CLI/GUI; `report()` never enables it) |
| `group_col`, `time_col` overrides | `None` | Passed to `summary()` only |

### Implementation notes

* Package `labtoolbox/livedead/`: `livedead.py` (168 lines); shared helpers `common/stats.py` (`summarize`, `anova_two_way`) and `common/io_utils.py`.
* Dependencies: NumPy, pandas, matplotlib (Agg), statsmodels (imported lazily inside `anova_two_way`), openpyxl for `.xlsx`.
* `LiveDeadAnalyzer` methods: `load`, `summary`, `anova`, `plot`, `report`. `run()` wires them together via `**kwargs` → constructor.
* Group × time key construction is `group.astype(str) + "_" + time.astype(str)` and is split back with `str.rsplit("_", n=1)` — **group labels containing an underscore break the split** (the last `_`-separated fragment becomes the time). Use labels without `_`.
* The two `common.stats` helpers are shared: `summarize` (mean/sd/SEM with optional log10) is imported but not used by `livedead`; `anova_two_way` is reused by `livedead_cellcounter`'s sibling analysis.
* CLI `labtoolbox livedead --file ... [--sheet ...]`; GUI tab **🦠 LIVE/DEAD** (with "Open example table" → `examples/example_livedead.xlsx`).

### Assumptions, limitations and known quirks

* **Repeated measures are ignored.** The `repeat` column is never used: rows are treated as independent observations, and an ANOVA on percentages does not model the repeat structure (no mixed model, no averaging over repeats).
* **Bar height and error bar are different statistics.** Bars are pooled-count viabilities; error bars are SEMs of the per-row percentages. For unbalanced counts the bar is not the mean of the plotted error-bar sample.
* **ANOVA is on per-row percentages**, not on pooled counts or log-counts; variance can be non-normal/bounded, and there is no check. `log10` exists but is off in the standard workflow.
* **All-zero rows are silently removed** from statistics after a warning; rows with zero total produce NaN and remain in the data frame (they are not dropped explicitly — only `live = dead = 0` rows are).
* **ANOVA failure is swallowed.** In `report()` any ANOVA exception leaves `anova = None` and no CSV, with no error surfaced.
* Group/time labels are compared as **strings**; numeric times are sorted lexicographically by pandas groupby (e.g. `10h` before `2h`). Normalise time labels (e.g. `01h`, `02h` or minutes) if order matters.
* No outlier detection, no batch-effect correction, no propagation of counting uncertainty (Poisson) into the ANOVA.
* The plot always spans `0–110 %` and has no significance annotations.

### QC and validation

* Built-in data-entry checks: negative counts, non-integer counts, all-zero rows (see above). These are the module's only automatic QC.
* Recommended manual QC: check that `Σlive + Σdead` per group/time is plausible for the imaging protocol; compare pooled viability with the mean-of-rows and with the counter module's `dead_rate`; inspect the ANOVA residual df (a saturated design, e.g. no replicates, gives no residual and no p-values).
* Verified example (commit `0e0508e`, Python 3.11, statsmodels 0.14): `data/examples/livedead_example.xlsx` → summary shows Control 1h/3h/5h = 58.6/57.9/55.6 % and 5%F-DLC = 57.9/69.3/40.9 % (n = 4 per cell); Type III ANOVA gives group p = 0.803, time p = 0.072, interaction p = 0.296 (with an intercept row in the table).

### References

* Thermo Fisher Scientific. *LIVE/DEAD™ BacLight™ Bacterial Viability Kit (L7012) — product manual.* (SYTO 9 / propidium iodide staining and the live/dead interpretation)
* Berney M, Hammes F, Bosshard F, Weilenmann HU, Egli T. Assessment and interpretation of bacterial viability by using the LIVE/DEAD BacLight Kit in combination with flow cytometry. *Appl Environ Microbiol.* 2007;73(10):3283–3290. doi:10.1128/AEM.02750-06. (viability-staining interpretation and limitations)
* Seabold S, Perktold J. statsmodels: econometric and statistical modeling with Python. *Proc 9th Python in Science Conf.* 2010:92–96. (OLS / Type III ANOVA implementation)
* Sokal RR, Rohlf FJ. *Biometry: The Principles and Practice of Statistics in Biological Research.* 3rd ed. W. H. Freeman; 1995. (two-way ANOVA design and assumptions)
* McKinney W. Data structures for statistical computing in Python. *Proc 9th Python in Science Conf.* 2010:56–61. (pandas I/O)

## 中文

### 目的与科学背景

`livedead` 把表格化的 LIVE/DEAD 荧光计数转换成**存活率百分比**、分组汇总与双因素 ANOVA，并画出论文风格柱状图。LIVE/DEAD BacLight 染色中，绿色（SYTO 9）对象记为活菌（膜完整），红色（碘化丙啶）对象记为死菌（膜受损）；本模块处理由此得到的**逐视野计数**，不处理图像。典型用途：在多个时间点/重复下比较抗菌或抗黏附涂层（F-DLC、激光织构不锈钢）与对照。配套模块 `livedead_cellcounter` 可从荧光显微图自动产出这些计数。

### 输入与数据格式

一张表（Excel `.xlsx`/`.xls`，可指定工作表，或 CSV），列如下：

| 列名 | 必需 | 含义 |
|---|---|---|
| `live` | 是 | 一个视野/样品中的活菌（绿）数；非负整数 |
| `dead` | 是 | 死菌（红）数；非负整数 |
| `group` | 可选 | 处理/涂层标签，如 `Control`、`5%F-DLC` |
| `time` | 可选 | 采样时间标签，如 `1h`、`3h`、`5h` |
| `repeat` | 可选 | 重复编号——会作为列被接受，但**不参与任何统计** |

列名可通过 `LiveDeadAnalyzer` 构造参数（`live_col`、`dead_col`、`time_col`、`group_col`、`replicate_col`）修改。`live`/`dead` 为 NaN 的行会被丢弃。自带示例：`data/examples/livedead_example.xlsx` 与 `examples/example_livedead.xlsx`（3 组 × 3 时间 × 3 重复）。

### 载入时的计数校验

1. **负计数 → 硬报错。** 任一 `live < 0` 或 `dead < 0` 抛 `ValueError`（细胞计数不可能为负）。
2. **非整数计数 → 告警。** 与整数之差超出浮点容差的值触发 `warnings.warn`（允许归一化数据，但会标记）。
3. **派生列。** `total = live + dead`；`dead_rate = dead / total`；`viability_pct = live / total × 100`；除零得 `NaN` 而非 0 %。
4. **全零行被剔除。** `live = dead = 0`（"没有数到细胞"）的行会先告警，再**排除**出统计。

### 输出

`run(path, sheet=None, output_dir="output")` 写出并返回：

| 输出 | 内容 |
|---|---|
| `output/livedead_viability.png` | 柱状图：各 group × time 的存活率（%）；组用 `tab10` 配色；误差棒为逐行存活率的 SEM |
| `output/livedead_summary.csv` | 分组汇总（见下），UTF-8 带 BOM |
| `output/livedead_anova.csv` | statsmodels 的双因素 ANOVA 表（每项 `sum_sq`、`df`、`F`、`PR(>F)`，含截距行），ANOVA 成功时写出 |
| 返回 dict | `{"figure", "anova", "anova_csv", "summary", "summary_csv"}` |

汇总采用**合并计数**定义的存活率 `Σlive / Σ(live+dead) × 100`，列为 `n`（行数）、`live_sum`、`dead_sum`；`dead_rate`/`viability_pct` 先按行计算并保存在数据帧上，但汇总/作图会重新合并原始计数。

### 端到端流程

1. 载入表格（`common.io_utils.load_table`，CSV 容忍 UTF-8 BOM；Excel 可选工作表）。
2. 校验列名、去 NaN、把 `live`/`dead` 转 float。
3. 执行计数校验（负值报错、非整数告警），新增 `total`、`dead_rate`、`viability_pct`，剔除全零行。
4. **汇总**（`LiveDeadAnalyzer.summary`）：按 `group × time`（用 `<group>_<time>` 字符串）分组，算合并存活率、`n`、`live_sum`、`dead_sum`；若只有 `group` 则按组汇总；两者都没有则输出单行 "all"。
5. **双因素 ANOVA**（`LiveDeadAnalyzer.anova` → `common.stats.anova_two_way`）：对**逐行存活率百分比**拟合 `viability_pct ~ C(group) * C(time)` 的 OLS（Type III 平方和）；可选对响应做 log10 变换。
6. **画图**：合并存活率柱 + 逐行 SEM 误差棒。
7. 保存图、汇总 CSV、ANOVA CSV；ANOVA 的异常被吞掉（报告仍成功，`anova = None`）。

### 算法与公式

逐行：

```
total_i      = live_i + dead_i
viability_i  = 100 · live_i / total_i          (total_i = 0 时为 NaN)
dead_rate_i  = dead_i / total_i
```

分组/时间汇总（合并计数——主报告数值）：

```
viability_pooled = 100 · Σ live / Σ (live + dead)
n                = 该 group/time 单元的行数
```

柱状图误差棒（与合并柱高**并非同一统计量**，它是逐行存活率的 SEM）：

```
SEM = sd(viability_i, ddof=1) / √(行数)      (单行时为 0)
```

双因素 ANOVA 模型：

```
y_ij = μ + α_i(group) + β_j(time) + (αβ)_ij + ε_ij ,    ε ~ N(0, σ²)
```

用 `statsmodels.formula.api.ols` 拟合、`sm.stats.anova_lm(typ=3)` 出表；返回的 p 值分别为 `factor1_p`（组）、`factor2_p`（时间）、`interaction_p`（组×时间）。`log10=True` 时响应先取 `log10(viability)` 再拟合。没有事后检验、没有多重比较校正、也不检查正态性/方差齐性。

### 参数与默认值

| 参数 | 默认值 | 含义 |
|---|---|---|
| `path` / `--file` | 必填 | Excel/CSV 输入 |
| `sheet` / `--sheet` | `None` | Excel 工作表名 |
| `output_dir` / `--output` | `output` | 输出目录 |
| `live_col`、`dead_col` | `live`、`dead` | 计数列名 |
| `time_col`、`group_col` | `time`、`group` | 因子列名 |
| `replicate_col` | `repeat` | 接受但**任何统计都不使用** |
| `log10` | `False` | 是否变换 ANOVA 响应（CLI/GUI 未暴露；`report()` 从不开启） |
| `group_col`、`time_col` 覆盖参数 | `None` | 仅供 `summary()` 使用 |

### 实现说明

* 包 `labtoolbox/livedead/`：`livedead.py`（168 行）；共享工具 `common/stats.py`（`summarize`、`anova_two_way`）与 `common/io_utils.py`。
* 依赖：NumPy、pandas、matplotlib（Agg）、statsmodels（在 `anova_two_way` 内懒加载）、openpyxl（读 `.xlsx`）。
* `LiveDeadAnalyzer` 方法：`load`、`summary`、`anova`、`plot`、`report`。`run()` 用 `**kwargs` → 构造器把它们串起来。
* group × time 键由 `group.astype(str) + "_" + time.astype(str)` 拼接，再用 `str.rsplit("_", n=1)` 拆回——**含下划线的组名会破坏拆分**（最后一个 `_` 之后被当作时间）。请使用不含 `_` 的标签。
* `common.stats` 两个助手是共享的：`summarize`（均值/标准差/SEM，可选 log10）被 import 但 `livedead` 未使用；`anova_two_way` 也被 `livedead_cellcounter` 的同类分析复用。
* 命令行 `labtoolbox livedead --file ... [--sheet ...]`；GUI 标签页 **🦠 LIVE/DEAD**（"打开范例表格" → `examples/example_livedead.xlsx`）。

### 假设、局限与已知怪癖

* **忽略重复测量结构。** `repeat` 列从不使用：行被当作独立观测，对百分比做 ANOVA 也不建模重复结构（无混合模型、不对重复取平均）。
* **柱高与误差棒是不同统计量。** 柱是合并计数存活率；误差棒是逐行百分比的 SEM。计数不平衡时柱高不等于误差棒样本的均值。
* **ANOVA 作用于逐行百分比**，不是合并计数或对数计数；方差可能非正态/有界，且没有检验。`log10` 虽存在，但标准工作流不开启。
* **全零行在告警后被静默剔除**出统计；总数为 0 的行产生 NaN 且仍留在数据帧中（只有 `live = dead = 0` 的行会被剔除）。
* **ANOVA 失败被吞掉。** `report()` 中任何 ANOVA 异常都只留下 `anova = None` 且不写 CSV，不向用户报错。
* group/time 标签按**字符串**比较；数字时间会被 pandas groupby 按字典序排序（如 `10h` 排在 `2h` 前）。若顺序重要，请规范化时间标签（如 `01h`、`02h` 或分钟）。
* 无离群值检测、无批效应校正、不把计数不确定性（泊松）传播进 ANOVA。
* 图固定 `0–110 %`，无显著性标注。

### 质控与验证

* 内建数据录入校验：负计数、非整数计数、全零行（见上）。这是模块仅有的自动 QC。
* 建议人工 QC：检查每个 group/time 的 `Σlive + Σdead` 是否符合成像流程；把合并存活率与行均值、以及计数模块的 `dead_rate` 对比；检查 ANOVA 残差自由度（饱和设计如无重复时没有残差，也就没有 p 值）。
* 核对示例（commit `0e0508e`，Python 3.11、statsmodels 0.14）：`data/examples/livedead_example.xlsx` → 汇总 Control 1h/3h/5h = 58.6/57.9/55.6 %，5%F-DLC = 57.9/69.3/40.9 %（每格 n = 4）；Type III ANOVA 得 group p = 0.803、time p = 0.072、交互 p = 0.296（表中含截距行）。

### 参考文献

* Thermo Fisher Scientific. *LIVE/DEAD™ BacLight™ Bacterial Viability Kit (L7012) — product manual.*（SYTO 9 / 碘化丙啶染色与死活判读）
* Berney M, Hammes F, Bosshard F, Weilenmann HU, Egli T. Assessment and interpretation of bacterial viability by using the LIVE/DEAD BacLight Kit in combination with flow cytometry. *Appl Environ Microbiol.* 2007;73(10):3283–3290. doi:10.1128/AEM.02750-06.（存活率染色的解释与局限）
* Seabold S, Perktold J. statsmodels: econometric and statistical modeling with Python. *Proc 9th Python in Science Conf.* 2010:92–96.（OLS / Type III ANOVA 实现）
* Sokal RR, Rohlf FJ. *Biometry: The Principles and Practice of Statistics in Biological Research.* 3rd ed. W. H. Freeman; 1995.（双因素 ANOVA 设计与假设）
* McKinney W. Data structures for statistical computing in Python. *Proc 9th Python in Science Conf.* 2010:56–61.（pandas I/O）
