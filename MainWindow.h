#pragma once
#include "MainWindow.g.h"

namespace winrt::EZLlamaLauncher::implementation
{
    struct MainWindow : MainWindowT<MainWindow>
    {
        MainWindow();

        // XAML event handlers
        void NavBasic_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);
        void NavParam_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);
        void ThemeBtn_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);
        void ActionBtn_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);
        void OpenUrlBtn_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);
        void BrowseLlama_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);
        void BrowseModel_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);
        void RefreshModel_Click(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&);

    private:
        // Config
        std::filesystem::path m_configPath;
        Windows::Data::Json::JsonObject m_config{ nullptr };
        std::wstring m_themeMode = L"auto";

        // Model scan cache
        using file_time = std::filesystem::file_time_type;
        std::unordered_map<std::wstring, std::pair<file_time, std::vector<std::wstring>>> m_modelCache;
        std::map<std::wstring, std::wstring> m_fileMapping; // display -> abs path

        // Param UI
        std::map<std::wstring, Microsoft::UI::Xaml::Controls::TextBox> m_paramEntries;

        // Process management
        PROCESS_INFORMATION m_pi{ 0 };
        HANDLE m_hChildStdoutRd = nullptr;
        std::thread m_monitorThread;
        std::atomic<bool> m_isRunning{ false };
        std::atomic<bool> m_urlOpened{ false };
        std::wstring m_targetUrl = L"http://127.0.0.1:8080";
        std::wstring m_browserUrl = L"http://127.0.0.1:8080";

        // Logging
        std::mutex m_logMutex;
        std::vector<std::wstring> m_logQueue;
        Microsoft::UI::Dispatching::DispatcherQueueTimer m_logTimer{ nullptr };

        // Debounced save
        Microsoft::UI::Dispatching::DispatcherQueueTimer m_saveTimer{ nullptr };

        // Initialization
        void BuildParamPage();
        void ShowPage(bool basic);

        // Config helpers
        std::filesystem::path GetConfigPath();
        void LoadConfig();
        void SaveConfig();
        void SaveParams();
        void ScheduleSaveParams();

        // Theme
        void ApplyTheme(std::wstring const& mode, bool save = true);
        std::wstring GetSystemTheme();

        // Models
        std::vector<std::wstring> GetModelFiles(std::wstring const& path);
        void RefreshModelList();

        // Logging
        void AppendLog(std::wstring const& msg);
        void FlushLogs();
        void ScheduleLogFlush();
        void OnLogTimerTick(Microsoft::UI::Dispatching::DispatcherQueueTimer const&, Windows::Foundation::IInspectable const&);
        void OnSaveTimerTick(Microsoft::UI::Dispatching::DispatcherQueueTimer const&, Windows::Foundation::IInspectable const&);

        // Process
        void StartServer();
        void StopServer();
        void MonitorOutput();
        void OnProcessExit(int code);
        void OnServerReady();

        // UI helpers
        void UpdateActionButton();
        void SetStatus(std::wstring const& text, std::wstring const& style = L"");
        void ShowMessage(std::wstring const& title, std::wstring const& content);
        void OnClosed(Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::WindowEventArgs const&);

        // Utilities
        static std::wstring Trim(std::wstring const& s);
    };
}
