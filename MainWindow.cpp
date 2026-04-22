#include "pch.h"
#include "MainWindow.h"
#include "MainWindow.g.cpp"

using namespace winrt;
using namespace Microsoft::UI::Xaml;
using namespace Microsoft::UI::Xaml::Controls;
using namespace Microsoft::UI::Xaml::Media;
using namespace Microsoft::UI::Dispatching;
using namespace Windows::Data::Json;

namespace {
    struct ParamInfo { std::wstring key; std::wstring flag; std::wstring desc; };
    struct ParamGroup { std::wstring name; std::vector<ParamInfo> params; };

    const std::vector<ParamGroup> PARAM_GROUPS = {
        {L"模型加载参数", {
            {L"model", L"-m", L"本地 GGUF 模型文件路径（覆盖下方下拉选择）"},
            {L"hf", L"-hf", L"Hugging Face Hub 模型（格式：用户/仓库:量化标签）"},
            {L"model_url", L"-mu", L"远程 URL 加载模型"},
            {L"alias", L"--alias", L"模型别名"},
        }},
        {L"网络与服务参数", {
            {L"host", L"--host", L"监听地址（默认 127.0.0.1；0.0.0.0 允许所有网访问）"},
            {L"port", L"--port", L"监听端口（默认 8080）"},
            {L"api_key", L"--api-key", L"API Key（请求需携带 Authorization: Bearer <key>）"},
            {L"timeout", L"--timeout", L"读写超时时间（秒）"},
            {L"metrics", L"--metrics", L"启用 /metrics 端点（输入任意值启用）"},
        }},
        {L"性能与硬件参数", {
            {L"ngl", L"-ngl", L"GPU 层数（99 通常可将所有层放入 GPU）"},
            {L"ctx_size", L"-c", L"上下文窗口大小（token 数）"},
            {L"parallel", L"-np", L"并行请求槽位数"},
            {L"threads", L"-t", L"CPU 推理线程数"},
            {L"batch_size", L"-b", L"批处理大小"},
            {L"ubatch_size", L"-ub", L"微批次大小"},
            {L"flash_attn", L"-fa", L"启用 Flash Attention（输入任意值启用）"},
            {L"cache_prompt", L"--cache-prompt", L"启用 prompt 缓存（输入任意值启用）"},
            {L"cache_reuse", L"--cache-reuse", L"缓存复用的 token 数量"},
            {L"cache_type_k", L"-ctk", L"Key 缓存量化类型（q4_0 / q8_0 / f16）"},
            {L"cache_type_v", L"-ctv", L"Value 缓存量化类型"},
            {L"no_mmap", L"--no-mmap", L"禁用内存映射（输入任意值启用）"},
            {L"split_mode", L"--split-mode", L"多卡切分模式（none / layer / row）"},
            {L"tensor_split", L"--tensor-split", L"多卡显存分配比例（如 7,8）"},
        }},
        {L"采样与生成参数", {
            {L"temp", L"--temp", L"温度（0=确定性，越高越随机；默认 0.8）"},
            {L"top_k", L"--top-k", L"Top-K 采样（默认 40）"},
            {L"top_p", L"--top-p", L"Top-P 核采样（默认 1.0）"},
            {L"min_p", L"--min-p", L"最小概率阈值（默认 0.0）"},
            {L"repeat_penalty", L"--repeat-penalty", L"重复惩罚系数（默认 1.0）"},
            {L"presence_penalty", L"--presence-penalty", L"存在惩罚（默认 0.0）"},
            {L"predict", L"-n", L"最大生成 token 数（默认 -1）"},
            {L"seed", L"--seed", L"随机种子（默认 -1）"},
        }},
        {L"模板与格式化参数", {
            {L"jinja", L"--jinja", L"使用 Jinja 模板引擎（输入即启用）"},
            {L"chat_template", L"--chat-template", L"聊天模板（llama3 / chatml / llama2）"},
            {L"chat_template_kwargs", L"--chat-template-kwargs", L"模板额外参数（JSON 格式）"},
        }},
        {L"多模型 Router 模式参数", {
            {L"models_dir", L"--models-dir", L"本地 GGUF 模型目录（不指定 -m 时进入 Router 模式）"},
            {L"models_max", L"--models-max", L"同时驻留内存的最大模型数"},
            {L"models_preset", L"--models-preset", L"预设配置文件路径（.ini）"},
            {L"cache_list", L"-cl", L"列出缓存中的模型（输入任意值启用）"},
        }},
        {L"日志与调试参数", {
            {L"verbose", L"-v", L"启用详细日志（输入任意值启用）"},
            {L"log_verbosity", L"-lv", L"日志详细级别（0-4）"},
            {L"log_timestamps", L"--log-timestamps", L"日志输出时间戳（输入任意值启用）"},
            {L"log_colors", L"--log-colors", L"日志着色（auto / on / off）"},
            {L"props", L"--props", L"启用 /props 端点（输入任意值启用）"},
        }},
    };

