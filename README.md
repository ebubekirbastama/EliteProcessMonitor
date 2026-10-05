# Elite Process Monitor Pro v8

Bu sürüm v7'deki "ETW KAPALI / pywintrace paketi yüklenemedi" durumunu hedefler.

## İlk çalıştırma
`KURULUM_VE_BASLAT.bat` dosyasını normal çift tıklayın. Dosya kendisi yönetici yetkisi ister.

Kurulum sırasında aynı Python ortamına şu paketler yüklenir:
- PySide6
- psutil
- pywintrace 0.2.0
- pyinstaller

Program `.pyw` dosyasından doğrudan açılırsa ve `etw` modülü eksikse, v8 aynı Python yorumlayıcısı ile `pywintrace==0.2.0` kurmayı otomatik olarak dener.

## ETW hâlâ kapalıysa
`ETW_ONAR.bat` dosyasını çalıştırın. Paket temiz şekilde kaldırılıp yeniden kurulur ve `import etw` testi yapılır.

Tanılama dosyaları:
- `%LOCALAPPDATA%\EliteProcessMonitor\etw_diagnostic.txt`
- `%LOCALAPPDATA%\EliteProcessMonitor\pywintrace_install.txt`

Bu iki dosya, modül bulunamaması ile ETW oturumu açılamaması sorunlarını birbirinden ayırır.
