import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from tkinter import filedialog, messagebox
import json
import os
import sys
import subprocess
import threading
import webbrowser
import glob
import winreg

def get_resource_path(relative_path):
    """获取资源文件路径，兼容开发环境和 PyInstaller 打包环境"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发环境
    return os.path.join(os.path.abspath("."), relative_path)


def get_config_path():
    """获取配置文件路径，优先使用 exe 所在目录（支持持久化读写）"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 单文件模式：exe 所在目录
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, "config.json")
    # 开发环境：当前工作目录
    return os.path.join(os.path.abspath("."), "config.json")


CONFIG_FILE = get_config_path()
ICON_PATH = get_resource_path("ico/logo.ico")

DEFAULT_CONFIG = {
    "LlamaPath": "",
    "ModelPath": "",
    "ThemeMode": "auto"
}

THEME_MAP = {
    "dark": "darkly",
    "light": "flatly"
}

LOG_COLORS = {
    "dark": {"bg": "#1e1e1e", "fg": "#d4d4d4"},
    "light": {"bg": "#f8f9fa", "fg": "#212529"}
}

TARGET_URL = "http://127.0.0.1:8080"


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 补全缺失字段
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            messagebox.showerror("配置错误", f"读取配置文件失败: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
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
    """获取指定路径下的模型文件列表"""
    if not path or not os.path.isdir(path):
        return []
    extensions = ("*.gguf", "*.bin", "*.safetensors", "*.pt", "*.pth", "*.ckpt")
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(path, ext)))
    for ext in extensions:
        files.extend(glob.glob(os.path.join(path, "**", ext), recursive=True))
    files = sorted(set(files))
    return files


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.current_theme_mode = resolve_theme_mode(self.config)

        self.root.title("EZ-llama-launcher")
        self.root.geometry("800x700")
        self.root.resizable(True, False)
        self.root.place_window_center()

        self.process = None
        self.monitor_thread = None
        self.is_running = False
        self.url_opened = False

        self._build_ui()
        self._apply_theme(self.current_theme_mode, save=False)
        self._refresh_model_list()

    def _build_ui(self):
        # 主容器
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=BOTH, expand=YES)

        # === 标题 + 主题切换按钮 ===
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=X, pady=(0, 15))
        title_frame.columnconfigure(0, weight=1)

        left_frame = ttk.Frame(title_frame)
        left_frame.grid(row=0, column=0, sticky=W)

        ttk.Label(
            left_frame,
            text="EZ-llama-launcher",
            font=("Microsoft YaHei UI", 18, "bold"),
            bootstyle="primary"
        ).pack(anchor=W)
        ttk.Label(
            left_frame,
            text="简易 Llama.cpp 模型启动器",
            font=("Microsoft YaHei UI", 10),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(2, 0))

        # 右上角主题切换按钮
        right_frame = ttk.Frame(title_frame)
        right_frame.grid(row=0, column=1, sticky=E)

        self.theme_btn = ttk.Button(
            right_frame,
            text="🌙 暗色",
            command=self._toggle_theme,
            bootstyle="outline-secondary",
            width=10
        )
        self.theme_btn.pack(anchor=E)

        ttk.Separator(main_frame, bootstyle="secondary").pack(fill=X, pady=(0, 15))

        # === LlamaPath ===
        ttk.Label(main_frame, text="llama.cpp 路径", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(0, 4))
        llama_frame = ttk.Frame(main_frame)
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
        ttk.Label(main_frame, text="模型文件夹路径", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(0, 4))
        model_frame = ttk.Frame(main_frame)
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
        ttk.Label(main_frame, text="选择模型文件", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(8, 4))
        combo_frame = ttk.Frame(main_frame)
        combo_frame.pack(fill=X, pady=(0, 12))
        combo_frame.columnconfigure(0, weight=1)

        self.model_combo = ttk.Combobox(combo_frame, state="readonly", bootstyle="primary")
        self.model_combo.grid(row=0, column=0, sticky=EW, padx=(0, 8))

        ttk.Button(
            combo_frame, text="刷新", command=self._refresh_model_list,
            bootstyle="outline-secondary", width=10
        ).grid(row=0, column=1)

        # === 操作按钮 ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=X, pady=(10, 12))

        self.start_btn = ttk.Button(
            btn_frame, text="▶  启动 llama-server",
            command=self._start_server,
            bootstyle="success", width=20
        )
        self.start_btn.pack(side=LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(
            btn_frame, text="⏹  停止",
            command=self._stop_server,
            bootstyle="danger", width=12,
            state=DISABLED
        )
        self.stop_btn.pack(side=LEFT)

        # === 状态栏 ===
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=X, pady=(0, 8))

        ttk.Label(status_frame, text="状态:", font=("Microsoft YaHei UI", 9, "bold")).pack(side=LEFT, padx=(0, 6))
        self.status_label = ttk.Label(
            status_frame, text="就绪",
            font=("Microsoft YaHei UI", 9),
            bootstyle="secondary"
        )
        self.status_label.pack(side=LEFT)

        # === 日志区域 ===
        ttk.Label(main_frame, text="运行日志", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=W, pady=(0, 4))
        self.log_text = ScrolledText(
            main_frame, height=16, wrap=WORD, autohide=True,
            font=("Consolas", 10)
        )
        self.log_text.pack(fill=BOTH, expand=YES)

        # 绑定路径变化事件
        self.model_dir_var.trace_add("write", lambda *args: self._on_model_dir_change())

    def _apply_theme(self, mode, save=True):
        """应用主题模式：'dark' 或 'light'"""
        if mode not in THEME_MAP:
            mode = "dark"

        self.current_theme_mode = mode
        theme_name = THEME_MAP[mode]
        colors = LOG_COLORS[mode]

        # 切换 ttkbootstrap 主题
        self.root.style.theme_use(theme_name)

        # 更新日志区域颜色
        self.log_text.text.configure(bg=colors["bg"], fg=colors["fg"])

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
        """在日志区域追加消息"""
        self.log_text.text.configure(state=NORMAL)
        self.log_text.text.insert(END, message + "\n")
        self.log_text.text.see(END)
        self.log_text.text.configure(state=DISABLED)

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

    def _refresh_model_list(self):
        """刷新模型文件下拉列表"""
        path = self.model_dir_var.get().strip()
        files = get_model_files(path)

        if files:
            display_names = []
            self.file_mapping = {}
            for f in files:
                abs_path = os.path.abspath(f)
                if path and abs_path.startswith(os.path.abspath(path)):
                    display = os.path.relpath(abs_path, path)
                else:
                    display = abs_path
                display_names.append(display)
                self.file_mapping[display] = abs_path

            self.model_combo.configure(values=display_names)
            if display_names:
                self.model_combo.current(0)
            self._log(f"[系统] 发现 {len(files)} 个模型文件")
        else:
            self.model_combo.configure(values=[])
            self.model_combo.set("")
            self._log("[系统] 未找到模型文件，请检查模型路径")

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
        if not model_display or model_display not in getattr(self, "file_mapping", {}):
            messagebox.showerror("错误", "请先选择模型文件")
            return

        model_path = self.file_mapping[model_display]

        if not os.path.exists(model_path):
            messagebox.showerror("错误", f"模型文件不存在: {model_path}")
            return

        # 保存配置
        self.config["LlamaPath"] = llama_path
        self.config["ModelPath"] = model_dir
        save_config(self.config)

        self._set_status("正在启动...", "warning")
        self.start_btn.configure(state=DISABLED)
        self.stop_btn.configure(state=NORMAL)
        self.is_running = True
        self.url_opened = False

        self._log("=" * 50)
        self._log("[系统] 启动 llama-server")
        self._log(f"[系统] 工作目录: {llama_path}")
        self._log(f"[系统] 模型文件: {model_path}")

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

        try:
            self.process = subprocess.Popen(
                [server_exe, "-m", model_path],
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

    def _monitor_output(self):
        """在后台线程中监听 llama-server 输出"""
        try:
            for line in self.process.stdout:
                if line is None:
                    break
                line = line.rstrip("\n\r")
                if not line:
                    continue

                self.root.after(0, lambda l=line: self._log(l))

                # 精确匹配目标 URL
                if not self.url_opened and TARGET_URL in line:
                    self.url_opened = True
                    self.root.after(0, self._on_server_ready)
        except Exception as e:
            self.root.after(0, lambda e=e: self._log(f"[错误] 监听异常: {e}"))
        finally:
            return_code = None
            try:
                return_code = self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            self.root.after(0, lambda rc=return_code: self._on_process_exit(rc))

    def _on_server_ready(self):
        """检测到服务就绪时的回调"""
        self._log(f"[系统] 检测到服务地址: {TARGET_URL}")
        self._set_status("启动成功", "success")
        try:
            webbrowser.open(TARGET_URL)
            self._log("[系统] 已自动打开浏览器")
        except Exception as e:
            self._log(f"[错误] 打开浏览器失败: {e}")

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
        self.start_btn.configure(state=NORMAL)
        self.stop_btn.configure(state=DISABLED)

    def on_close(self):
        """窗口关闭时清理"""
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