    const std::unordered_set<std::wstring> FLAG_PARAMS = {
        L"metrics", L"flash_attn", L"cache_prompt", L"no_mmap", L"jinja",
        L"cache_list", L"verbose", L"log_timestamps", L"props"
    };
}

namespace winrt::EZLlamaLauncher::implementation
{
    std::wstring MainWindow::Trim(std::wstring const& s)
    {
        size_t start = s.find_first_not_of(L" \t\r\n");
        if (start == std::wstring::npos) return L"";
        size_t end = s.find_last_not_of(L" \t\r\n");
        return s.substr(start, end - start + 1);
    }

    MainWindow::MainWindow()
    {
        InitializeComponent();

        Title(L"EZ-llama-launcher");
        ExtendsContentIntoTitleBar(true);

        // Timers
        m_logTimer = DispatcherQueue().CreateTimer();
        m_logTimer.Interval(std::chrono::milliseconds(100));
        m_logTimer.Tick({ this, &MainWindow::OnLogTimerTick });

        m_saveTimer = DispatcherQueue().CreateTimer();
        m_saveTimer.Interval(std::chrono::milliseconds(200));
        m_saveTimer.Tick({ this, &MainWindow::OnSaveTimerTick });

        // Load config and build UI
        LoadConfig();
        BuildParamPage();
        ApplyTheme(m_themeMode, false);

        // Init basic page fields
        LlamaPathBox().Text(m_config.GetNamedString(L"LlamaPath", L""));
        ModelPathBox().Text(m_config.GetNamedString(L"ModelPath", L""));

        // Events
        Closed({ this, &MainWindow::OnClosed });
        ModelPathBox().LostFocus([this](auto&, auto&) { RefreshModelList(); });

        ModelCombo().SelectionChanged([this](auto&, auto&) {
            if (auto item = ModelCombo().SelectedItem()) {
                auto display = std::wstring(item.as<winrt::hstring>());
                auto it = m_fileMapping.find(display);
                if (it != m_fileMapping.end()) {
                    m_config.SetNamedValue(L"ModelFilePath", JsonValue::CreateStringValue(it->second));
                    SaveConfig();
                }
            }
        });

        MmprojCombo().SelectionChanged([this](auto&, auto&) {
            if (auto item = MmprojCombo().SelectedItem()) {
                auto display = std::wstring(item.as<winrt::hstring>());
                auto it = m_fileMapping.find(display);
                if (it != m_fileMapping.end()) {
                    m_config.SetNamedValue(L"MmprojPath", JsonValue::CreateStringValue(it->second));
                    SaveConfig();
                }
            }
        });

        // Initial model scan
        RefreshModelList();
    }

