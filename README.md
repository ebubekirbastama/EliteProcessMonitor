# Elite Process Monitor Pro

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Qt-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Windows](https://img.shields.io/badge/Platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)
![ETW](https://img.shields.io/badge/Telemetry-Windows%20ETW-5C2D91?style=for-the-badge)
![License](https://img.shields.io/badge/License-Apache%202.0-orange?style=for-the-badge)

> Windows üzerinde süreçleri ve sistem kaynaklarını izlemek için geliştirilmiş, PySide6 tabanlı masaüstü process monitoring uygulaması.

## 📌 Proje Hakkında

**Elite Process Monitor Pro**, Windows üzerinde çalışan süreçleri izlemek, süreç bazlı kaynak kullanımını geçmişe dönük saklamak ve sistem performansını tek bir masaüstü arayüzünde takip etmek amacıyla geliştirilmiştir.

Kaynak koduna göre uygulama özellikle süreç bazında **CPU, RAM, GPU ve disk/ağ metrikleri**, Windows **ETW (Event Tracing for Windows)** üzerinden süreç bazlı ağ trafiği ve sistem seviyesinde ek performans ölçümleri üzerinde çalışır. Veriler SQLite veritabanında tutulur. fileciteturn274file0

Uygulama Windows yönetici yetkisini otomatik olarak istemektedir; bunun nedeni süreç bazlı ağ ölçümünde Windows ETW oturumunun kullanılmasıdır. fileciteturn274file0

## ✨ Öne Çıkan Özellikler

- 🔎 Çalışan Windows süreçlerini izleme
- 📊 Süreç bazlı CPU ve RAM ölçümü
- 🎮 GPU ve GPU memory metrikleri
- 💽 Süreç bazlı disk okuma/yazma hızları
- 🌐 Süreç bazlı network upload/download ölçümü
- 🧩 Windows ETW tabanlı ağ ölçümü
- 🌡️ Sıcaklık verisi için destek
- 🗃️ SQLite ile geçmiş metriklerin saklanması
- 📈 Geçmiş veriler üzerinden performans takibi
- 🖥️ PySide6 masaüstü arayüzü
- 🔔 Windows system tray desteği
- ⚙️ Otomatik UAC/yönetici yetkisi yükseltme
- 🧪 ETW ve bağımlılık tanılama kayıtları
- 📦 PyInstaller ile Windows EXE oluşturma

## 🧰 Teknoloji Kartları

| Teknoloji | Kullanım |
|---|---|
| 🐍 **Python** | Ana uygulama dili |
| 🖥️ **PySide6 / Qt** | Masaüstü kullanıcı arayüzü |
| 📊 **psutil** | Süreç ve sistem kaynak metrikleri |
| ⚡ **Windows ETW** | Süreç bazlı ağ olaylarının izlenmesi |
| 🔌 **pywintrace 0.2.0** | Python üzerinden ETW erişimi |
| 🗃️ **SQLite** | Tarihsel metrik veri deposu |
| 📦 **PyInstaller** | Windows EXE paketleme |
| 🪟 **Windows UAC** | Yönetici yetkisi yükseltme |

Resmî bağımlılık listesinde `PySide6`, `psutil`, `pywintrace==0.2.0` ve `pyinstaller` bulunuyor. fileciteturn275file0

## 📁 Proje Yapısı

```text
EliteProcessMonitor/
├── EliteProcessMonitor.pyw       # Ana masaüstü uygulaması
├── requirements.txt              # Python bağımlılıkları
├── KURULUM_VE_BASLAT.bat         # Kurulum / onarım / başlatma
├── build_exe.bat                 # PyInstaller EXE oluşturma
├── ETW_ONAR.bat                  # ETW onarım yardımcı betiği
├── HATA_GOSTER.bat               # Hata/diagnostic yardımcı betiği
├── LICENSE                       # Apache License 2.0
├── .gitignore
└── README.md
```

Repository'nin ana çalışma dosyası `EliteProcessMonitor.pyw` dosyasıdır; yanında kurulum, tanılama ve EXE oluşturma için batch araçları bulunmaktadır. fileciteturn273file0

### Veri dizini

Uygulama kullanıcı verilerini Windows'ta:

```text
%LOCALAPPDATA%\EliteProcessMonitor\
```

altında tutar. SQLite veritabanı:

```text
elite_process_monitor.db
```

olarak oluşturulur. Başlangıç ve ETW tanılama kayıtları da aynı veri dizini altında tutulur. fileciteturn274file0

## 🚀 Kurulum

### Yöntem 1 — Otomatik kurulum

Windows'ta repository klasöründeki `KURULUM_VE_BASLAT.bat` dosyasını çalıştırın.

Script yönetici yetkisi ister, Python kurulumunu kontrol eder, `pip`'i günceller ve gerekli paketleri kurar. Ardından ETW modülünü test edip uygulamayı `pythonw.exe` ile başlatır. fileciteturn276file0

### Yöntem 2 — Manuel kurulum

```bash
python -m pip install -r requirements.txt
```

Ardından Windows üzerinde:

```bash
pythonw EliteProcessMonitor.pyw
```

> ETW tabanlı süreç ağı ölçümünün çalışması için Windows ve yönetici yetkisi gereklidir.

## ▶️ Kullanım

1. Windows üzerinde uygulamayı başlatın.
2. UAC isteği gelirse yönetici iznini onaylayın.
3. Uygulama çalışan süreçleri ve kaynak kullanımını toplamaya başlar.
4. Süreç bazındaki CPU/RAM/GPU/disk/network değerlerini arayüzden inceleyin.
5. İlgili süreçlerin geçmiş metriklerini SQLite üzerinden takip edin.
6. ETW kullanılamıyorsa `%LOCALAPPDATA%\EliteProcessMonitor` altındaki tanılama kayıtlarını kontrol edin.

Uygulama eksik `psutil` veya `PySide6` bağımlılığında kullanıcıya kurulum yönlendirmesi verir; ETW bağımlılığı için de `pywintrace==0.2.0` kurulumu/onarımı denenir. fileciteturn274file0

## 🔍 Çalışma Akışı

```text
                 Elite Process Monitor Pro
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       Windows Processes          Windows ETW
              │                         │
              ▼                         ▼
       psutil Metrics          Kernel Network Events
              │                         │
       ┌──────┼──────┐                  │
       ▼      ▼      ▼                  ▼
      CPU    RAM    GPU/Disk       PID + Network Bytes
       │      │      │                  │
       └──────┴──────┴──────────┬───────┘
                                ▼
                          SQLite Database
                                │
                                ▼
                         PySide6 Dashboard
```

SQLite katmanı süreç örneklerinin yanında disk, network, sıcaklık ve GPU kaynak bilgilerini saklamak üzere genişletilmiş alanlara sahiptir. Sistem seviyesinde network geçmişi için ayrı `system_samples` tablosu bulunur. fileciteturn274file0

## 🗃️ Veri Saklama

Uygulama SQLite kullanır ve eski veritabanlarını bozmadan yeni metrik kolonları eklemek üzere tablo şemasını kontrol eder.

Süreç kayıtlarında başlıca PID, process creation time, process name, executable path, timestamp, CPU, RAM, GPU, GPU memory, disk/network hızları, sıcaklık ve network toplam byte alanları tutulabilir. fileciteturn274file0

## ⚠️ Teknik Sınırlamalar

Bu proje **Windows odaklı bir sistem izleme aracıdır** ve ETW nedeniyle platform bağımlılığı yüksektir.

- ETW yalnızca Windows üzerinde kullanılabilir.
- Süreç bazlı ağ ölçümü yönetici yetkisine bağlıdır.
- `pywintrace==0.2.0` belirli bir sürüme sabitlenmiştir.
- GPU ve sıcaklık verilerinin kullanılabilirliği donanıma/sürücülere göre değişebilir.
- ETW provider erişimi başarısız olabilir; uygulama bunun için tanılama dosyaları üretir.
- Uzun süreli izleme SQLite verisinin büyümesine neden olabilir.
- ETW olaylarının maliyeti izleme kapsamına ve sisteme göre değişebilir.

## 🔐 Güvenli Kullanım

Uygulama yönetici yetkisiyle çalışabildiği ve sistem/process bilgilerine erişebildiği için yalnızca **kendi bilgisayarınızda veya yönetme yetkiniz bulunan Windows sistemlerinde** kullanılmalıdır.

Kaynak kodunda UAC yükseltmesi `ShellExecuteW(..., "runas", ...)` üzerinden gerçekleştirilmektedir. Kullanıcı UAC isteğini reddederse uygulama açılabilir ancak ETW kartında yetki hatası görülebilir. fileciteturn274file0

- SQLite veritabanını herkese açık klasörlere taşımayın.
- Tanılama dosyalarını paylaşmadan önce sistem bilgilerini kontrol edin.
- Sürekli ETW izleme yapmadan önce performans etkisini test edin.
- Uygulamayı güvenilmeyen kullanıcı hesaplarında yönetici olarak çalıştırmayın.

## 🛠️ Modernizasyon Önerileri

- Python sürüm matrisi ve CI testleri
- ETW katmanını ayrı worker/service mimarisine ayırma
- SQLite retention, arşivleme ve otomatik temizlik
- Büyük veri setleri için aggregation stratejileri
- GPU ve sensör sağlayıcıları için abstraction katmanı
- ETW provider/event ID'lerini yapılandırılabilir hale getirme
- Daha gelişmiş process tree ve parent/child ilişkileri
- CSV/JSON export
- Alarm eşikleri ve bildirim sistemi
- Kontrollü dependency bootstrap
- Windows Service / tray worker mimarisi
- GitHub Actions ile otomatik EXE build
- Unit/integration testleri ve statik analiz

## 📦 Windows EXE Oluşturma

Repository'deki `build_exe.bat` scripti PyInstaller kullanarak yönetici yetkisi isteyen tek dosyalık Windows EXE üretir. Kullanılan seçenekler arasında `--onefile`, `--windowed`, `--uac-admin` ve `--collect-all etw` bulunur. fileciteturn277file0

```bat
build_exe.bat
```

Beklenen çıktı:

```text
dist\EliteProcessMonitorPro.exe
```

## 🧪 Tanılama

Başlangıç sorunlarında `HATA_GOSTER.bat`, ETW kurulumu/onarımı için `ETW_ONAR.bat` kullanılabilir.

Uygulama ayrıca başlangıç hatalarını ve ETW tanılama bilgilerini `%LOCALAPPDATA%\EliteProcessMonitor` altında kaydetmek üzere tasarlanmıştır. fileciteturn273file0turn274file0

## 📄 Lisans

Bu repository **Apache License 2.0** ile lisanslanmıştır. Lisansın tam metni repository'deki `LICENSE` dosyasındadır. fileciteturn278file0

## 👤 Geliştirici

**Ebubekir Bastama**  
GitHub: [@ebubekirbastama](https://github.com/ebubekirbastama)

---

⭐ Projeyi faydalı bulduysanız repository'ye yıldız bırakabilirsiniz.
