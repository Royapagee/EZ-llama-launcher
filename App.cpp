#include "pch.h"
#include "App.h"
#include "App.g.cpp"
#include "MainWindow.h"

using namespace winrt;
using namespace Microsoft::UI::Xaml;

namespace winrt::EZLlamaLauncher::implementation
{
    App::App()
    {
    }

    void App::OnLaunched(LaunchActivatedEventArgs const&)
    {
        m_window = make<MainWindow>();
        m_window.Activate();
    }
}