    void MainWindow::BuildParamPage()
    {
        auto paramsConfig = m_config.GetNamedObject(L"Params", JsonObject());

        for (auto const& group : PARAM_GROUPS)
        {
            auto border = Border();
            border.BorderThickness(ThicknessHelper::FromUniformLength(1));
            border.CornerRadius(CornerRadiusHelper::FromUniformRadius(4));
            border.Padding(ThicknessHelper::FromLengths(12, 12, 12, 12));
            border.Margin(ThicknessHelper::FromLengths(0, 0, 0, 12));
            border.BorderBrush(SolidColorBrush(Windows::UI::Colors::Gray()));

            auto groupStack = StackPanel();

            auto title = TextBlock();
            title.Text(group.name);
            title.FontWeight(Windows::UI::Text::FontWeights::Bold());
            title.FontSize(16);
            title.Margin(ThicknessHelper::FromLengths(0, 0, 0, 8));
            groupStack.Children().Append(title);

            for (auto const& param : group.params)
            {
                auto grid = Grid();
                grid.ColumnDefinitions().Append(ColumnDefinition());
                grid.ColumnDefinitions().Append(ColumnDefinition());
                grid.ColumnDefinitions().GetAt(0).Width(GridLengthHelper::FromPixels(140));
                grid.ColumnDefinitions().GetAt(1).Width(GridLengthHelper::FromStar(1));

                auto flagLbl = TextBlock();
                flagLbl.Text(param.flag);
                flagLbl.FontFamily(Windows::UI::Xaml::Media::FontFamily(L"Consolas"));
                flagLbl.VerticalAlignment(VerticalAlignment::Top);
                Grid::SetColumn(flagLbl, 0);

                auto entryStack = StackPanel();
                Grid::SetColumn(entryStack, 1);

                auto entry = TextBox();
                if (paramsConfig.HasKey(param.key)) {
                    entry.Text(paramsConfig.GetNamedString(param.key));
                }
                entry.Margin(ThicknessHelper::FromLengths(8, 0, 0, 0));

                auto descLbl = TextBlock();
                descLbl.Text(param.desc);
                descLbl.FontSize(12);
                descLbl.Opacity(0.7);
                descLbl.TextWrapping(TextWrapping::Wrap);
                descLbl.Margin(ThicknessHelper::FromLengths(8, 2, 0, 0));

                entryStack.Children().Append(entry);
                entryStack.Children().Append(descLbl);

                grid.Children().Append(flagLbl);
                grid.Children().Append(entryStack);
                groupStack.Children().Append(grid);

                m_paramEntries[param.key] = entry;

                entry.LostFocus([this](auto&, auto&) {
                    ScheduleSaveParams();
                });
            }

            border.Child(groupStack);
            ParamStack().Children().Append(border);
        }
    }

    void MainWindow::ShowPage(bool basic)
    {
        auto app = Application::Current();
        if (basic) {
            BasicScroll().Visibility(Visibility::Visible);
            ParamScroll().Visibility(Visibility::Collapsed);
            NavBasicBtn().Style(app.Resources().Lookup(box_value(L"AccentButtonStyle")).as<Style>());
            NavParamBtn().Style(app.Resources().Lookup(box_value(L"DefaultButtonStyle")).as<Style>());
        } else {
            BasicScroll().Visibility(Visibility::Collapsed);
            ParamScroll().Visibility(Visibility::Visible);
            NavBasicBtn().Style(app.Resources().Lookup(box_value(L"DefaultButtonStyle")).as<Style>());
            NavParamBtn().Style(app.Resources().Lookup(box_value(L"AccentButtonStyle")).as<Style>());
        }
    }

    // ===== Config =====
    std::filesystem::path MainWindow::GetConfigPath()
    {
        wchar_t exePath[MAX_PATH];
        GetModuleFileNameW(nullptr, exePath, MAX_PATH);
        return std::filesystem::path(exePath).parent_path() / L"config.json";
    }

    void MainWindow::LoadConfig()
    {
        m_configPath = GetConfigPath();
        if (!std::filesystem::exists(m_configPath)) {
            m_config = JsonObject();
            m_config.SetNamedValue(L"LlamaPath", JsonValue::CreateStringValue(L""));
            m_config.SetNamedValue(L"ModelPath", JsonValue::CreateStringValue(L""));
            m_config.SetNamedValue(L"ModelFilePath", JsonValue::CreateStringValue(L""));
            m_config.SetNamedValue(L"MmprojPath", JsonValue::CreateStringValue(L""));
            m_config.SetNamedValue(L"ThemeMode", JsonValue::CreateStringValue(L"auto"));
            m_config.SetNamedValue(L"Params", JsonObject());
            m_themeMode = L"auto";
            return;
        }

        try {
            std::wifstream fs(m_configPath, std::ios::binary);
            fs.imbue(std::locale(fs.getloc(), new std::codecvt_utf8_utf16<wchar_t>));
            std::wstringstream ss;
            ss << fs.rdbuf();
            m_config = JsonObject::Parse(ss.str());
        } catch (...) {
            m_config = JsonObject();
        }

        auto ensureString = [&](wchar_t const* key, wchar_t const* def) {
            if (!m_config.HasKey(key)) m_config.SetNamedValue(key, JsonValue::CreateStringValue(def));
        };
        ensureString(L"LlamaPath", L"");
        ensureString(L"ModelPath", L"");
        ensureString(L"ModelFilePath", L"");
        ensureString(L"MmprojPath", L"");
        ensureString(L"ThemeMode", L"auto");
        if (!m_config.HasKey(L"Params")) m_config.SetNamedValue(L"Params", JsonObject());

        m_themeMode = std::wstring(m_config.GetNamedString(L"ThemeMode", L"auto"));
    }

