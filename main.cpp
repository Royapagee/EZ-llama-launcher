#include "pch.h"
#include "App.h"
#include "App.g.cpp"

using namespace winrt;
using namespace Microsoft::UI::Xaml;

int __stdcall wWinMain(HINSTANCE, HINSTANCE, PWSTR, int)
{
    winrt::init_apartment(apartment_type::single_threaded);
    Application::Start([](auto&&)
    {
        make<::winrt::EZLlamaLauncher::implementation::App>();
    });
    return 0;
}
