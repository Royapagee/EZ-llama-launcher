import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from ttkbootstrap.widgets import ToolTip
from tkinter import filedialog, messagebox
import tkinter as tk
import json
import os
import sys
import subprocess
import threading
import queue
import webbrowser
import winreg
from pathlib import Path


def get_resource_path(relative_path):
    """获取资源文件路径，兼容开发环境和 PyInstaller 打包环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def get_config_path():
    """获取配置文件路径，优先使用 exe 所在目录（支持持久化读写）"""
    if hasattr(sys, '_MEIPASS'):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, "config.json")
    return os.path.join(os.path.abspath("."), "config.json")


CONFIG_FILE = get_config_path()
ICON_PATH = get_resource_path("ico/logo.ico")

DEFAULT_CONFIG = {
    "LlamaPath": "",
    "ModelPath": "",
    "ModelFilePath": "",
    "MmprojPath": "",
    "ThemeMode": "auto",
    "Params": {}
}

THEME_MAP = {
    "dark": "darkly",
    "light": "flatly"
}

LOG_COLORS = {
    "dark": {"bg": "#1e1e1e", "fg": "#eeeeee"},
    "light": {"bg": "#f8f9fa", "fg": "#212529"}
}

TARGET_URL = "http://127.0.0.1:8080"

PARAM_GROUPS = [
    ("模型加载参数", [
        ("model", "-m", "本地 GGUF 模型文件路径（覆盖下方下拉选择）"),
        ("hf", "-hf", "Hugging Face Hub 模型（格式：用户/仓库:量化标签）"),
        ("model_url", "-mu", "远程 URL 加载模型"),
        ("alias", "--alias", "模型别名"),
    ]),
    ("网络与服务参数", [
        ("host", "--host", "监听地址（默认 127.0.0.1；0.0.0.0 允许所有网访问）"),
        ("port", "--port", "监听端口（默认 8080）"),
        ("api_key", "--api-key", "API Key（请求需携带 Authorization: Bearer <key>）"),
        ("timeout", "--timeout", "读写超时时间（秒）"),
        ("metrics", "--metrics", "启用 /metrics 端点（输入任意值启用）"),
    ]),
    ("性能与硬件参数", [
        ("ngl", "-ngl", "GPU 层数（99 通常可将所有层放入 GPU）"),
        ("ctx_size", "-c", "上下文窗口大小（token 数）"),
        ("parallel", "-np", "并行请求槽位数"),
        ("threads", "-t", "CPU 推理线程数"),
        ("batch_size", "-b", "批处理大小"),
        ("ubatch_size", "-ub", "微批次大小"),
        ("flash_attn", "-fa", "启用 Flash Attention（输入任意值启用）"),
        ("cache_prompt", "--cache-prompt", "启用 prompt 缓存（输入任意值启用）"),
        ("cache_reuse", "--cache-reuse", "缓存复用的 token 数量"),
        ("cache_type_k", "-ctk", "Key 缓存量化类型（q4_0 / q8_0 / f16）"),
        ("cache_type_v", "-ctv", "Value 缓存量化类型"),
        ("no_mmap", "--no-mmap", "禁用内存映射（输入任意值启用）"),
        ("split_mode", "--split-mode", "多卡切分模式（none / layer / row）"),
        ("tensor_split", "--tensor-split", "多卡显存分配比例（如 7,8）"),
    ]),
    ("采样与生成参数", [
        ("temp", "--temp", "温度（0=确定性，越高越随机；默认 0.8）"),
        ("top_k", "--top-k", "Top-K 采样（默认 40）"),
        ("top_p", "--top-p", "Top-P 核采样（默认 1.0）"),
        ("min_p", "--min-p", "最小概率阈值（默认 0.0）"),
        ("repeat_penalty", "--repeat-penalty", "重复惩罚系数（默认 1.0）"),
        ("presence_penalty", "--presence-penalty", "存在惩罚（默认 0.0）"),
        ("predict", "-n", "最大生成 token 数（默认 -1）"),
        ("seed", "--seed", "随机种子（默认 -1）"),
    ]),
    ("模板与格式化参数", [
        ("jinja", "--jinja", "使用 Jinja 模板引擎（输入即启用）"),
        ("chat_template", "--chat-template", "聊天模板（llama3 / chatml / llama2）"),
        ("chat_template_kwargs", "--chat-template-kwargs", "模板额外参数（JSON 格式）"),
    ]),
    ("多模型 Router 模式参数", [
        ("models_dir", "--models-dir", "本地 GGUF 模型目录（不指定 -m 时进入 Router 模式）"),
        ("models_max", "--models-max", "同时驻留内存的最大模型数"),
        ("models_preset", "--models-preset", "预设配置文件路径（.ini）"),
        ("cache_list", "-cl", "列出缓存中的模型（输入任意值启用）"),
    ]),
    ("日志与调试参数", [
        ("verbose", "-v", "启用详细日志（输入任意值启用）"),
        ("log_verbosity", "-lv", "日志详细级别（0-4）"),
        ("log_timestamps", "--log-timestamps", "日志输出时间戳（输入任意值启用）"),
        ("log_colors", "--log-colors", "日志着色（auto / on / off）"),
        ("props", "--props", "启用 /props 端点（输入任意值启用）"),
    ]),
]

FLAG_PARAMS = {
    "metrics", "flash_attn", "cache_prompt", "no_mmap", "jinja",
    "cache_list", "verbose", "log_timestamps", "props"
}

# 模块级模型扫描缓存: {path: (mtime, files_list)}
_MODEL_SCAN_CACHE = {}


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                if not isinstance(config.get("Params"), dict):
                    config["Params"] = {}
                return config
        except Exception as e:
            messagebox.showerror("配置错误", f"读取配置文件失败: {e}")
    return DEFAULT_CONFIG.copy()


_last_saved_json = None


def save_config(config):
    """保存配置文件（按固定键顺序输出，内容未变化时跳过实际写盘）"""
    global _last_saved_json
    try:
        key_order = [
            "LlamaPath", "ModelPath", "ModelFilePath", "MmprojPath",
            "ThemeMode", "Params"
        ]
        ordered = {}
        for k in key_order:
            if k in config:
                ordered[k] = config[k]
        for k, v in config.items():
            if k not in ordered:
                ordered[k] = v
        payload = json.dumps(ordered, ensure_ascii=False, indent=4)
        if payload == _last_saved_json:
            return
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(payload)
        _last_saved_json = payload
    except Exception as e:
        messagebox.showerror("配置错误", f"保存配置文件失败: {e}")


def get_system_theme():
    """检测 Windows 系统主题，返回 'dark' 或 'light'"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"