    void MainWindow::SaveConfig()
    {
        if (!m_config) return;
        try {
            std::wofstream fs(m_configPath, std::ios::binary);
            fs.imbue(std::locale(fs.getloc(), new std::codecvt_utf8_utf16<wchar_t>));
            fs << m_config.ToString();
        } catch (...) {}
    }

    void MainWindow::SaveParams()
    {
        auto params = JsonObject();
        for (auto const& [key, box] : m_paramEntries) {
            auto val = Trim(std::wstring(box.Text()));
            if (!val.empty()) {
                params.SetNamedValue(key, JsonValue::CreateStringValue(val));
            }
        }
        m_config.SetNamedValue(L"Params", params);
        SaveConfig();
    }

    void MainWindow::ScheduleSaveParams()
    {
        if (m_saveTimer) m_saveTimer.Start();
    }

    void MainWindow::OnSaveTimerTick(DispatcherQueueTimer const&, Windows::Foundation::IInspectable const&)
    {
        m_saveTimer.Stop();
        SaveParams();
    }

    // ===== Theme =====
    std::wstring MainWindow::GetSystemTheme()
    {
        DWORD value = 1;
        DWORD size = sizeof(value);
        if (RegGetValueW(HKEY_CURRENT_USER,
            L"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
            L"AppsUseLightTheme",
            RRF_RT_REG_DWORD, nullptr, &value, &size) == ERROR_SUCCESS) {
            return value == 1 ? L"light" : L"dark";
        }
        return L"dark";
    }

    void MainWindow::ApplyTheme(std::wstring const& mode, bool save)
    {
        std::wstring actual = mode;
        if (actual == L"auto") actual = GetSystemTheme();
        if (actual != L"dark" && actual != L"light") actual = L"dark";

        auto root = Content().as<FrameworkElement>();
        if (actual == L"dark") {
            root.RequestedTheme(ElementTheme::Dark);
            ThemeBtn().Content(box_value(L"☀ 亮色"));
        } else {
            root.RequestedTheme(ElementTheme::Light);
            ThemeBtn().Content(box_value(L"🌙 暗色"));
        }

        if (save) {
            m_config.SetNamedValue(L"ThemeMode", JsonValue::CreateStringValue(mode));
            SaveConfig();
        }
    }

    // ===== Models =====
    std::vector<std::wstring> MainWindow::GetModelFiles(std::wstring const& path)
    {
        if (path.empty() || !std::filesystem::is_directory(path)) return {};

        auto absPath = std::filesystem::absolute(path);
        file_time mtime = {};
        try { mtime = std::filesystem::last_write_time(absPath); } catch (...) {}

        auto it = m_modelCache.find(absPath.wstring());
        if (it != m_modelCache.end() && it->second.first == mtime) {
            return it->second.second;
        }

        std::vector<std::wstring> files;
        static const std::vector<std::wstring> exts = {L".gguf", L".bin", L".safetensors", L".pt", L".pth", L".ckpt"};

        try {
            for (const auto& entry : std::filesystem::recursive_directory_iterator(absPath, std::filesystem::directory_options::skip_permission_denied)) {
                if (!entry.is_regular_file()) continue;
                auto ext = entry.path().extension().wstring();
                std::transform(ext.begin(), ext.end(), ext.begin(), ::towlower);
                if (std::find(exts.begin(), exts.end(), ext) != exts.end()) {
                    files.push_back(entry.path().wstring());
                }
            }
        } catch (...) {}

        std::sort(files.begin(), files.end());
        m_modelCache[absPath.wstring()] = {mtime, files};
        return files;
    }

