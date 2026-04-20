# EZ-llama-launcher

简单的 Llama.cpp 启动器，用于将启动命令封装成 GUI 简化操作。

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
├── main.py              # 主程序入口
├── config.json          # 配置文件（自动创建）
├── requirements.txt     # Python 依赖
├── ico/
│   └── logo.ico         # 图标
├── LICENSE
└── README.md
```

## 安装与运行

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd EZ-llama-launcher
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv
```

### 3. 安装依赖

```bash
.venv\Scripts\pip install -r requirements.txt
```

### 4. 运行程序

```bash
.venv\Scripts\python main.py
```

## 使用说明

1. 首次启动时，在界面上方设置 **llama.cpp 路径**（解压后的 llama.cpp 目录，包含 `llama-server.exe`）
2. 设置 **模型文件夹路径**（存放 `.gguf` 模型文件的目录）
3. 在下拉菜单中选择要加载的模型文件
4. 点击 **▶ 启动 llama-server** 按钮
5. 服务启动成功后，浏览器会自动打开 `http://127.0.0.1:8080`

## 配置文件

程序会自动在工作目录下创建 `config.json`：

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

## 打包为可执行文件（可选）

如果需要分发给没有 Python 环境的用户，可使用 PyInstaller 打包：

```bash
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller -F -w -i ico/logo.ico main.py
```

打包后的可执行文件位于 `dist/main.exe`。

另：作者自行编译了一份exe，可以前往`Releases`页面下载
或[点击前往](https://github.com/Royapagee/EZ-llama-launcher/releases)


## 许可证

[LICENSE](LICENSE)
