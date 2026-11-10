# -*- coding: utf-8 -*-
"""
实验室工具箱 GUI 界面 (tkinter) - 支持中英文切换
- 9 个标签页, 每个模块一个独立配置面板
- 顶部 中/EN 切换按钮; 字体按平台自动选 (Windows 雅黑 / macOS PingFang / Linux Noto)
- 统一入口: python -m labtoolbox.gui
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from labtoolbox.growth_curve import run as gc_run
from labtoolbox.lipss_dloa import run as dloa_run
from labtoolbox.xdlvo import run as xdlvo_run
from labtoolbox.livedead import run as ld_run
from labtoolbox.contact_angle import run as ca_run
from labtoolbox.livedead_cellcounter import run as ldc_run
from labtoolbox.livedead_cellcounter.cellcounter import imagej_status
from labtoolbox.surfmetrics import run as sm_run
from labtoolbox.semtexture import run as stx_run
from labtoolbox.contact_schematic import run as schematic_run
from labtoolbox.common.fonts import pick_tk_font
from labtoolbox.i18n import tr


class LabToolboxApp:
    def __init__(self):
        self.lang = "zh"  # 'zh' | 'en'
        self._widgets = []  # (widget, text_key) 用于语言切换时刷新
        self._notebook_tabs = []  # (tab_frame, text_key) notebook 标签页标题

        self.root = tk.Tk()
        self.root.title("实验室工具箱 LabToolbox")
        self.root.geometry("780x580")
        self.root.configure(bg="#1e1e2e")
        self.root.attributes("-topmost", False)

        # 跨平台中文字体 (Windows 雅黑 / macOS PingFang / Linux Noto; 旧代码写死雅黑)
        self.font_family = pick_tk_font(self.root) or "TkDefaultFont"

        # 样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#1e1e2e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#313244", foreground="#cdd6f4",
                        padding=(16, 8), font=(self.font_family, 10))
        style.map("TNotebook.Tab", background=[("selected", "#89b4fa")],
                  foreground=[("selected", "#11111b")])
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabelframe", background="#181825", foreground="#cdd6f4")
        style.configure("TLabelframe.Label", background="#181825", foreground="#89b4fa",
                        font=(self.font_family, 10, "bold"))
        style.configure("TLabel", background="#181825", foreground="#cdd6f4",
                        font=(self.font_family, 10))
        style.configure("TButton", background="#45475a", foreground="#cdd6f4",
                        font=(self.font_family, 10), padding=(10, 6))
        style.map("TButton", background=[("active", "#585b70")])

        # 顶部栏: 标题 + 语言切换
        header = tk.Frame(self.root, bg="#1e1e2e")
        header.pack(fill="x", padx=10, pady=(8, 2))

        self.title_label = tk.Label(header, text=tr("🧪 实验室工具箱 LabToolbox", self.lang),
                                    bg="#1e1e2e", fg="#89b4fa",
                                    font=(self.font_family, 16, "bold"))
        self.title_label.pack(side="left")

        self.lang_btn = tk.Button(header, text="EN", command=self.toggle_lang,
                                  bg="#45475a", fg="#cdd6f4", relief="flat",
                                  activebackground="#89b4fa", activeforeground="#11111b",
                                  font=(self.font_family, 10, "bold"),
                                  cursor="hand2", padx=12, pady=2)
        self.lang_btn.pack(side="right")

        # 标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        self._build_all_tabs()
        self._fit_window_to_tabs()

        # 底部状态栏
        self.status_var = tk.StringVar(value=tr("就绪 - 选择一个模块配置并运行", self.lang))
        status = tk.Label(self.root, textvariable=self.status_var, bg="#1e1e2e",
                          fg="#a6e3a1", font=(self.font_family, 9), pady=6)
        status.pack(fill="x")

    def _fit_window_to_tabs(self):
        """按标签页标题实际宽度加宽窗口 (9 个标签页在旧 780px 下会被截断).

        只放宽, 不缩窄 (保留原 780x580 布局); 上限为屏幕可用宽度, 避免超出屏幕.
        """
        try:
            from tkinter import font as tkfont
            tab_font = tkfont.Font(family=self.font_family, size=10)
            need = sum(tab_font.measure(tr(text, self.lang)) + 36
                       for _, text in self._notebook_tabs) + 40
        except Exception:  # noqa: BLE001 - 量不出来就用原宽度
            need = 780
        screen = self.root.winfo_screenwidth() or need
        width = min(max(780, need), max(780, screen - 120))
        self.root.geometry(f"{width}x580")

    # ---------- 语言切换 ----------
    def toggle_lang(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self.lang_btn.config(text="中" if self.lang == "en" else "EN")
        self._refresh_all_texts()
        self._fit_window_to_tabs()
        self.status_var.set(tr("就绪 - 选择一个模块配置并运行", self.lang))

    def _refresh_all_texts(self):
        """刷新所有已注册控件的文本"""
        self.title_label.config(text=tr("🧪 实验室工具箱 LabToolbox", self.lang))
        for widget, key in self._widgets:
            try:
                widget.config(text=key(self.lang) if callable(key) else tr(key, self.lang))
            except Exception:
                pass
        # notebook 标签页标题需要专门 API 更新
        for tab_widget, key in self._notebook_tabs:
            try:
                self.notebook.tab(self.notebook.index(tab_widget), text=tr(key, self.lang))
            except Exception:
                pass

    def _T(self, text):
        """注册并返回翻译文本 (用于 Label/Button/Notebook tab)"""
        return tr(text, self.lang)

    # ---------- 通用组件 ----------
    def _file_row(self, parent, label, var, filetypes):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr(label, self.lang), width=18)
        lbl.pack(side="left")
        self._widgets.append((lbl, label))
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=4)
        btn = ttk.Button(row, text=tr("浏览...", self.lang),
                         command=lambda: var.set(filedialog.askopenfilename(filetypes=filetypes)))
        btn.pack(side="left")
        self._widgets.append((btn, "浏览..."))
        return row

    def _folder_row(self, parent, label, var):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr(label, self.lang), width=18)
        lbl.pack(side="left")
        self._widgets.append((lbl, label))
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=4)
        btn = ttk.Button(row, text=tr("浏览...", self.lang),
                         command=lambda: var.set(filedialog.askdirectory()))
        btn.pack(side="left")
        self._widgets.append((btn, "浏览..."))
        return row

    def _output_row(self, parent, var):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("输出目录", self.lang), width=18)
        lbl.pack(side="left")
        self._widgets.append((lbl, "输出目录"))
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=4)
        btn = ttk.Button(row, text=tr("浏览...", self.lang),
                         command=lambda: var.set(filedialog.askdirectory()))
        btn.pack(side="left")
        self._widgets.append((btn, "浏览..."))
        return row

    def _run_button(self, parent, text, callback):
        btn = ttk.Button(parent, text=tr(text, self.lang), command=callback)
        btn.pack(pady=10)
        self._widgets.append((btn, text))
        return btn

    def _open_example(self):
        """打开生长曲线范例表格"""
        self._open_example_file("example_growth_curve.xlsx")

    def _open_example_ld(self):
        """打开 LIVE/DEAD 范例表格"""
        self._open_example_file("example_livedead.xlsx")

    def _open_example_file(self, name):
        """用系统默认程序打开 examples 目录下的范例文件"""
        import subprocess
        # 源码运行: 仓库根/examples; PyInstaller 打包: _MEIPASS/examples
        candidates = []
        if getattr(sys, "frozen", False):
            candidates.append(sys._MEIPASS)  # type: ignore
        candidates.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = None
        for base in candidates:
            p = os.path.join(base, "examples", name)
            if os.path.exists(p):
                path = p
                break
        if path is None:
            messagebox.showwarning(tr("提示", self.lang),
                                   tr("范例文件不存在: ", self.lang) + " / ".join(candidates))
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as e:  # noqa: BLE001 - 打不开就用提示兜底
            messagebox.showwarning(tr("提示", self.lang),
                                   tr("无法打开范例文件: ", self.lang) + f"{path} ({e})")

    def _run_async(self, fn, *args, **kwargs):
        """后台线程运行, 完成后更新状态 (关键字参数原样透传给 fn)。

        旧实现只收 *args, 而各标签页都用关键字调用 → 点运行按钮会 TypeError;
        这里补齐 **kwargs, 并把异常消息先存成普通变量 (Python 3 的 except 变量
        在块结束时被删除, 直接闭包引用会 NameError)。
        """
        self.status_var.set(tr("⏳ 运行中...", self.lang))

        def worker():
            try:
                result = fn(*args, **kwargs)
                self.root.after(0, lambda: self.status_var.set(
                    tr("✅ 完成! 输出见输出目录", self.lang)))
                if isinstance(result, dict):
                    figure = result.get("figure")
                    if not figure:
                        figures = result.get("figures") or []
                        figure = figures[0] if figures else None
                    if figure:
                        self.root.after(0, lambda f=figure: messagebox.showinfo(
                            tr("完成", self.lang),
                            f"{tr('分析完成!', self.lang)}\n{tr('图表: ', self.lang)}{f}"))
            except Exception as e:  # noqa: BLE001
                msg = str(e) or e.__class__.__name__
                self.root.after(0, lambda: self.status_var.set(f"❌ {msg}"))
                self.root.after(0, lambda: messagebox.showerror(
                    tr("错误", self.lang), msg))

        threading.Thread(target=worker, daemon=True).start()

    # ---------- 标签页 ----------
    def _build_all_tabs(self):
        self._build_growth_tab()
        self._build_dloa_tab()
        self._build_xdlvo_tab()
        self._build_livedead_tab()
        self._build_contact_tab()
        self._build_livedead_counter_tab()
        self._build_surfmetrics_tab()
        self._build_semtexture_tab()
        self._build_schematic_tab()

    def _build_growth_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("📈 生长曲线", self.lang))
        self._notebook_tabs.append((tab, "📈 生长曲线"))  # notebook tab 文本单独处理
        inner = ttk.LabelFrame(tab, text=tr("细菌生长曲线拟合 (OD600 / CFU)", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "细菌生长曲线拟合 (OD600 / CFU)"))

        self.gc_file = tk.StringVar()
        self._file_row(inner, "数据文件", self.gc_file,
                       [("Excel/CSV", "*.xlsx *.xls *.csv")])
        # 范例表格提示
        row = ttk.Frame(inner); row.pack(fill="x", pady=2)
        lbl = ttk.Label(row, text=tr("范例: ", self.lang), foreground="#a6adc8")
        lbl.pack(side="left"); self._widgets.append((lbl, "范例: "))
        ttk.Label(row, text="time_min, od600, cfu_ml", foreground="#f9e2af").pack(side="left")
        btn = ttk.Button(row, text=tr("打开范例表格", self.lang), command=self._open_example)
        btn.pack(side="left", padx=8)
        self._widgets.append((btn, "打开范例表格"))
        self.gc_out = tk.StringVar(value="output")
        self._output_row(inner, self.gc_out)
        self._run_button(inner, "🚀 运行生长曲线分析",
                         lambda: self._run_async(gc_run, path=self.gc_file.get(),
                                                 output_dir=self.gc_out.get()))

    def _build_dloa_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("🔬 LIPSS/DLOA", self.lang))
        self._notebook_tabs.append((tab, "🔬 LIPSS/DLOA"))
        inner = ttk.LabelFrame(tab, text=tr("SEM 图像 LIPSS 周期与取向角分析", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "SEM 图像 LIPSS 周期与取向角分析"))

        self.dloa_folder = tk.StringVar()
        self._folder_row(inner, "SEM 图像文件夹", self.dloa_folder)
        row = ttk.Frame(inner)
        row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("每微米像素数", self.lang), width=18)
        lbl.pack(side="left")
        self._widgets.append((lbl, "每微米像素数"))
        self.dloa_ppm = tk.StringVar(value="32.0")
        ttk.Entry(row, textvariable=self.dloa_ppm, width=12).pack(side="left", padx=4)
        lbl = ttk.Label(row, text=tr("(31.25 nm/px = 32)", self.lang), foreground="#a6adc8")
        lbl.pack(side="left"); self._widgets.append((lbl, "(31.25 nm/px = 32)"))
        self.dloa_out = tk.StringVar(value="output")
        self._output_row(inner, self.dloa_out)
        self._run_button(inner, "🚀 运行 DLOA 分析",
                         lambda: self._run_async(
                             dloa_run, folder=self.dloa_folder.get(),
                             output_dir=self.dloa_out.get(),
                             pixel_size_um=1.0 / float(self.dloa_ppm.get())))

    def _build_semtexture_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("🧭 织构一致性", self.lang))
        self._notebook_tabs.append((tab, "🧭 织构一致性"))
        inner = ttk.LabelFrame(tab, text=tr("SEM 织构一致性与合格区面积", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "SEM 织构一致性与合格区面积"))

        self.stx_folder = tk.StringVar()
        self._folder_row(inner, "SEM 图像根目录（子文件夹=分组）", self.stx_folder)

        row = ttk.Frame(inner)
        row.pack(fill="x", pady=4)
        for label, var, width, key in [
                ("像素尺寸 nm（空=自动）", "31.25", 10, "像素尺寸 nm（空=自动）"),
                ("判定窗边长 (µm)", "2", 8, "判定窗边长 (µm)")]:
            lbl = ttk.Label(row, text=tr(label, self.lang), width=22)
            lbl.pack(side="left")
            self._widgets.append((lbl, key))
            v = tk.StringVar(value=var)
            ttk.Entry(row, textvariable=v, width=width).pack(side="left", padx=(0, 12))
            if key.startswith("像素"):
                self.stx_pxnm = v
            else:
                self.stx_tile = v

        self.stx_out = tk.StringVar(value="output")
        self._output_row(inner, self.stx_out)
        self._run_button(inner, "🚀 运行一致性分析",
                         lambda: self._run_async(
                             stx_run, folder=self.stx_folder.get(),
                             output_dir=self.stx_out.get(),
                             pixel_nm=(float(self.stx_pxnm.get()) if self.stx_pxnm.get().strip() else None),
                             tile_um=float(self.stx_tile.get() or 4)))

    def _build_xdlvo_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("🧫 XDLVO", self.lang))
        self._notebook_tabs.append((tab, "🧫 XDLVO"))
        inner = ttk.LabelFrame(tab, text=tr("XDLVO 细菌粘附预测", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "XDLVO 细菌粘附预测"))

        row = ttk.Frame(inner); row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("θ 二碘甲烷 (°)", self.lang), width=18)
        lbl.pack(side="left"); self._widgets.append((lbl, "θ 二碘甲烷 (°)"))
        self.xd_t1 = tk.StringVar(value="48.2")
        ttk.Entry(row, textvariable=self.xd_t1, width=10).pack(side="left")

        row = ttk.Frame(inner); row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("θ 水 (°)", self.lang), width=18)
        lbl.pack(side="left"); self._widgets.append((lbl, "θ 水 (°)"))
        self.xd_t2 = tk.StringVar(value="72.3")
        ttk.Entry(row, textvariable=self.xd_t2, width=10).pack(side="left")

        row = ttk.Frame(inner); row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("θ 甲酰胺 (°)", self.lang), width=18)
        lbl.pack(side="left"); self._widgets.append((lbl, "θ 甲酰胺 (°)"))
        self.xd_t3 = tk.StringVar(value="61.5")
        ttk.Entry(row, textvariable=self.xd_t3, width=10).pack(side="left")

        row = ttk.Frame(inner); row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("细菌半径 (nm)", self.lang), width=18)
        lbl.pack(side="left"); self._widgets.append((lbl, "细菌半径 (nm)"))
        self.xd_r = tk.StringVar(value="500")
        ttk.Entry(row, textvariable=self.xd_r, width=10).pack(side="left")
        lbl = ttk.Label(row, text=tr("离子强度 (M)", self.lang), foreground="#a6adc8")
        lbl.pack(side="left", padx=(12, 0)); self._widgets.append((lbl, "离子强度 (M)"))
        self.xd_i = tk.StringVar(value="0.01")
        ttk.Entry(row, textvariable=self.xd_i, width=10).pack(side="left")

        self.xd_out = tk.StringVar(value="output")
        self._output_row(inner, self.xd_out)
        self._run_button(inner, "🚀 运行 XDLVO 分析",
                         lambda: self._run_async(
                             xdlvo_run,
                             contact_angles=(float(self.xd_t1.get()),
                                             float(self.xd_t2.get()),
                                             float(self.xd_t3.get())),
                             radius_nm=float(self.xd_r.get()),
                             I_M=float(self.xd_i.get()),
                             output_dir=self.xd_out.get()))

    def _build_livedead_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("🦠 LIVE/DEAD", self.lang))
        self._notebook_tabs.append((tab, "🦠 LIVE/DEAD"))
        inner = ttk.LabelFrame(tab, text=tr("LIVE/DEAD 存活率统计 + 双因素 ANOVA", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "LIVE/DEAD 存活率统计 + 双因素 ANOVA"))

        self.ld_file = tk.StringVar()
        self._file_row(inner, "数据文件", self.ld_file,
                       [("Excel/CSV", "*.xlsx *.xls *.csv")])
        # 范例表格提示
        row = ttk.Frame(inner); row.pack(fill="x", pady=2)
        lbl = ttk.Label(row, text=tr("范例: ", self.lang), foreground="#a6adc8")
        lbl.pack(side="left"); self._widgets.append((lbl, "范例: "))
        ttk.Label(row, text="group, time, repeat, live, dead", foreground="#f9e2af").pack(side="left")
        btn = ttk.Button(row, text=tr("打开范例表格", self.lang), command=self._open_example_ld)
        btn.pack(side="left", padx=8)
        self._widgets.append((btn, "打开范例表格"))
        row = ttk.Frame(inner); row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("工作表名 (可选)", self.lang), width=18)
        lbl.pack(side="left"); self._widgets.append((lbl, "工作表名 (可选)"))
        self.ld_sheet = tk.StringVar()
        ttk.Entry(row, textvariable=self.ld_sheet, width=20).pack(side="left", padx=4)
        self.ld_out = tk.StringVar(value="output")
        self._output_row(inner, self.ld_out)
        self._run_button(inner, "🚀 运行 LIVE/DEAD 分析",
                         lambda: self._run_async(
                             ld_run, path=self.ld_file.get(),
                             sheet=self.ld_sheet.get() or None,
                             output_dir=self.ld_out.get()))

    def _build_contact_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("💧 接触角/表面能", self.lang))
        self._notebook_tabs.append((tab, "💧 接触角/表面能"))
        inner = ttk.LabelFrame(tab, text=tr("OWRK 表面自由能计算", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "OWRK 表面自由能计算"))

        row = ttk.Frame(inner); row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("液体1 接触角 (°)", self.lang), width=18)
        lbl.pack(side="left"); self._widgets.append((lbl, "液体1 接触角 (°)"))
        self.ca_t1 = tk.StringVar(value="72.3")
        ttk.Entry(row, textvariable=self.ca_t1, width=10).pack(side="left")
        lbl2 = ttk.Label(row, text=tr("液体1", self.lang), foreground="#a6adc8")
        lbl2.pack(side="left", padx=(12, 0)); self._widgets.append((lbl2, "液体1"))
        self.ca_l1 = tk.StringVar(value="water")
        ttk.Combobox(row, textvariable=self.ca_l1, width=14,
                     values=["water", "diiodomethane", "formamide", "glycerol", "ethylene_glycol"]).pack(side="left")

        row = ttk.Frame(inner); row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("液体2 接触角 (°)", self.lang), width=18)
        lbl.pack(side="left"); self._widgets.append((lbl, "液体2 接触角 (°)"))
        self.ca_t2 = tk.StringVar(value="48.2")
        ttk.Entry(row, textvariable=self.ca_t2, width=10).pack(side="left")
        lbl2 = ttk.Label(row, text=tr("液体2", self.lang), foreground="#a6adc8")
        lbl2.pack(side="left", padx=(12, 0)); self._widgets.append((lbl2, "液体2"))
        self.ca_l2 = tk.StringVar(value="diiodomethane")
        ttk.Combobox(row, textvariable=self.ca_l2, width=14,
                     values=["water", "diiodomethane", "formamide", "glycerol", "ethylene_glycol"]).pack(side="left")

        self._run_button(inner, "🚀 计算表面能",
                         lambda: self._run_async(
                             ca_run, theta1=float(self.ca_t1.get()),
                             theta2=float(self.ca_t2.get()),
                             liquid1=self.ca_l1.get(), liquid2=self.ca_l2.get()))

    def _build_livedead_counter_tab(self):
        """荧光显微镜 LIVE/DEAD 细胞计数 (repeat 文件夹结构)"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("🔬 LIVE/DEAD 细胞计数", self.lang))
        self._notebook_tabs.append((tab, "🔬 LIVE/DEAD 细胞计数"))
        inner = ttk.LabelFrame(tab, text=tr(
            "荧光图像计数: repeat1/2/3 → 1h/3h → area-channelN", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "荧光图像计数: repeat1/2/3 → 1h/3h → area-channelN"))

        self.ldc_folder = tk.StringVar()
        self._folder_row(inner, "图像根文件夹", self.ldc_folder)

        # 结构说明
        tip = ttk.Label(inner, foreground="#a6adc8", wraplength=650, justify="left",
                        text=tr("结构: 根文件夹/repeat1/1h/1-g1.tif (g=活菌) + 1-r1.tif (r=死菌)\n"
                                "文件名: {区域}-{g|r}{编号}, 区域 c=Control, 1/2/3=测试区\n"
                                "引擎: imagej (默认方法学: ImageJ 1.54 自适应阈值 + Analyze Particles) / "
                                "opencv (旧 Python 引擎, 仅排查对照; 阈值/圆形度只对它生效)", self.lang))
        tip.pack(fill="x", padx=8, pady=4)
        self._widgets.append((tip, "结构: 根文件夹/repeat1/1h/1-g1.tif (g=活菌) + 1-r1.tif (r=死菌)\n"
                                   "文件名: {区域}-{g|r}{编号}, 区域 c=Control, 1/2/3=测试区\n"
                                   "引擎: imagej (默认方法学: ImageJ 1.54 自适应阈值 + Analyze Particles) / "
                                   "opencv (旧 Python 引擎, 仅排查对照; 阈值/圆形度只对它生效)"))

        # 引擎选择: imagej = 默认方法学口径; opencv = 旧 Python 引擎, 仅排查/回归对照
        erow = ttk.Frame(inner)
        erow.pack(fill="x", pady=3)
        elbl = ttk.Label(erow, text=tr("计数引擎", self.lang), width=14)
        elbl.pack(side="left")
        self._widgets.append((elbl, "计数引擎"))
        self.ldc_backend = tk.StringVar(value="imagej")
        ttk.Combobox(erow, textvariable=self.ldc_backend, width=10, state="readonly",
                     values=["imagej", "opencv"]).pack(side="left")
        self.ldc_ij_status = ttk.Label(erow, text=self._imagej_status_text(),
                                       foreground="#a6adc8")
        self.ldc_ij_status.pack(side="left", padx=(12, 0))
        self._widgets.append((self.ldc_ij_status, self._imagej_status_text))

        # 参数 (可调)
        row = ttk.Frame(inner); row.pack(fill="x", pady=3)
        lbl = ttk.Label(row, text=tr("最小面积(px)", self.lang), width=14)
        lbl.pack(side="left"); self._widgets.append((lbl, "最小面积(px)"))
        self.ldc_min = tk.StringVar(value="4")
        ttk.Entry(row, textvariable=self.ldc_min, width=8).pack(side="left")
        lbl = ttk.Label(row, text=tr("圆形度", self.lang), width=10)
        lbl.pack(side="left", padx=(10, 0)); self._widgets.append((lbl, "圆形度"))
        self.ldc_round = tk.StringVar(value="0.4")
        ttk.Entry(row, textvariable=self.ldc_round, width=8).pack(side="left")
        lbl = ttk.Label(row, text=tr("绿阈值", self.lang), width=10)
        lbl.pack(side="left", padx=(10, 0)); self._widgets.append((lbl, "绿阈值"))
        self.ldc_gt = tk.StringVar(value="15")
        ttk.Entry(row, textvariable=self.ldc_gt, width=8).pack(side="left")
        lbl = ttk.Label(row, text=tr("红阈值", self.lang), width=10)
        lbl.pack(side="left", padx=(10, 0)); self._widgets.append((lbl, "红阈值"))
        self.ldc_rt = tk.StringVar(value="15")
        ttk.Entry(row, textvariable=self.ldc_rt, width=8).pack(side="left")

        self.ldc_out = tk.StringVar(value="output")
        self._output_row(inner, self.ldc_out)

        def _run_counter():
            # 只传当前引擎用得到的参数 (imagej 用不上阈值/圆形度; 方法学未改动)
            backend = self.ldc_backend.get()
            engine_kw = {"min_size": int(self.ldc_min.get())}
            if backend == "opencv":
                engine_kw.update(min_roundness=float(self.ldc_round.get()),
                                 green_thresh=int(self.ldc_gt.get()),
                                 red_thresh=int(self.ldc_rt.get()))
            self._run_async(ldc_run, folder=self.ldc_folder.get(),
                            output_dir=self.ldc_out.get(),
                            backend=backend, **engine_kw)

        self._run_button(inner, "🚀 运行细胞计数分析", _run_counter)

    def _build_surfmetrics_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("🏔️ 表面形貌", self.lang))
        self._notebook_tabs.append((tab, "🏔️ 表面形貌"))
        inner = ttk.LabelFrame(
            tab,
            text=tr("AFM/SEM 高度图 → 3D 图 + 粗糙度 (Sa/Sq/Sz) + 表面积 (Sdr)", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append(
            (inner, "AFM/SEM 高度图 → 3D 图 + 粗糙度 (Sa/Sq/Sz) + 表面积 (Sdr)"))

        self.sm_file = tk.StringVar()
        self._file_row(inner, "高度图文件", self.sm_file,
                       [("AFM/高度图", "*.ibw *.tif *.tiff *.txt *.xyz *.csv")])
        self.sm_folder = tk.StringVar()
        self._folder_row(inner, "批量文件夹 (.ibw)", self.sm_folder)

        row = ttk.Frame(inner)
        row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("通道 (空=自动)", self.lang), width=18)
        lbl.pack(side="left")
        self._widgets.append((lbl, "通道 (空=自动)"))
        self.sm_ch = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.sm_ch, width=12).pack(side="left", padx=4)

        row = ttk.Frame(inner)
        row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("像素尺寸 X (nm, 空=自动)", self.lang), width=18)
        lbl.pack(side="left")
        self._widgets.append((lbl, "像素尺寸 X (nm, 空=自动)"))
        self.sm_px = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.sm_px, width=12).pack(side="left", padx=4)
        lbl_ibw = ttk.Label(row, text=tr("(.ibw 自动读取)", self.lang), foreground="#a6adc8")
        lbl_ibw.pack(side="left")
        self._widgets.append((lbl_ibw, "(.ibw 自动读取)"))

        self.sm_out = tk.StringVar(value="output")
        self._output_row(inner, self.sm_out)
        self._run_button(
            inner, "🚀 运行表面分析",
            lambda: self._run_async(
                sm_run,
                file=self.sm_file.get().strip() or None,
                folder=self.sm_folder.get().strip() or None,
                channel=int(self.sm_ch.get()) if self.sm_ch.get().strip() else None,
                px=float(self.sm_px.get()) if self.sm_px.get().strip() else None,
                py=None,
                output_dir=self.sm_out.get()))

    def _build_schematic_tab(self):
        """AFM 流程末端: 实测几何 → 细菌黏附 3D 示意图 + 接触几何图 (第 9 标签页)"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("📐 接触几何示意", self.lang))
        self._notebook_tabs.append((tab, "📐 接触几何示意"))
        inner = ttk.LabelFrame(tab, text=tr("细菌-织构接触几何示意图 (AFM 流程末端)", self.lang))
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        self._widgets.append((inner, "细菌-织构接触几何示意图 (AFM 流程末端)"))

        self.sc_folder = tk.StringVar()
        self._folder_row(inner, "AFM 数据目录", self.sc_folder)

        row = ttk.Frame(inner)
        row.pack(fill="x", pady=4)
        lbl = ttk.Label(row, text=tr("样品标签", self.lang), width=18)
        lbl.pack(side="left")
        self._widgets.append((lbl, "样品标签"))
        self.sc_label = tk.StringVar(value="515 nm")
        ttk.Entry(row, textvariable=self.sc_label, width=12).pack(side="left", padx=4)
        lbl2 = ttk.Label(row, text=tr("(进标题, 如 515 nm)", self.lang), foreground="#a6adc8")
        lbl2.pack(side="left")
        self._widgets.append((lbl2, "(进标题, 如 515 nm)"))

        tip = ttk.Label(inner, foreground="#a6adc8", wraplength=650, justify="left",
                        text=tr("输出: fig1/2/3 接触示意图 + geometry_measurements.csv + README.md", self.lang))
        tip.pack(fill="x", padx=8, pady=4)
        self._widgets.append((tip, "输出: fig1/2/3 接触示意图 + geometry_measurements.csv + README.md"))

        self.sc_out = tk.StringVar(value="output")
        self._output_row(inner, self.sc_out)
        self._run_button(inner, "🚀 运行接触几何示意",
                         lambda: self._run_async(
                             schematic_run,
                             folder=self.sc_folder.get(),
                             output_dir=self.sc_out.get(),
                             label=self.sc_label.get().strip() or "515 nm"))

    def _imagej_status_text(self, lang=None):
        """ImageJ 探测状态 (细胞计数标签页提示; 语言切换时作为 callable 刷新)."""
        lang = lang or self.lang
        try:
            st = imagej_status()
        except Exception:  # noqa: BLE001 - 状态提示失败不影响使用
            st = {"found": False, "dir": None}
        if st.get("found") and st.get("dir"):
            return f"ImageJ: {st['dir']}"
        return "ImageJ: " + tr("未找到 (可设 LABTOOLBOX_IMAGEJ_DIR)", lang)

    def run(self):
        self.root.mainloop()


def main():
    app = LabToolboxApp()
    app.run()


if __name__ == "__main__":
    main()