    void MainWindow::RefreshModelList()
    {
        auto path = std::wstring(ModelPathBox().Text());
        auto files = GetModelFiles(path);

        ModelCombo().Items().Clear();
        MmprojCombo().Items().Clear();
        m_fileMapping.clear();

        if (files.empty()) {
            AppendLog(L"[系统] 未找到模型文件，请检查模型路径");
            return;
        }

        auto basePath = std::filesystem::absolute(path);
        for (auto const& f : files) {
            auto rel = std::filesystem::relative(f, basePath).wstring();
            if (rel.empty() || rel.starts_with(L"..")) rel = f;
            m_fileMapping[rel] = f;
            ModelCombo().Items().Append(box_value(winrt::hstring(rel)));
            MmprojCombo().Items().Append(box_value(winrt::hstring(rel)));
        }

        auto restoreCombo = [&](ComboBox& combo, wchar_t const* savedKey) {
            auto saved = std::wstring(m_config.GetNamedString(savedKey, L""));
            if (!saved.empty()) {
                for (uint32_t i = 0; i < combo.Items().Size(); ++i) {
                    auto display = std::wstring(combo.Items().GetAt(i).as<winrt::hstring>());
                    auto it = m_fileMapping.find(display);
                    if (it != m_fileMapping.end() && it->second == saved) {
                        combo.SelectedIndex(i);
                        return;
                    }
                }
            }
            if (combo.Items().Size() > 0) combo.SelectedIndex(0);
        };

        restoreCombo(ModelCombo(), L"ModelFilePath");
        restoreCombo(MmprojCombo(), L"MmprojPath");

        AppendLog(L"[系统] 发现 " + std::to_wstring(files.size()) + L" 个模型文件");
    }

    // ===== Logging =====
    void MainWindow::AppendLog(std::wstring const& msg)
    {
        std::lock_guard lock(m_logMutex);
        m_logQueue.push_back(msg);
    }

    void MainWindow::FlushLogs()
    {
        std::vector<std::wstring> lines;
        {
            std::lock_guard lock(m_logMutex);
            lines = std::move(m_logQueue);
            m_logQueue.clear();
        }

        if (lines.empty()) {
            if (!m_isRunning.load()) {
                m_logTimer.Stop();
            }
            return;
        }

        auto box = LogBox();
        auto current = std::wstring(box.Text());
        for (auto const& line : lines) {
            if (!current.empty()) current += L"\n";
            current += line;

            if (!m_urlOpened.load() && line.find(m_targetUrl) != std::wstring::npos) {
                m_urlOpened = true;
                OnServerReady();
            }
        }
        box.Text(current);
        box.Select(current.size(), 0);
    }

    void MainWindow::ScheduleLogFlush()
    {
        if (m_logTimer && !m_logTimer.IsRunning()) {
            m_logTimer.Start();
        }
    }

    void MainWindow::OnLogTimerTick(DispatcherQueueTimer const&, Windows::Foundation::IInspectable const&)
    {
        FlushLogs();
    }

