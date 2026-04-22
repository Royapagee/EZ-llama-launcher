# EZ-llama-launcher

- 简单的 Llama.cpp 启动器，用于将启动命令封装成 GUI 简化操作。
- 本项目基于ai生成

## 功能特性

- **路径配置管理**：独立配置文件持久化保存 llama.cpp 程序路径和模型文件夹路径
- **模型自动扫描**：自动读取模型目录下的 `.gguf`、`.bin`、`.safetensors` 等模型文件，支持下拉选择
- **一键启动服务**：自动调起 llama-server，无需手动输入命令
- **智能浏览器打开**：检测到 `http://127.0.0.1:8080` 服务就绪后，自动调用系统浏览器打开
- **暗色/亮色主题**：自动跟随 Windows 系统主题，支持右上角手动切换
- **实时日志输出**：内置日志区域实时显示服务运行状态

## 项目结构

```
EZ-llama-launcher/
├── main.py              # 原版 Python 入口（保留参考）
├── main.cpp             # WinUI 3 C++ 入口
├── EZLlamaLauncher.vcxproj   # Visual Studio 项目文件
├── packages.config      # NuGet 包配置
├── App.xaml / App.cpp / App.h   # WinUI 3 应用框架
├── MainWindow.xaml / MainWindow.cpp / MainWindow.h   # 主窗口与核心逻辑
├── pch.h / pch.cpp      # 预编译头
├── app.manifest         # 应用清单
├── config.json          # 配置文件（自动创建）
├── ico/
│   └── logo.ico         # 图标
├── LICENSE
└── README.md
```

## 构建与运行（WinUI 3 C++）

### 环境要求

- Windows 10 版本 19041 或更高 / Windows 11
- Visual Studio 2022（含 "使用 C++ 的桌面开发" 和 "Windows 应用 SDK" 工作负载）
- Windows App SDK 1.5+（通过 NuGet 自动还原）

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd EZ-llama-launcher
```

### 2. 还原 NuGet 包

在 Visual Studio 中打开 `EZLlamaLauncher.vcxproj`，右键项目 → **还原 NuGet 包**；
或在 Developer Command Prompt 中执行：

```bash
msbuild -t:restore EZLlamaLauncher.vcxproj
```

### 3. 编译运行

在 Visual Studio 中选择 **x64** → **Release**，按 **F5** 编译并运行。

编译生成的可执行文件位于 `x64/Release/EZLamaLauncher.exe`（Unpackaged，可直接复制运行，附带 Windows App SDK 运行时）。

## 原版 Python 运行方式（保留）

如果你仍想使用 Python 版本：

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

## 使用说明

1. 首次启动时，在界面上方设置 **llama.cpp 路径**（解压后的 llama.cpp 目录，包含 `llama-server.exe`）
2. 设置 **模型文件夹路径**（存放 `.gguf` 模型文件的目录）
3. 在下拉菜单中选择要加载的模型文件
4. 点击 **▶ 启动** 按钮
5. 服务启动成功后，浏览器会自动打开 `http://127.0.0.1:8080`

## 配置文件

程序会自动在 exe 所在目录下创建 `config.json`：

```json
{
    "LlamaPath": "",
    "ModelPath": "",
    "ThemeMode": "auto"
}
```

| 字段 | 说明 |
|------|------|
| `LlamaPath` | llama.cpp 程序所在目录 |
| `ModelPath` | 模型文件存放目录 |
| `ThemeMode` | 主题模式：`auto`（跟随系统）、`dark`（暗色）、`light`（亮色） |

## 许可证

[LICENSE](LICENSE)