def resolve_theme_mode(config):
    """根据配置确定实际使用的主题模式"""
    mode = config.get("ThemeMode", "auto")
    if mode == "auto":
        return get_system_theme()
    return mode if mode in THEME_MAP else "dark"


def get_model_files(path):
    """
    获取指定路径下的模型文件列表。
    使用 os.scandir 单次递归扫描替代多次 rglob，并基于目录修改时间缓存结果。
    """
    if not path or not os.path.isdir(path):
        return []

    abs_path = os.path.abspath(path)
    try:
        current_mtime = os.path.getmtime(abs_path)
    except OSError:
        current_mtime = 0

    # 检查缓存是否有效
    cached = _MODEL_SCAN_CACHE.get(abs_path)
    if cached is not None:
        cached_mtime, cached_files = cached
        if current_mtime == cached_mtime:
            return cached_files

    # 单次扫描所有目标扩展名
    extensions = (".gguf", ".bin", ".safetensors", ".pt", ".pth", ".ckpt")
    files = []
    append = files.append
    for root, _dirs, filenames in os.walk(abs_path):
        for name in filenames:
            if name.endswith(extensions):
                append(os.path.join(root, name))

    result = sorted(files)
    _MODEL_SCAN_CACHE[abs_path] = (current_mtime, result)
    return result


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.current_theme_mode = resolve_theme_mode(self.config)

        self.root.title("EZ-llama-launcher")
        self.root.geometry("900x820")
        self.root.resizable(True, False)
        self.root.place_window_center()

        self.process = None
        self.monitor_thread = None
        self.is_running = False
        self.url_opened = False
        self.target_url = TARGET_URL
        self.current_page = None

        # 日志队列与批量刷新控制
        self.log_queue = queue.Queue()
        self._log_after_id = None
        self._save_after_id = None

        # 参数页面延迟构建标记
        self._param_page_built = False

        # 初始化参数字典
        self.param_vars = {}
        params_config = self.config.get("Params", {})
        for group_name, params in PARAM_GROUPS:
            for key, flag, desc in params:
                var = ttk.StringVar(value=params_config.get(key, ""))
                self.param_vars[key] = var

        self._build_ui()
        self._apply_theme(self.current_theme_mode, save=False)
        self._refresh_model_list()

    def _build_ui(self):
        # 主容器
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        # === 顶部固定区域：标题 ===
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 10))

        # 标题
        left_frame = ttk.Frame(header_frame)
        left_frame.pack(side=LEFT, fill=Y)

        ttk.Label(
            left_frame,
            text="EZ-llama-launcher",
            font=("Microsoft YaHei UI", 20, "bold"),
            bootstyle="primary"
        ).pack(anchor=W)
        self.secondary_labels = []
        subtitle = ttk.Label(
            left_frame,
            text="简易 Llama.cpp 模型启动器",
            font=("Microsoft YaHei UI", 11),
            bootstyle="secondary"
        )
        subtitle.pack(anchor=W, pady=(2, 0))
        self.secondary_labels.append(subtitle)

        ttk.Separator(main_frame, bootstyle="secondary").pack(fill=X, pady=(0, 10))

        # === 页面切换按钮 + 右侧功能按钮 ===
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill=X, pady=(0, 10))

        self.nav_basic_btn = ttk.Button(
            nav_frame,
            text="基本设置",
            command=lambda: self._show_page("basic"),
            bootstyle="primary",
            width=12
        )
        self.nav_basic_btn.pack(side=LEFT, padx=(0, 8))

        self.nav_param_btn = ttk.Button(
            nav_frame,
            text="参数配置",
            command=lambda: self._show_page("param"),
            bootstyle="outline-secondary",
            width=12
        )
        self.nav_param_btn.pack(side=LEFT)

        # 右侧按钮（主题 + 启动/停止 + 打开服务）
        right_frame = ttk.Frame(nav_frame)
        right_frame.pack(side=RIGHT, fill=Y)

        self.theme_btn = ttk.Button(
            right_frame,
            text="🌙 暗色",
            command=self._toggle_theme,
            bootstyle="outline-secondary",
            width=10
        )
        self.theme_btn.pack(side=LEFT, padx=(0, 8))

        self.action_btn = ttk.Button(
            right_frame,
            text="▶ 启动",
            command=self._start_server,
            bootstyle="success",
            width=12
        )
        self.action_btn.pack(side=LEFT)

        self.open_url_btn = ttk.Button(
            right_frame,
            text="🌐 打开服务",
            command=self._open_browser,
            bootstyle="info",
            width=12,
            state=DISABLED
        )
        self.open_url_btn.pack(side=RIGHT, padx=(8, 0))

        # === 内容区域（可切换）===
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=BOTH, expand=YES)

        # 基本设置页面
        self.basic_page = ttk.Frame(self.content_frame, padding=5)
        self._build_basic_page(self.basic_page)

        # 参数配置页面（延迟构建）
        self.param_page = ttk.Frame(self.content_frame, padding=5)

        # 默认显示基本设置
        self._show_page("basic")

    def _show_page(self, page_name):
        """切换显示基本设置或参数配置页面"""
        if self.current_page == page_name:
            return
        self.current_page = page_name

        self.basic_page.pack_forget()
        self.param_page.pack_forget()

        if page_name == "basic":
            self.basic_page.pack(fill=BOTH, expand=YES)
            self.nav_basic_btn.configure(bootstyle="primary")
            self.nav_param_btn.configure(bootstyle="outline-secondary")
        else:
            # 延迟构建参数页面
            if not self._param_page_built:
                self._build_param_page(self.param_page)
                self._param_page_built = True
            self.param_page.pack(fill=BOTH, expand=YES)
            self.nav_basic_btn.configure(bootstyle="outline-secondary")
            self.nav_param_btn.configure(bootstyle="primary")

    def _build_basic_page(self, parent):
        """构建基本设置页面内容"""
        # === LlamaPath ===
        ttk.Label(parent, text="llama.cpp 路径", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(0, 4))
        llama_frame = ttk.Frame(parent)
        llama_frame.pack(fill=X, pady=(0, 12))
        llama_frame.columnconfigure(0, weight=1)

        self.llama_var = ttk.StringVar(value=self.config.get("LlamaPath", ""))
        self.llama_entry = ttk.Entry(llama_frame, textvariable=self.llama_var, bootstyle="primary")
        self.llama_entry.grid(row=0, column=0, sticky=EW, padx=(0, 8))

        ttk.Button(
            llama_frame, text="浏览...", command=self._browse_llama,
            bootstyle="outline-primary", width=10
        ).grid(row=0, column=1)

        # === ModelPath ===
        ttk.Label(parent, text="模型文件夹路径", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(0, 4))
        model_frame = ttk.Frame(parent)
        model_frame.pack(fill=X, pady=(0, 12))
        model_frame.columnconfigure(0, weight=1)

        self.model_dir_var = ttk.StringVar(value=self.config.get("ModelPath", ""))
        self.model_dir_entry = ttk.Entry(model_frame, textvariable=self.model_dir_var, bootstyle="primary")
        self.model_dir_entry.grid(row=0, column=0, sticky=EW, padx=(0, 8))

        ttk.Button(
            model_frame, text="浏览...", command=self._browse_model_dir,
            bootstyle="outline-primary", width=10
        ).grid(row=0, column=1)

        # === 模型文件选择 ===
        ttk.Label(parent, text="选择模型文件", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(8, 4))
        combo_frame = ttk.Frame(parent)
        combo_frame.pack(fill=X, pady=(0, 12))
        combo_frame.columnconfigure(0, weight=1)

        self.model_combo = ttk.Combobox(combo_frame, state="readonly", bootstyle="primary")
        self.model_combo.grid(row=0, column=0, sticky=EW, padx=(0, 8))

        ttk.Button(
            combo_frame, text="刷新", command=self._refresh_model_list,
            bootstyle="outline-secondary", width=10
        ).grid(row=0, column=1)

        # === 多模态投影层 ===
        mmproj_label_frame = ttk.Frame(parent)
        mmproj_label_frame.pack(anchor=W, pady=(8, 0))
        ttk.Label(
            mmproj_label_frame, text="多模态投影层",
            font=("Microsoft YaHei UI", 10, "bold")
        ).pack(side=LEFT)
        mmproj_desc_lbl = ttk.Label(
            mmproj_label_frame,
            text="为例如Gemma4之类的模型提供多模态支持",
            font=("Microsoft YaHei UI", 9),
            bootstyle="secondary"
        )
        mmproj_desc_lbl.pack(side=LEFT, padx=(8, 0))
        self.secondary_labels.append(mmproj_desc_lbl)

        mmproj_combo_frame = ttk.Frame(parent)
        mmproj_combo_frame.pack(fill=X, pady=(0, 12))
        mmproj_combo_frame.columnconfigure(0, weight=1)

        self.mmproj_combo = ttk.Combobox(mmproj_combo_frame, state="readonly", bootstyle="primary")
        self.mmproj_combo.grid(row=0, column=0, sticky=EW, padx=(0, 8))

        ttk.Button(
            mmproj_combo_frame, text="刷新", command=self._refresh_model_list,
            bootstyle="outline-secondary", width=10
        ).grid(row=0, column=1)

        # === 状态栏 ===
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=X, pady=(10, 8))

        ttk.Label(status_frame, text="状态:", font=("Microsoft YaHei UI", 9, "bold")).pack(side=LEFT, padx=(0, 6))
        self.status_label = ttk.Label(
            status_frame, text="就绪",
            font=("Microsoft YaHei UI", 9),
            bootstyle="secondary"
        )
        self.status_label.pack(side=LEFT)
        self.secondary_labels.append(self.status_label)

        # === 日志区域 ===
        ttk.Label(parent, text="运行日志", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(0, 4))
        self.log_text = ScrolledText(
            parent, height=18, wrap=WORD, autohide=True,
            font=("Consolas", 10)
        )
        self.log_text.pack(fill=BOTH, expand=YES)

        # 绑定路径变化事件
        self.model_dir_var.trace_add("write", lambda *args: self._on_model_dir_change())

        # 绑定下拉框选择事件，实现实时持久化
        self.model_combo.bind("<<ComboboxSelected>>", lambda e: self._persist_combo_selection(self.model_combo, "ModelFilePath"))
        self.mmproj_combo.bind("<<ComboboxSelected>>", lambda e: self._persist_combo_selection(self.mmproj_combo, "MmprojPath"))

    def _build_param_page(self, parent):
        """构建参数配置页面内容"""
        # 提示标签
        hint_lbl = ttk.Label(
            parent,
            text="提示：留空表示不启用该参数；对于开关型参数，输入任意值即可启用。",
            font=("Microsoft YaHei UI", 10),
            bootstyle="secondary"
        )
        hint_lbl.pack(anchor=W, pady=(0, 8))
        self.secondary_labels.append(hint_lbl)

        # Canvas + Scrollbar
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, padding=5)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._build_param_ui(scroll_frame)

    def _build_param_ui(self, parent):
        """在滚动框架内构建参数输入控件"""
        self.param_entries = {}
        for group_name, params in PARAM_GROUPS:
            group = ttk.Labelframe(parent, text=group_name, padding=10)
            group.pack(fill=X, pady=(0, 14), padx=2)

            for key, flag, desc in params:
                row_container = ttk.Frame(group)
                row_container.pack(fill=X, pady=(4, 8))

                row = ttk.Frame(row_container)
                row.pack(fill=X)
                row.columnconfigure(1, weight=1)

                label_text = f"{flag}"
                lbl = ttk.Label(row, text=label_text, width=24, anchor=W, font=("Consolas", 11))
                lbl.grid(row=0, column=0, sticky=NW)

                var = self.param_vars[key]
                entry = ttk.Entry(row, textvariable=var, bootstyle="primary", font=("Microsoft YaHei UI", 10))
                entry.grid(row=0, column=1, sticky=EW, padx=(8, 0))

                # 描述小字
                desc_lbl = ttk.Label(
                    row, text=desc,
                    font=("Microsoft YaHei UI", 9),
                    bootstyle="secondary",
                    wraplength=600
                )
                desc_lbl.grid(row=1, column=1, sticky=EW, padx=(8, 0), pady=(2, 0))
                self.secondary_labels.append(desc_lbl)

                ToolTip(lbl, text=desc, bootstyle=("secondary", "inverse"))
                ToolTip(entry, text=desc, bootstyle=("secondary", "inverse"))

                self.param_entries[key] = entry
                entry.bind("<FocusOut>", lambda e: self._save_params())

    def _save_params(self):
        """防抖保存：将所有非空参数保存到配置文件中"""
        if getattr(self, '_save_after_id', None):
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(200, self._do_save_params)

    def _do_save_params(self):
        """执行实际的参数保存，仅在参数发生变化时才写入文件"""
        params = {}
        for key, var in self.param_vars.items():
            val = var.get().strip()
            if val:
                params[key] = val

        old_params = self.config.get("Params", {})
        if params == old_params:
            return

        self.config["Params"] = params
        save_config(self.config)

    def _update_action_btn(self):
        """根据运行状态更新启动/停止按钮"""
        if self.is_running:
            self.action_btn.configure(
                text="⏹ 停止",
                bootstyle="danger",
                command=self._stop_server
            )
        else:
            self.action_btn.configure(
                text="▶ 启动",
                bootstyle="success",
                command=self._start_server
            )

    def _apply_theme(self, mode, save=True):
        """应用主题模式：'dark' 或 'light'"""
        if mode not in THEME_MAP:
            mode = "dark"
        if mode == getattr(self, 'current_theme_mode', None):
            return

        self.current_theme_mode = mode
        theme_name = THEME_MAP[mode]
        colors = LOG_COLORS[mode]

        # 切换 ttkbootstrap 主题
        self.root.style.theme_use(theme_name)

        # 更新日志区域颜色
        self.log_text.text.configure(bg=colors["bg"], fg=colors["fg"])

        # 更新 secondary 标签颜色以提高暗色可见性
        hint_color = "#e0e0e0" if mode == "dark" else "#6c757d"
        for lbl in getattr(self, "secondary_labels", []):
            try:
                lbl.configure(foreground=hint_color)
            except Exception:
                pass

        # 更新按钮文字
        if mode == "dark":
            self.theme_btn.configure(text="☀ 亮色")
        else:
            self.theme_btn.configure(text="🌙 暗色")

        # 保存配置
        if save:
            self.config["ThemeMode"] = mode
            save_config(self.config)

    def _toggle_theme(self):
        """手动切换主题"""
        new_mode = "light" if self.current_theme_mode == "dark" else "dark"
        self._apply_theme(new_mode, save=True)

    def _log(self, message):
        """在日志区域追加消息（直接写入，用于单条非高频日志）"""
        text = self.log_text.text
        text.configure(state=NORMAL)
        text.insert(END, message + "\n")
        text.see(END)
        text.configure(state=DISABLED)

    def _schedule_log_flush(self):
        """调度日志队列批量刷新"""
        if self._log_after_id is not None:
            return
        self._log_after_id = self.root.after(100, self._flush_logs)

    def _flush_logs(self):
        """批量刷新日志队列到 GUI，减少主线程更新频率"""
        self._log_after_id = None
        lines = []
        while True:
            try:
                lines.append(self.log_queue.get_nowait())
            except queue.Empty:
                break

        if not lines:
            if self.is_running:
                self._schedule_log_flush()
            return

        text = self.log_text.text
        text.configure(state=NORMAL)
        text.insert(END, "\n".join(lines) + "\n")
        text.see(END)
        text.configure(state=DISABLED)

        if not self.url_opened:
            target = self.target_url
            for line in lines:
                if target in line:
                    self.url_opened = True
                    self._on_server_ready()
                    break

        if self.is_running or not self.log_queue.empty():
            self._schedule_log_flush()

    def _set_status(self, text, style="secondary"):
        self.status_label.configure(text=text, bootstyle=style)

    def _browse_llama(self):
        path = filedialog.askdirectory(title="选择 llama.cpp 目录")
        if path:
            self.llama_var.set(path)
            self.config["LlamaPath"] = path
            save_config(self.config)

    def _browse_model_dir(self):
        path = filedialog.askdirectory(title="选择模型文件夹")
        if path:
            self.model_dir_var.set(path)
            self.config["ModelPath"] = path
            save_config(self.config)
            self._refresh_model_list()

    def _on_model_dir_change(self):
        if hasattr(self, "_after_id"):
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(500, self._delayed_refresh)

    def _delayed_refresh(self):
        self._refresh_model_list()

    def _restore_combo(self, combo, config_key, display_names):
        """根据配置恢复下拉框选中项，若找不到则默认选第一项"""
        if not display_names:
            combo.set("")
            return
        saved = self.config.get(config_key, "")
        if saved:
            mapping = getattr(self, "file_mapping", {})
            for display, abs_path in mapping.items():
                if abs_path == saved:
                    combo.set(display)
                    return
        combo.current(0)

    def _persist_combo_selection(self, combo, config_key):
        """将下拉框当前选中项持久化到配置并保存"""
        display = combo.get()
        mapping = getattr(self, "file_mapping", {})
        self.config[config_key] = mapping.get(display, "")
        save_config(self.config)

    def _refresh_model_list(self):
        """刷新模型文件下拉列表"""
        path = self.model_dir_var.get().strip()
        files = get_model_files(path)

        if files:
            display_names = []
            self.file_mapping = {}
            abs_path_base = os.path.abspath(path) if path else ""
            for f in files:
                abs_path = os.path.abspath(f)
                if abs_path_base and abs_path.startswith(abs_path_base):
                    display = os.path.relpath(abs_path, abs_path_base)
                else:
                    display = abs_path
                display_names.append(display)
                self.file_mapping[display] = abs_path

            self.model_combo.configure(values=display_names)
            self._restore_combo(self.model_combo, "ModelFilePath", display_names)
            self._log(f"[系统] 发现 {len(files)} 个模型文件")
        else:
            self.model_combo.configure(values=[])
            self.model_combo.set("")
            self._log("[系统] 未找到模型文件，请检查模型路径")

        # 同步刷新多模态投影层下拉框
        if files:
            self.mmproj_combo.configure(values=display_names)
            self._restore_combo(self.mmproj_combo, "MmprojPath", display_names)
        else:
            self.mmproj_combo.configure(values=[])
            self.mmproj_combo.set("")

    def _start_server(self):
        if self.is_running:
            messagebox.showwarning("提示", "服务正在运行中")
            return

        llama_path = self.llama_var.get().strip()
        model_dir = self.model_dir_var.get().strip()
        model_display = self.model_combo.get()

        if not llama_path:
            messagebox.showerror("错误", "请先设置 llama.cpp 路径")
            return
        if not os.path.isdir(llama_path):
            messagebox.showerror("错误", f"llama.cpp 路径不存在: {llama_path}")
            return

        # 保存基本配置与参数
        self.config["LlamaPath"] = llama_path
        self.config["ModelPath"] = model_dir
        save_config(self.config)
        self._save_params()

        # 判断是否有模型或 Router 参数
        model_override = self.param_vars["model"].get().strip()
        models_dir = self.param_vars["models_dir"].get().strip()
        models_preset = self.param_vars["models_preset"].get().strip()

        file_mapping = getattr(self, "file_mapping", {})
        has_model = bool(model_override)
        if not has_model and model_display and model_display in file_mapping:
            has_model = True

        has_router = bool(models_dir) or bool(models_preset)

        if not has_model and not has_router:
            messagebox.showerror("错误", "请先选择模型文件，或在参数配置中填写模型路径/模型目录")
            return

        model_path = ""
        if not model_override and model_display and model_display in file_mapping:
            model_path = file_mapping[model_display]

        if model_path and not os.path.exists(model_path):
            messagebox.showerror("错误", f"模型文件不存在: {model_path}")
            return

        # 计算实际目标 URL（浏览器固定使用 127.0.0.1）
        host = self.param_vars["host"].get().strip() or "127.0.0.1"
        port = self.param_vars["port"].get().strip() or "8080"
        self.target_url = f"http://{host}:{port}"
        self.browser_url = f"http://127.0.0.1:{port}"

        self._set_status("正在启动...", "warning")
        self.is_running = True
        self._update_action_btn()
        self.url_opened = False

        self._log("=" * 50)
        self._log("[系统] 启动 llama-server")
        self._log(f"[系统] 工作目录: {llama_path}")

        # 自动检测可执行文件
        server_exe = None
        possible_names = ["llama-server.exe", "llama-server"]
        for name in possible_names:
            candidate = os.path.join(llama_path, name)
            if os.path.exists(candidate):
                server_exe = candidate
                break

        if server_exe is None:
            messagebox.showerror("错误", f"在 LlamaPath 下未找到 llama-server 可执行文件\n路径: {llama_path}")
            self._reset_ui_state()
            self._set_status("未找到 llama-server", "danger")
            return

        self._log(f"[系统] 可执行文件: {server_exe}")

        # 构建参数列表
        args = [server_exe]

        # 模型参数
        if model_override:
            args.extend(["-m", model_override])
            self._log(f"[系统] 模型: {model_override}")
        elif model_path:
            args.extend(["-m", model_path])
            self._log(f"[系统] 模型: {model_path}")

        # 多模态投影层参数
        mmproj_path = self.config.get("MmprojPath", "")
        if mmproj_path:
            args.extend(["--mmproj", mmproj_path])
            self._log(f"[系统] 多模态投影层: {mmproj_path}")

        # 其他参数
        for group_name, params in PARAM_GROUPS:
            for key, flag, desc in params:
                if key == "model":
                    continue
                value = self.param_vars[key].get().strip()
                if value:
                    args.append(flag)
                    if key not in FLAG_PARAMS:
                        args.append(value)
                    self._log(f"[参数] {flag}" + (f" {value}" if key not in FLAG_PARAMS else ""))

        try:
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                cwd=llama_path,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            self._log(f"[错误] 启动失败: {e}")
            self._set_status(f"启动失败: {e}", "danger")
            self._reset_ui_state()
            return

        self.monitor_thread = threading.Thread(target=self._monitor_output, daemon=True)
        self.monitor_thread.start()
        self._schedule_log_flush()

    def _monitor_output(self):
        """在后台线程中监听 llama-server 输出（通过队列批量提交到 GUI）"""
        try:
            for line in self.process.stdout:
                if line is None:
                    break
                line = line.rstrip("\n\r")
                if line:
                    self.log_queue.put(line)
        except Exception as e:
            self.log_queue.put(f"[错误] 监听异常: {e}")
        finally:
            return_code = None
            try:
                return_code = self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            self.root.after(0, lambda rc=return_code: self._on_process_exit(rc))

    def _open_browser(self):
        """手动打开浏览器访问服务"""
        url = getattr(self, "browser_url", None) or self.target_url
        if url:
            try:
                webbrowser.open(url)
                self._log(f"[系统] 已打开浏览器: {url}")
            except Exception as e:
                self._log(f"[错误] 打开浏览器失败: {e}")
        else:
            self._log("[错误] 服务地址未设置")

    def _on_server_ready(self):
        """检测到服务就绪时的回调"""
        self._log(f"[系统] 检测到服务地址: {self.target_url}")
        self._set_status("启动成功", "success")
        try:
            self.open_url_btn.configure(state=NORMAL)
        except Exception:
            pass

    def _on_process_exit(self, return_code):
        """进程退出时的回调"""
        self.is_running = False
        self._reset_ui_state()

        if return_code is not None and return_code != 0:
            self._set_status(f"进程已退出，返回码: {return_code}", "danger")
            self._log(f"[系统] 进程退出，返回码: {return_code}")
        else:
            self._set_status("已停止", "secondary")
            self._log("[系统] 进程已结束")

    def _stop_server(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self._log("[系统] 正在停止服务...")
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self._log("[系统] 已强制结束进程")
            except Exception as e:
                self._log(f"[错误] 停止失败: {e}")
        self._reset_ui_state()
        self._set_status("已停止", "secondary")

    def _reset_ui_state(self):
        self.is_running = False
        self._update_action_btn()
        try:
            self.open_url_btn.configure(state=DISABLED)
        except Exception:
            pass

    def on_close(self):
        """窗口关闭时清理"""
        self._persist_combo_selection(self.model_combo, "ModelFilePath")
        self._persist_combo_selection(self.mmproj_combo, "MmprojPath")
        self._save_params()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                pass
        self.root.destroy()


def main():
    config = load_config()
    mode = resolve_theme_mode(config)
    theme_name = THEME_MAP.get(mode, "darkly")

    root = ttk.Window(themename=theme_name)
    try:
        if os.path.exists(ICON_PATH):
            root.iconbitmap(ICON_PATH)
    except Exception:
        pass
    app = LauncherApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