    // ===== Process =====
    void MainWindow::StartServer()
    {
        if (m_isRunning.load()) return;

        auto llamaPath = Trim(std::wstring(LlamaPathBox().Text()));
        auto modelDir = Trim(std::wstring(ModelPathBox().Text()));
        auto modelDisplay = ModelCombo().SelectedItem()
            ? std::wstring(ModelCombo().SelectedItem().as<winrt::hstring>()) : L"";

        if (llamaPath.empty()) {
            ShowMessage(L"错误", L"请先设置 llama.cpp 路径");
            return;
        }
        if (!std::filesystem::is_directory(llamaPath)) {
            ShowMessage(L"错误", L"llama.cpp 路径不存在");
            return;
        }

        m_config.SetNamedValue(L"LlamaPath", JsonValue::CreateStringValue(llamaPath));
        m_config.SetNamedValue(L"ModelPath", JsonValue::CreateStringValue(modelDir));
        SaveConfig();
        SaveParams();

        auto modelOverride = m_paramEntries.count(L"model")
            ? Trim(std::wstring(m_paramEntries.at(L"model").Text())) : L"";
        auto modelsDir = m_paramEntries.count(L"models_dir")
            ? Trim(std::wstring(m_paramEntries.at(L"models_dir").Text())) : L"";
        auto modelsPreset = m_paramEntries.count(L"models_preset")
            ? Trim(std::wstring(m_paramEntries.at(L"models_preset").Text())) : L"";

        bool hasModel = !modelOverride.empty();
        if (!hasModel && !modelDisplay.empty()) {
            auto it = m_fileMapping.find(modelDisplay);
            if (it != m_fileMapping.end()) hasModel = true;
        }
        bool hasRouter = !modelsDir.empty() || !modelsPreset.empty();

        if (!hasModel && !hasRouter) {
            ShowMessage(L"错误", L"请先选择模型文件，或在参数配置中填写模型路径/模型目录");
            return;
        }

        std::filesystem::path exePath;
        auto p = std::filesystem::path(llamaPath);
        if (std::filesystem::exists(p / L"llama-server.exe")) {
            exePath = p / L"llama-server.exe";
        } else if (std::filesystem::exists(p / L"llama-server")) {
            exePath = p / L"llama-server";
        } else {
            ShowMessage(L"错误", L"在 LlamaPath 下未找到 llama-server 可执行文件");
            SetStatus(L"未找到 llama-server", L"danger");
            return;
        }

        std::wstring cmdLine = L"\"" + exePath.wstring() + L"\"";

        std::wstring modelPath;
        if (!modelOverride.empty()) {
            modelPath = modelOverride;
        } else if (!modelDisplay.empty()) {
            auto it = m_fileMapping.find(modelDisplay);
            if (it != m_fileMapping.end()) modelPath = it->second;
        }

        if (!modelPath.empty()) {
            cmdLine += L" -m \"" + modelPath + L"\"";
        }

        auto mmprojDisplay = MmprojCombo().SelectedItem()
            ? std::wstring(MmprojCombo().SelectedItem().as<winrt::hstring>()) : L"";
        if (!mmprojDisplay.empty()) {
            auto it = m_fileMapping.find(mmprojDisplay);
            if (it != m_fileMapping.end()) {
                cmdLine += L" --mmproj \"" + it->second + L"\"";
            }
        }

        for (auto const& group : PARAM_GROUPS) {
            for (auto const& param : group.params) {
                if (param.key == L"model") continue;
                auto it = m_paramEntries.find(param.key);
                if (it == m_paramEntries.end()) continue;
                auto val = Trim(std::wstring(it->second.Text()));
                if (val.empty()) continue;
                cmdLine += L" " + param.flag;
                if (FLAG_PARAMS.find(param.key) == FLAG_PARAMS.end()) {
                    cmdLine += L" \"" + val + L"\"";
                }
            }
        }

        auto host = m_paramEntries.count(L"host")
            ? Trim(std::wstring(m_paramEntries.at(L"host").Text())) : L"";
        auto port = m_paramEntries.count(L"port")
            ? Trim(std::wstring(m_paramEntries.at(L"port").Text())) : L"";
        if (host.empty()) host = L"127.0.0.1";
        if (port.empty()) port = L"8080";
        m_targetUrl = L"http://" + host + L":" + port;
        m_browserUrl = L"http://127.0.0.1:" + port;

        SECURITY_ATTRIBUTES sa = { sizeof(sa), nullptr, TRUE };
        HANDLE hWrite = nullptr;
        if (!CreatePipe(&m_hChildStdoutRd, &hWrite, &sa, 0)) {
            AppendLog(L"[错误] 创建管道失败");
            return;
        }
        SetHandleInformation(m_hChildStdoutRd, HANDLE_FLAG_INHERIT, 0);

        STARTUPINFOW si = { sizeof(si) };
        si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdOutput = hWrite;
        si.hStdError = hWrite;

        std::vector<wchar_t> mutableCmdLine(cmdLine.begin(), cmdLine.end());
        mutableCmdLine.push_back(L'\0');

        PROCESS_INFORMATION pi = { 0 };
        auto workDir = llamaPath;
        if (!workDir.empty() && workDir.back() != L'\\' && workDir.back() != L'/') workDir += L'\\';

        BOOL created = CreateProcessW(
            exePath.c_str(),
            mutableCmdLine.data(),
            nullptr, nullptr, TRUE,
            CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
            nullptr,
            workDir.empty() ? nullptr : workDir.c_str(),
            &si, &pi);

        CloseHandle(hWrite);

        if (!created) {
            AppendLog(L"[错误] 启动失败");
            CloseHandle(m_hChildStdoutRd);
            m_hChildStdoutRd = nullptr;
            return;
        }

        m_pi = pi;
        m_isRunning = true;
        m_urlOpened = false;
        UpdateActionButton();
        OpenUrlBtn().IsEnabled(false);
        SetStatus(L"正在启动...", L"warning");

        AppendLog(L"[系统] 启动 llama-server");
        AppendLog(L"[系统] 工作目录: " + llamaPath);
        AppendLog(L"[系统] 可执行文件: " + exePath.wstring());

        m_monitorThread = std::thread(&MainWindow::MonitorOutput, this);
        ScheduleLogFlush();
    }

    void MainWindow::StopServer()
    {
        if (m_pi.hProcess) {
            TerminateProcess(m_pi.hProcess, 1);
            AppendLog(L"[系统] 正在停止服务...");
        }
    }

