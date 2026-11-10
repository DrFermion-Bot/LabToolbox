# growth_curve — Bacterial growth-curve fitting / 细菌生长曲线拟合

> [← Module index](README.md) · [English](#english) · [中文](#中文)

## English

### Purpose and scientific context

`growth_curve` fits optical-density (OD600) time series of bacterial cultures with empirical growth models and produces a standard two-panel figure (OD600 and log10 CFU/mL). It is used to characterise batch cultures of *E. coli* and *S. aureus* — lag time, maximum growth rate and asymptotic OD — e.g. when comparing the growth of bacteria exposed to F-DLC-coated surfaces or to different media. The fit parameters are reported as a ranked table (best R² first); the module is a curve-fitting/reporting tool, not a mechanistic growth model.

### Inputs and data formats

The module needs a table with exactly three columns (names are configurable only through the Python API):

| Column | Unit | Meaning |
|---|---|---|
| `time_min` | minutes | Sampling time |
| `od600` | absorbance (a.u.) | Optical density at 600 nm |
| `cfu_ml` | CFU/mL | Colony-forming units per mL (viable counts; used for the second panel only) |

* Files: `.xlsx` / `.xls` via `pandas.read_excel` (sheet selectable with `sheet=`, otherwise the first sheet), or `.csv` read as UTF-8 with BOM tolerance (`utf-8-sig`; the bundled example CSV has a BOM).
* Rows with missing values in any of the three columns are dropped (`dropna`); all values are cast to float.
* All three columns are **required** even though `cfu_ml` is only plotted (the fit uses OD600 only).
* Embedded data: `GrowthCurveAnalyzer.load_from_lists(time_min, od600, cfu_ml)` exists for API use; it is not reachable from the CLI/GUI.
* Examples: `data/examples/growth_Ecoli_example.csv` (12 points, 60–427 min) and `examples/example_growth_curve.xlsx` (synthetic logistic curve, 10 points).

### Outputs

`run(path=..., output_dir="output", sheet=None)` (or `GrowthCurveAnalyzer.report()`):

| Output | Explanation |
|---|---|
| `output/growth_fit_params.csv` | UTF-8-BOM CSV with columns `model`, `r_squared`, `params`; rows sorted by R² descending |
| `output/growth_curve.png` | 2-panel figure: OD600 vs time (blue) and log10(CFU/mL) vs time (red); 200 dpi |
| return dict | `{"fit_params": DataFrame, "figure": path, "csv": path}` |

`params` is a single string of the fitted values joined with `", "` and formatted with `"%.4g"`, in the model's function-argument order. Parameter names are **not** written to the CSV — a reader must know the model signature to interpret them.

### End-to-end pipeline

1. Load the table (`common.io_utils.load_table`), validate the three column names, drop NaNs, cast to float.
2. For each model in `models = ("Gompertz", "Logistic", "Quadratic")`:
   * call `fit_curve(t, OD600, model_name)` → `scipy.optimize.curve_fit`, `maxfev=20000`, automatic initial guess when `p0 is None`;
   * on any exception the model is silently skipped;
   * compute R² from the fitted curve.
3. Assemble the parameter table and sort by R² (descending).
4. Plot both raw series (no fitted curves are drawn) and save the figure.
5. Save the parameter CSV and return everything.

### Algorithms and formulas

Models registered in `common/fitting.py` (x = time, y = OD600):

| Name | Function | Symbols |
|---|---|---|
| Linear | `a·x + b` | slope, intercept |
| Quadratic | `a·x² + b·x + c` | — |
| Exponential | `a·exp(b·x) + c` | — |
| Power | `a·x^b` | — |
| Gompertz | `A·exp(−exp( μ·e/A · (λ − x) + 1 ))` | `A` = asymptote (OD), `μ` = maximum specific growth rate (OD·min⁻¹), `λ` = lag time (min), `e` = Euler's number |
| Logistic | `A / (1 + exp(−k·(x − x0)))` | `A` = asymptote, `k` = rate (min⁻¹), `x0` = inflection time (min) |

The Gompertz form is Zwietering's re-parameterisation of the modified Gompertz model, in which the three parameters are directly interpretable (asymptote, maximum growth rate, lag time) — the same form recommended when comparing growth curves (Zwietering et al. 1990).

Goodness of fit:

```
y_hat = f(x; p)
R² = 1 − Σ(y − y_hat)² / Σ(y − ȳ)²        (NaN when the data are constant, Σ(y−ȳ)² = 0)
```

Initial guesses (`p0 is None`, only for the two growth models):

```
Gompertz: p0 = [1.1 · max(y), 0.5, x[argmax(y)]]
Logistic: p0 = [1.1 · max(y), 0.5, x[len(x)//2]]
```

No bounds are given to `curve_fit`; if `p0` is `None` SciPy uses its own default. Fitting is unweighted, in linear OD space, with all time points equally weighted.

### Parameters and defaults

| Parameter | Default | Where | Meaning |
|---|---|---|---|
| `path` / `--data` | required | API/CLI | Excel/CSV input file |
| `output_dir` / `--output` | `output` | API/CLI | Output directory (created if missing) |
| `sheet` | `None` | API/CLI (`livedead` has a flag; growth CLI does not expose `sheet`) | Excel worksheet name |
| `time_col` | `time_min` | class constructor | time column name |
| `od_col` | `od600` | class constructor | OD column name |
| `cfu_col` | `cfu_ml` | class constructor | CFU column name |
| `models` | `("Gompertz", "Logistic", "Quadratic")` | `fit_all()` | models to try |
| `p0` | `None` (auto for Gompertz/Logistic) | `fit_curve()` | initial parameters |
| `maxfev` | `20000` | `fit_curve()` | max function evaluations |

`run(data=None, path=None, ...)` accepts `data` for API compatibility but ignores it and raises `ValueError("需要提供 path")` when no path is given.

### Implementation notes

* Package `labtoolbox/growth_curve/`: `growth.py` (107 lines) + `common/fitting.py` (67 lines) + `common/io_utils.py`.
* `GrowthCurveAnalyzer` methods: `load`, `load_from_lists`, `fit_all`, `plot`, `report`. Dependencies: NumPy, pandas, SciPy, matplotlib (Agg backend).
* Fits use `scipy.optimize.curve_fit`; R² is computed manually (not `scipy.stats.linregress`). The covariance matrix `pcov` is returned by `fit_curve` but dropped by `fit_all`, so parameter uncertainties are not reported.
* The figure plots raw data only — the fitted models are **not** overlaid, so the R² table is the only visual/numerical link to the fit. Titles and axis labels are hard-coded English.
* GUI tab **📈 生长曲线** ("Open example table" button opens `examples/example_growth_curve.xlsx`); CLI `labtoolbox growth-curve --data ...`.

### Assumptions, limitations and known quirks

* **Only OD600 is fitted.** CFU data are plotted (log10) but never fitted; CFU = 0 produces `-inf` and matplotlib/NumPy warnings (there is no guard).
* **Gompertz default starting value is badly scaled for minute-based data.** The hard-coded `μ0 = 0.5 OD·min⁻¹` is far above typical batch-culture values (≈0.01–0.03 min⁻¹), and the lag guess sits at the time of maximum OD. On the bundled `data/examples/growth_Ecoli_example.csv` the Gompertz fit converges to a degenerate `μ = 0.5, λ = 421 min` solution with **R² = −3.29**, while Logistic reaches R² = 0.999. Always inspect R² (and be ready to rescale time to hours or supply `p0` through the API).
* **No fit is drawn on the figure**, so a bad fit is easy to miss from the PNG alone.
* **Silent failure modes.** A model whose `curve_fit` raises is silently dropped; if *all* models fail, `fit_all` returns an empty DataFrame and the subsequent `sort_values("r_squared")` raises `KeyError`.
* **`params` is an unlabelled string** formatted to 4 significant digits; precision and covariance are not preserved.
* **Fitting is unweighted and in linear space.** No replicate/error bars, no weighting by CFU precision, no log-OD (exponential-phase) fitting, no blank/plate-path-length correction, no well-plate/OD-reader metadata.
* **No model selection statistics** beyond R² (no AIC/BIC, no residual diagnostics, no confidence intervals).
* Model formulas are the standard empirical ones; no Arrhenius/pH/temperature dependence is modelled.

### QC and validation

* The only built-in quality metric is R² per model (NaN if the data are constant), plus the check that the rank-1 model is physically plausible (positive `A`, `μ`, `k`; `λ` inside the sampling window).
* Recommended manual QC: overlay the chosen model at the tabulated parameters before publication; compare Gompertz/Logistic asymptotes with the observed plateau; verify that `λ` is not pinned to the first/last sample.
* Verification example at commit `0e0508e` (Python 3.11, SciPy 1.17, NumPy 2.4) on `data/examples/growth_Ecoli_example.csv`: Logistic R² = 0.9992 (A = 1.496, k = 0.02855 min⁻¹, x0 = 181.6 min), Quadratic R² = 0.9597, Gompertz R² = −3.29 (see quirk above); figure and CSV are produced as described.

### References

* Zwietering MH, Jongenburger I, Rombouts FM, van 't Riet K. Modeling of the bacterial growth curve. *Appl Environ Microbiol.* 1990;56(6):1875–1881. doi:10.1128/aem.56.6.1875-1881.1990. (modified Gompertz parameterisation and comparison of Logistic/Gompertz models)
* Virtanen P, et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. *Nat Methods.* 2020;17:261–272. doi:10.1038/s41592-019-0686-2. (`scipy.optimize.curve_fit`)
* McKinney W. Data structures for statistical computing in Python. *Proc 9th Python in Science Conf.* 2010:56–61. (pandas table I/O used by the module)
* Verhulst PF. Notice sur la loi que la population suit dans son accroissement. *Correspondance Mathématique et Physique.* 1838;10:113–121. (original logistic growth equation)

## 中文

### 目的与科学背景

`growth_curve` 用经验生长模型拟合细菌培养的 OD600 时间序列，并输出标准双面板图（OD600 与 log10 CFU/mL）。用于表征 *E. coli*、*S. aureus* 的批培养特征——延滞期、最大比生长速率、渐近 OD——例如比较接触 F-DLC 涂层表面或不同培养基中细菌的生长。拟合参数以按 R² 排序的表报告；本模块是曲线拟合/报告工具，不是机制性生长模型。

### 输入与数据格式

需要恰好三列的表格（列名仅可通过 Python API 改）：

| 列名 | 单位 | 含义 |
|---|---|---|
| `time_min` | 分钟 | 采样时间 |
| `od600` | 吸光度（a.u.） | 600 nm 光密度 |
| `cfu_ml` | CFU/mL | 每毫升菌落形成单位（活菌计数；仅用于第二面板） |

* 文件：`.xlsx` / `.xls` 经 `pandas.read_excel`（可用 `sheet=` 选工作表，否则取第一个），或 `.csv` 按 UTF-8 读（容忍 BOM：`utf-8-sig`，仓库自带示例 CSV 带 BOM）。
* 三列中任一处缺失的行会被 `dropna` 丢弃；数值统一转 float。
* 三列**均为必需**，尽管 `cfu_ml` 只用于画图（拟合只用 OD600）。
* 内嵌数据：`GrowthCurveAnalyzer.load_from_lists(time_min, od600, cfu_ml)` 供 API 使用；CLI/GUI 无法触达。
* 示例：`data/examples/growth_Ecoli_example.csv`（12 点，60–427 min）与 `examples/example_growth_curve.xlsx`（合成逻辑斯蒂曲线，10 点）。

### 输出

`run(path=..., output_dir="output", sheet=None)`（或 `GrowthCurveAnalyzer.report()`）：

| 输出 | 说明 |
|---|---|
| `output/growth_fit_params.csv` | UTF-8-BOM CSV，列 `model`、`r_squared`、`params`；按 R² 降序排列 |
| `output/growth_curve.png` | 双面板图：OD600–时间（蓝）、log10(CFU/mL)–时间（红）；200 dpi |
| 返回 dict | `{"fit_params": DataFrame, "figure": path, "csv": path}` |

`params` 是把拟合值按 `"%.4g"` 格式化后用 `", "` 拼接的字符串，顺序与模型函数参数一致。CSV 中**不写**参数名——读者必须知道模型签名才能解读。

### 端到端流程

1. 载入表格（`common.io_utils.load_table`），校验三个列名，去 NaN，转 float。
2. 对 `models = ("Gompertz", "Logistic", "Quadratic")` 中每个模型：
   * 调 `fit_curve(t, OD600, model_name)` → `scipy.optimize.curve_fit`，`maxfev=20000`，`p0 is None` 时用自动初值；
   * 任何异常都静默跳过该模型；
   * 由拟合曲线计算 R²。
3. 组装参数表并按 R² 降序排序。
4. 画两条原始序列（**不画**拟合曲线），保存图。
5. 保存参数 CSV 并返回。

### 算法与公式

`common/fitting.py` 注册的模型（x = 时间，y = OD600）：

| 名称 | 函数 | 符号 |
|---|---|---|
| Linear | `a·x + b` | 斜率、截距 |
| Quadratic | `a·x² + b·x + c` | — |
| Exponential | `a·exp(b·x) + c` | — |
| Power | `a·x^b` | — |
| Gompertz | `A·exp(−exp( μ·e/A · (λ − x) + 1 ))` | `A` = 渐近值（OD），`μ` = 最大比生长速率（OD·min⁻¹），`λ` = 延滞时间（min），`e` = 自然常数 |
| Logistic | `A / (1 + exp(−k·(x − x0)))` | `A` = 渐近值，`k` = 速率（min⁻¹），`x0` = 拐点时间（min） |

Gompertz 形式是修正 Gompertz 模型的 Zwietering 重参数化，三个参数可直接解释（渐近值、最大生长速率、延滞时间）——也是比较生长曲线时推荐使用的形式（Zwietering et al. 1990）。

拟合优度：

```
y_hat = f(x; p)
R² = 1 − Σ(y − y_hat)² / Σ(y − ȳ)²        (数据恒定、Σ(y−ȳ)² = 0 时为 NaN)
```

自动初值（`p0 is None`，仅两个生长模型）：

```
Gompertz: p0 = [1.1 · max(y), 0.5, x[argmax(y)]]
Logistic: p0 = [1.1 · max(y), 0.5, x[len(x)//2]]
```

`curve_fit` 没有给边界；若 `p0` 为 `None` 则用 SciPy 默认初值。拟合无权重、在线性 OD 空间进行，所有时间点等权。

### 参数与默认值

| 参数 | 默认值 | 位置 | 含义 |
|---|---|---|---|
| `path` / `--data` | 必填 | API/CLI | Excel/CSV 输入文件 |
| `output_dir` / `--output` | `output` | API/CLI | 输出目录（不存在则创建） |
| `sheet` | `None` | API（CLI 的 growth-curve 未暴露 `sheet`） | Excel 工作表名 |
| `time_col` | `time_min` | 类构造器 | 时间列名 |
| `od_col` | `od600` | 类构造器 | OD 列名 |
| `cfu_col` | `cfu_ml` | 类构造器 | CFU 列名 |
| `models` | `("Gompertz", "Logistic", "Quadratic")` | `fit_all()` | 尝试的模型 |
| `p0` | `None`（Gompertz/Logistic 自动） | `fit_curve()` | 初值参数 |
| `maxfev` | `20000` | `fit_curve()` | 最大函数评估次数 |

`run(data=None, path=None, ...)` 接受 `data` 仅为 API 兼容，实际忽略；没有 path 时抛 `ValueError("需要提供 path")`。

### 实现说明

* 包 `labtoolbox/growth_curve/`：`growth.py`（107 行）+ `common/fitting.py`（67 行）+ `common/io_utils.py`。
* `GrowthCurveAnalyzer` 方法：`load`、`load_from_lists`、`fit_all`、`plot`、`report`。依赖 NumPy、pandas、SciPy、matplotlib（Agg 后端）。
* 拟合用 `scipy.optimize.curve_fit`；R² 手算（不是 `scipy.stats.linregress`）。`fit_curve` 返回的协方差矩阵 `pcov` 被 `fit_all` 丢弃，因此不报告参数不确定度。
* 图上只画原始数据——**不叠加**拟合曲线，因此 R² 表是拟合结果唯一的可视化/数值联系。标题与轴标签为硬编码英文。
* GUI 标签页 **📈 生长曲线**（"打开范例表格"按钮打开 `examples/example_growth_curve.xlsx`）；命令行 `labtoolbox growth-curve --data ...`。

### 假设、局限与已知怪癖

* **只拟合 OD600。** CFU 数据只以 log10 画图、从不拟合；CFU = 0 会产生 `-inf` 与 matplotlib/NumPy 告警（无防护）。
* **Gompertz 默认初值对分钟量纲严重失配。** 硬编码 `μ0 = 0.5 OD·min⁻¹` 远高于典型批培养值（约 0.01–0.03 min⁻¹），延滞初值又取在 OD 最大处。对仓库自带 `data/examples/growth_Ecoli_example.csv`，Gompertz 收敛到退化解 `μ = 0.5、λ = 421 min`，**R² = −3.29**；而 Logistic 可达 R² = 0.999。务必查看 R²（并准备把时间换算成小时或通过 API 传 `p0`）。
* **图上不画拟合曲线**，因此仅凭 PNG 很难发现劣质拟合。
* **静默失败模式。** `curve_fit` 抛异常的模型被静默丢弃；若*所有*模型都失败，`fit_all` 返回空 DataFrame，随后 `sort_values("r_squared")` 抛 `KeyError`。
* **`params` 是无标签字符串**，4 位有效数字；精度与协方差都不保留。
* **拟合无权重且在实空间。** 无重复/误差棒、无按 CFU 精度加权、无 log-OD（指数相）拟合、无空白/光程校正、不读孔板或 OD 仪元数据。
* **除 R² 外没有模型选择统计**（无 AIC/BIC、无残差诊断、无置信区间）。
* 模型公式为标准经验式；不建模 Arrhenius/pH/温度依赖。

### 质控与验证

* 唯一内建质量指标是每个模型的 R²（数据恒定时为 NaN），另需人工判断排名第一的模型是否物理合理（`A`、`μ`、`k` 为正；`λ` 落在采样窗内）。
* 建议人工 QC：发表前用表中参数重画所选模型；把 Gompertz/Logistic 渐近值与观测平台比较；确认 `λ` 未钉在首/末采样点。
* commit `0e0508e` 的核对示例（Python 3.11、SciPy 1.17、NumPy 2.4，文件 `data/examples/growth_Ecoli_example.csv`）：Logistic R² = 0.9992（A = 1.496，k = 0.02855 min⁻¹，x0 = 181.6 min）、Quadratic R² = 0.9597、Gompertz R² = −3.29（见上述怪癖）；图与 CSV 均按描述生成。

### 参考文献

* Zwietering MH, Jongenburger I, Rombouts FM, van 't Riet K. Modeling of the bacterial growth curve. *Appl Environ Microbiol.* 1990;56(6):1875–1881. doi:10.1128/aem.56.6.1875-1881.1990.（修正 Gompertz 参数化，及 Logistic/Gompertz 模型比较）
* Virtanen P, et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. *Nat Methods.* 2020;17:261–272. doi:10.1038/s41592-019-0686-2.（`scipy.optimize.curve_fit`）
* McKinney W. Data structures for statistical computing in Python. *Proc 9th Python in Science Conf.* 2010:56–61.（模块使用的 pandas 表格 I/O）
* Verhulst PF. Notice sur la loi que la population suit dans son accroissement. *Correspondance Mathématique et Physique.* 1838;10:113–121.（原始逻辑斯蒂生长方程）