    void MainWindow::MonitorOutput()
    {
        std::vector<char> buffer(4096);
        std::string lineBuf;
        DWORD bytesRead = 0;

        while (true) {
            BOOL ok = ReadFile(m_hChildStdoutRd, buffer.data(), static_cast<DWORD>(buffer.size()), &bytesRead, nullptr);
            if (!ok || bytesRead == 0) break;

            lineBuf.append(buffer.data(), bytesRead);
            size_t pos = 0;
            while ((pos = lineBuf.find('\n')) != std::string::npos) {
                std::string line = lineBuf.substr(0, pos);
                if (!line.empty() && line.back() == '\r') line.pop_back();
                lineBuf.erase(0, pos + 1);

                if (!line.empty()) {
                    int wlen = MultiByteToWideChar(CP_UTF8, 0, line.c_str(), -1, nullptr, 0);
                    if (wlen > 1) {
                        std::wstring wline(wlen - 1, 0);
                        MultiByteToWideChar(CP_UTF8, 0, line.c_str(), -1, wline.data(), wlen);
                        std::lock_guard lock(m_logMutex);
                        m_logQueue.push_back(wline);
                    }
                }
            }
        }

        if (!lineBuf.empty()) {
            int wlen = MultiByteToWideChar(CP_UTF8, 0, lineBuf.c_str(), -1, nullptr, 0);
            if (wlen > 1) {
                std::wstring wline(wlen - 1, 0);
                MultiByteToWideChar(CP_UTF8, 0, lineBuf.c_str(), -1, wline.data(), wlen);
                std::lock_guard lock(m_logMutex);
                m_logQueue.push_back(wline);
            }
        }

        CloseHandle(m_hChildStdoutRd);
        m_hChildStdoutRd = nullptr;

        DWORD exitCode = 0;
        GetExitCodeProcess(m_pi.hProcess, &exitCode);
        WaitForSingleObject(m_pi.hProcess, INFINITE);

        CloseHandle(m_pi.hThread);
        CloseHandle(m_pi.hProcess);
        m_pi = { 0 };

        DispatcherQueue().TryEnqueue([this, exitCode]() {
            OnProcessExit(static_cast<int>(exitCode));
        });
    }

    void MainWindow::OnProcessExit(int code)
    {
        m_isRunning = false;
        m_logTimer.Stop();
        UpdateActionButton();
        OpenUrlBtn().IsEnabled(false);
        if (code != 0) {
            SetStatus(L"进程已退出，返回码: " + std::to_wstring(code), L"danger");
            AppendLog(L"[系统] 进程退出，返回码: " + std::to_wstring(code));
        } else {
            SetStatus(L"已停止", L"");
            AppendLog(L"[系统] 进程已结束");
        }
        FlushLogs();
    }

    void MainWindow::OnServerReady()
    {
        AppendLog(L"[系统] 检测到服务地址: " + m_targetUrl);
        SetStatus(L"启动成功", L"success");
        OpenUrlBtn().IsEnabled(true);
    }

    // ===== UI helpers =====
    void MainWindow::UpdateActionButton()
    {
        if (m_isRunning.load()) {
            ActionBtn().Content(box_value(L"⏹ 停止"));
            ActionBtn().Background(SolidColorBrush(Windows::UI::Colors::Crimson()));
        } else {
            ActionBtn().Content(box_value(L"▶ 启动"));
            ActionBtn().Background(SolidColorBrush(Windows::UI::Colors::ForestGreen()));
        }
    }

    void MainWindow::SetStatus(std::wstring const& text, std::wstring const& style)
    {
        StatusBlock().Text(text);
        if (style == L"danger") {
            StatusBlock().Foreground(SolidColorBrush(Windows::UI::Colors::Crimson()));
        } else if (style == L"warning") {
            StatusBlock().Foreground(SolidColorBrush(Windows::UI::Colors::DarkOrange()));
        } else if (style == L"success") {
            StatusBlock().Foreground(SolidColorBrush(Windows::UI::Colors::ForestGreen()));
        } else {
            StatusBlock().ClearValue(TextBlock::ForegroundProperty());
        }
    }

    void MainWindow::ShowMessage(std::wstring const& title, std::wstring const& content)
    {
        auto windowNative = this->try_as<::IWindowNative>();
        HWND hwnd = nullptr;
        if (windowNative) windowNative->get_WindowHandle(&hwnd);
        MessageBoxW(hwnd, content.c_str(), title.c_str(), MB_OK | MB_ICONWARNING);
    }

    void MainWindow::OnClosed(IInspectable const&, WindowEventArgs const&)
    {
        if (auto item = ModelCombo().SelectedItem()) {
            auto display = std::wstring(item.as<winrt::hstring>());
            auto it = m_fileMapping.find(display);
            if (it != m_fileMapping.end()) {
                m_config.SetNamedValue(L"ModelFilePath", JsonValue::CreateStringValue(it->second));
            }
        }
        if (auto item = MmprojCombo().SelectedItem()) {
            auto display = std::wstring(item.as<winrt::hstring>());
            auto it = m_fileMapping.find(display);
            if (it != m_fileMapping.end()) {
                m_config.SetNamedValue(L"MmprojPath", JsonValue::CreateStringValue(it->second));
            }
        }
        SaveParams();

        if (m_pi.hProcess) {
            TerminateProcess(m_pi.hProcess, 1);
            if (m_monitorThread.joinable()) {
                m_monitorThread.detach();
            }
            CloseHandle(m_pi.hProcess);
            CloseHandle(m_pi.hThread);
            m_pi = { 0 };
        }
        if (m_hChildStdoutRd) {
            CloseHandle(m_hChildStdoutRd);
            m_hChildStdoutRd = nullptr;
        }
    }

    // ===== Navigation & Actions =====
    void MainWindow::NavBasic_Click(IInspectable const&, RoutedEventArgs const&)
    {
        ShowPage(true);
    }

    void MainWindow::NavParam_Click(IInspectable const&, RoutedEventArgs const&)
    {
        ShowPage(false);
    }

    void MainWindow::ThemeBtn_Click(IInspectable const&, RoutedEventArgs const&)
    {
        auto current = m_themeMode;
        if (current == L"auto") current = GetSystemTheme();
        auto next = (current == L"dark") ? L"light" : L"dark";
        m_themeMode = next;
        ApplyTheme(next, true);
    }

    void MainWindow::ActionBtn_Click(IInspectable const&, RoutedEventArgs const&)
    {
        if (m_isRunning.load()) {
            StopServer();
        } else {
            StartServer();
        }
    }

    void MainWindow::OpenUrlBtn_Click(IInspectable const&, RoutedEventArgs const&)
    {
        ShellExecuteW(nullptr, L"open", m_browserUrl.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
        AppendLog(L"[系统] 已打开浏览器: " + m_browserUrl);
    }

    winrt::fire_and_forget MainWindow::BrowseLlama_Click(IInspectable const&, RoutedEventArgs const&)
    {
        auto lifetime = get_strong();
        auto picker = Windows::Storage::Pickers::FolderPicker();
        picker.SuggestedStartLocation(Windows::Storage::Pickers::PickerLocationId::Desktop);
        picker.FileTypeFilter().Append(L"*");

        auto windowNative = this->try_as<::IWindowNative>();
        HWND hwnd = nullptr;
        if (windowNative) windowNative->get_WindowHandle(&hwnd);
        if (hwnd) {
            auto init = picker.as<::IInitializeWithWindow>();
            if (init) init->Initialize(hwnd);
        }

        auto folder = co_await picker.PickSingleFolderAsync();
        if (folder) {
            DispatcherQueue().TryEnqueue([this, path = std::wstring(folder.Path())]() {
                LlamaPathBox().Text(path);
                m_config.SetNamedValue(L"LlamaPath", JsonValue::CreateStringValue(path));
                SaveConfig();
            });
        }
    }

    winrt::fire_and_forget MainWindow::BrowseModel_Click(IInspectable const&, RoutedEventArgs const&)
    {
        auto lifetime = get_strong();
        auto picker = Windows::Storage::Pickers::FolderPicker();
        picker.SuggestedStartLocation(Windows::Storage::Pickers::PickerLocationId::Desktop);
        picker.FileTypeFilter().Append(L"*");

        auto windowNative = this->try_as<::IWindowNative>();
        HWND hwnd = nullptr;
        if (windowNative) windowNative->get_WindowHandle(&hwnd);
        if (hwnd) {
            auto init = picker.as<::IInitializeWithWindow>();
            if (init) init->Initialize(hwnd);
        }

        auto folder = co_await picker.PickSingleFolderAsync();
        if (folder) {
            DispatcherQueue().TryEnqueue([this, path = std::wstring(folder.Path())]() {
                ModelPathBox().Text(path);
                m_config.SetNamedValue(L"ModelPath", JsonValue::CreateStringValue(path));
                SaveConfig();
                RefreshModelList();
            });
        }
    }

    void MainWindow::RefreshModel_Click(IInspectable const&, RoutedEventArgs const&)
    {
        RefreshModelList();
    }
}
