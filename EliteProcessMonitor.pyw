# -*- coding: utf-8 -*-
import os, sys, time, math, html, sqlite3, shutil, subprocess, json, re, threading
from pathlib import Path
from datetime import datetime
from statistics import mean

# -----------------------------------------------------------------------------
# Coder By&Ebubekir Bastama
# Windows yönetici yetkisi
# Süreç bazlı ağ ölçümü Microsoft ETW oturumu açtığı için program kendi kendini
# UAC ile yönetici olarak yeniden başlatır. Böylece kullanıcı ayrıca sağ tık
# "Yönetici olarak çalıştır" yapmak zorunda kalmaz.
# -----------------------------------------------------------------------------
def is_windows_admin():
    if os.name != 'nt':
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Windows'ta UAC isteyip aynı programı yönetici olarak yeniden başlatır.

    Frozen EXE ve .py/.pyw çalışma biçimlerinin ikisini de destekler.
    Başarıyla yeni süreç oluşturulursa True döner ve mevcut süreç kapanmalıdır.
    """
    if os.name != 'nt' or is_windows_admin():
        return False
    try:
        import ctypes
        if getattr(sys, 'frozen', False):
            executable = sys.executable
            args = ' '.join('"'+a.replace('"','\\"')+'"' for a in sys.argv[1:])
        else:
            executable = sys.executable
            script = str(Path(__file__).resolve())
            args_list = [script] + sys.argv[1:]
            args = ' '.join('"'+a.replace('"','\\"')+'"' for a in args_list)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, 'runas', executable, args, str(Path.cwd()), 1
        )
        return int(rc) > 32
    except Exception:
        return False


# Program doğrudan .pyw/.exe ile açıldığında da otomatik yükselt.
# UAC reddedilirse program yine açılır; ETW kartında gerçek hata gösterilir.
if os.name == 'nt' and not is_windows_admin():
    if relaunch_as_admin():
        raise SystemExit(0)

# Başlangıç bağımlılık kontrolü: .pyw hata konsolunu gizlediği için eksik paket varsa
# kullanıcıya Windows mesaj kutusunda açıkça ne yapılacağını gösterir.
def _startup_error(message):
    try:
        log_dir = Path(os.getenv('LOCALAPPDATA') or str(Path.home())) / 'EliteProcessMonitor'
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / 'startup_error.log').write_text(str(message), encoding='utf-8')
    except Exception:
        pass
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(message), 'Elite Process Monitor Pro - Başlatma Hatası', 0x10)
            return
        except Exception:
            pass
    print(message)

try:
    import psutil
except Exception as e:
    _startup_error(
        'Gerekli psutil paketi kurulu değil.\n\n'
        'Kurulum klasöründeki KURULUM_VE_BASLAT.bat dosyasını bir kez çalıştırın.\n\n'
        f'Teknik hata: {e}'
    )
    raise SystemExit(1)

# pywintrace/etw bağımlılığını otomatik onar. .pyw ile doğrudan açıldığında da
# kurulum eksikse sessizce pip üzerinden aynı Python ortamına yüklemeyi dener.
etw = None
_etw_import_error = ''
def _try_import_etw():
    global etw, _etw_import_error
    try:
        import importlib
        etw = importlib.import_module('etw')
        _etw_import_error = ''
        return True
    except Exception as e:
        _etw_import_error = f'{type(e).__name__}: {e}'
        etw = None
        return False

def _auto_install_pywintrace():
    if os.name != 'nt' or getattr(sys, 'frozen', False):
        return False
    if _try_import_etw():
        return True
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        cmd = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'pywintrace==0.2.0']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, creationflags=flags)
        diag = data_dir() / 'pywintrace_install.txt' if 'data_dir' in globals() else Path(os.getenv('LOCALAPPDATA') or Path.home()) / 'EliteProcessMonitor' / 'pywintrace_install.txt'
        diag.parent.mkdir(parents=True, exist_ok=True)
        diag.write_text('COMMAND: '+ ' '.join(cmd) + '\nRETURN: ' + str(r.returncode) + '\n\nSTDOUT:\n' + (r.stdout or '') + '\n\nSTDERR:\n' + (r.stderr or ''), encoding='utf-8')
        if r.returncode == 0:
            import importlib
            importlib.invalidate_caches()
            return _try_import_etw()
    except Exception as e:
        _etw_import_error = f'Kurulum hatası: {type(e).__name__}: {e}'
    return False

_auto_install_pywintrace()

try:
    from PySide6.QtCore import Qt, QTimer, QPointF
    from PySide6.QtGui import QColor, QFont, QPainter, QPen, QAction, QIcon, QPolygonF, QBrush
    from PySide6.QtWidgets import (
    QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QPushButton,QLineEdit,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,
    QFileDialog,QFrame,QSplitter,QAbstractItemView,QSizePolicy,QComboBox,
        QSystemTrayIcon,QMenu,QStyle
    )
except Exception as e:
    _startup_error(
        'Grafik arayüzü için PySide6 kurulu değil veya yüklenemedi.\n\n'
        'Kurulum klasöründeki KURULUM_VE_BASLAT.bat dosyasını bir kez çalıştırın.\n\n'
        'Manuel kurulum:  python -m pip install -r requirements.txt\n\n'
        f'Teknik hata: {e}'
    )
    raise SystemExit(1)

APP_NAME='Elite Process Monitor Pro'
SAMPLE_INTERVAL_MS=5000
GPU_REFRESH_SEC=15
TEMP_REFRESH_SEC=30
MAX_CHART_POINTS=180
GOLD='#D4AF37'; GOLD2='#F0D777'; BG='#17191D'; SURFACE='#202329'; SURFACE2='#292D34'; BORDER='#3B4049'; TEXT='#F4F4F4'; MUTED='#9DA3AE'


def data_dir():
    p=Path(os.getenv('LOCALAPPDATA') or Path.home())/'EliteProcessMonitor'
    p.mkdir(parents=True,exist_ok=True)
    return p
DB_PATH=data_dir()/'elite_process_monitor.db'


def fmt_duration(sec):
    sec=max(0,int(sec or 0)); d,r=divmod(sec,86400); h,r=divmod(r,3600); m,s=divmod(r,60)
    return f'{d} gün {h:02}:{m:02}:{s:02}' if d else f'{h:02}:{m:02}:{s:02}'


def fmt_pct(v, digits=1): return 'N/A' if v is None else f'{v:.{digits}f}%'


def fmt_size(num_bytes):
    if num_bytes is None: return 'N/A'
    n=float(num_bytes)
    units=['B','KB','MB','GB','TB']
    i=0
    while abs(n)>=1024 and i<len(units)-1:
        n/=1024.0; i+=1
    return f'{n:.2f} {units[i]}' if i>=3 else f'{n:.1f} {units[i]}'


def fmt_rate(bps):
    return 'N/A' if bps is None else f'{fmt_size(bps)}/sn'


def fmt_temp(v): return 'N/A' if v is None else f'{v:.1f} °C'


def safe_mean(vals):
    v=[x for x in vals if x is not None]
    return mean(v) if v else None


class DB:
    def __init__(self,path):
        self.c=sqlite3.connect(path)
        self.c.execute('''CREATE TABLE IF NOT EXISTS samples(
            id INTEGER PRIMARY KEY AUTOINCREMENT,pid INTEGER,create_time REAL,name TEXT,exe TEXT,ts REAL,
            cpu REAL,ram_mb REAL,ram_pct REAL,gpu REAL,gpu_mem_mb REAL)''')
        # Eski veritabanlarını bozmadan profesyonel metrikleri ekle.
        cols={r[1] for r in self.c.execute('PRAGMA table_info(samples)')}
        additions={
            'disk_read_bps':'REAL','disk_write_bps':'REAL','net_up_bps':'REAL','net_down_bps':'REAL',
            'temp_c':'REAL','gpu_source':'TEXT','net_sent_total':'INTEGER','net_recv_total':'INTEGER','net_scope':'TEXT'
        }
        for col,typ in additions.items():
            if col not in cols:
                self.c.execute(f'ALTER TABLE samples ADD COLUMN {col} {typ}')
        self.c.execute('CREATE INDEX IF NOT EXISTS idx_samples ON samples(pid,create_time,ts)')
        self.c.execute('''CREATE TABLE IF NOT EXISTS system_samples(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, net_up_bps REAL, net_down_bps REAL,
            bytes_sent_total INTEGER, bytes_recv_total INTEGER, temp_c REAL)''')
        self.c.execute('CREATE INDEX IF NOT EXISTS idx_system_samples_ts ON system_samples(ts)')
        self.c.commit()
    def add(self,row):
        self.c.execute('''INSERT INTO samples(
            pid,create_time,name,exe,ts,cpu,ram_mb,ram_pct,gpu,gpu_mem_mb,
            disk_read_bps,disk_write_bps,net_up_bps,net_down_bps,temp_c,gpu_source,
            net_sent_total,net_recv_total,net_scope
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',row)
    def add_system(self,row):
        self.c.execute('''INSERT INTO system_samples(ts,net_up_bps,net_down_bps,bytes_sent_total,bytes_recv_total,temp_c) VALUES(?,?,?,?,?,?)''',row)
    def system_history(self,since=None):
        q='SELECT ts,net_up_bps,net_down_bps,bytes_sent_total,bytes_recv_total,temp_c FROM system_samples'
        a=[]
        if since is not None:
            q+=' WHERE ts>=?'; a.append(since)
        q+=' ORDER BY ts'
        return self.c.execute(q,a).fetchall()
    def flush(self):
        self.c.commit()
    def history(self,pid,ct,since=None):
        q='''SELECT ts,cpu,ram_mb,ram_pct,gpu,gpu_mem_mb,disk_read_bps,disk_write_bps,
             net_up_bps,net_down_bps,temp_c,gpu_source,net_sent_total,net_recv_total,net_scope FROM samples
             WHERE pid=? AND ABS(create_time-?)<0.01'''
        a=[pid,ct]
        if since is not None: q+=' AND ts>=?'; a.append(since)
        q+=' ORDER BY ts'
        return self.c.execute(q,a).fetchall()
    def close(self): self.c.close()


class ProcessNetworkETW:
    """Seçilen PID'ler için Windows ETW üzerinden TCP/UDP byte muhasebesi.

    Kaynak: Microsoft-Windows-Kernel-Network
    IPv4/IPv6 TCP send/receive ve UDP send/receive olaylarının PID + size
    alanlarını toplar. Sistem toplamını süreç verisi gibi göstermez.
    """
    SEND_IDS={10,26,42,58}
    RECV_IDS={11,27,43,59}
    PROVIDER_GUID='{7DD42A49-5329-4832-8DFD-43D979153A88}'

    def __init__(self):
        self.available=False
        self.error=''
        self.job=None
        self.backend='ETW'
        self._lock=threading.Lock()
        self._totals={}
        self._last={}
        self._events_seen=0
        self._started_at=None
        self.admin=is_windows_admin()
        self._diag=[]

        if os.name!='nt':
            self.error='ETW yalnız Windows üzerinde kullanılabilir.'
            return
        if not self.admin:
            self.error='Yönetici yetkisi yok. Program UAC ile yönetici olarak açılmalıdır.'
            self._write_diag()
            return
        if etw is None:
            self.error='ETW bileşeni yüklenemedi: ' + (_etw_import_error or 'pywintrace/etw bulunamadı')
            self._write_diag()
            return

        # Önce Windows'ta provider gerçekten kayıtlı mı kontrol et. Bu sadece
        # tanılama içindir; logman bulunamazsa ETW denemesi yine yapılır.
        try:
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            q=subprocess.run(
                ['logman','query','providers','Microsoft-Windows-Kernel-Network'],
                capture_output=True,text=True,timeout=5,creationflags=flags
            )
            self._diag.append(f'logman returncode={q.returncode}')
            if q.returncode!=0:
                self._diag.append((q.stderr or q.stdout or '').strip()[:500])
        except Exception as e:
            self._diag.append(f'logman kontrolü yapılamadı: {e}')

        # pywintrace sürümleri arasında küçük davranış farkları olabildiği için
        # iki güvenli ETW başlatma yolu denenir. Olay filtrelemesi callback içinde
        # yapılıyor; böylece provider tarafında gereksiz filtre uyumsuzluğu olmaz.
        attempts=[
            ('provider-default', None),
        ]
        errors=[]
        for label,keywords in attempts:
            try:
                if keywords is None:
                    provider=etw.ProviderInfo(
                        'Microsoft-Windows-Kernel-Network',
                        etw.GUID(self.PROVIDER_GUID)
                    )
                else:
                    provider=etw.ProviderInfo(
                        'Microsoft-Windows-Kernel-Network',
                        etw.GUID(self.PROVIDER_GUID),
                        any_keywords=keywords
                    )
                self.job=etw.ETW(
                    session_name=f'EliteProcessMonitorNetwork_{os.getpid()}_{int(time.time())}',
                    providers=[provider],
                    event_callback=self._on_event,
                    ignore_exists_error=True,
                    ring_buf_size=64,
                    min_buffers=2,
                    max_buffers=64,
                    callback_wait_time=0.0
                )
                self.job.start()
                self.available=True
                self.backend=f'ETW/{label}'
                self._started_at=time.time()
                self.error=''
                self._diag.append(f'ETW aktif: {self.backend}')
                break
            except Exception as e:
                try:
                    if self.job:
                        self.job.stop()
                except Exception:
                    pass
                self.job=None
                msg=f'{label}: {type(e).__name__}: {e}'
                errors.append(msg)
                self._diag.append(msg)

        if not self.available:
            self.error='ETW başlatılamadı. ' + ' | '.join(errors)
        self._write_diag()

    def _write_diag(self):
        try:
            lines=[
                f'Tarih: {datetime.now():%Y-%m-%d %H:%M:%S}',
                f'Yönetici: {self.admin}',
                f'Python: {sys.version}',
                f'Executable: {sys.executable}',
                f'ETW modülü: {getattr(etw,"__file__",None) if etw else None}',
                f'ETW import hatası: {_etw_import_error}',
                f'Aktif: {self.available}',
                f'Backend: {self.backend}',
                f'Hata: {self.error}',
                *self._diag,
            ]
            (data_dir()/'etw_diagnostic.txt').write_text('\n'.join(lines),encoding='utf-8')
        except Exception:
            pass

    def _on_event(self,event):
        try:
            event_id,data=event
            if event_id not in (self.SEND_IDS|self.RECV_IDS):
                return
            # Manifest alan adı PID ve size'dır. Bazı TDH sürümlerinde alan adı
            # farklı casing ile gelebileceği için toleranslı davran.
            pid_val=data.get('PID', data.get('Pid', data.get('pid')))
            size_val=data.get('size', data.get('Size', data.get('SIZE',0)))
            pid=int(pid_val)
            size=max(0,int(size_val or 0))
            if size<=0:
                return
            with self._lock:
                d=self._totals.setdefault(pid,[0,0])  # sent, recv
                if event_id in self.SEND_IDS:
                    d[0]+=size
                elif event_id in self.RECV_IDS:
                    d[1]+=size
                self._events_seen += 1
        except Exception:
            pass

    def ensure_pid(self,pid):
        now=time.time()
        with self._lock:
            cur=list(self._totals.get(pid,[0,0]))
            self._last[pid]=(cur[0],cur[1],now)

    def remove_pid(self,pid):
        with self._lock:
            self._last.pop(pid,None)

    def sample(self,pid,now=None):
        now=now or time.time()
        if not self.available:
            return {'up_bps':None,'down_bps':None,'sent_total':None,'recv_total':None,'scope':'unavailable'}
        with self._lock:
            sent,recv=self._totals.get(pid,[0,0])
            prev=self._last.get(pid)
            if not prev:
                self._last[pid]=(sent,recv,now)
                return {'up_bps':0.0,'down_bps':0.0,'sent_total':sent,'recv_total':recv,'scope':'process_etw'}
            ps,pr,pt=prev
            dt=max(.1,now-pt)
            up=max(0,(sent-ps)/dt)
            down=max(0,(recv-pr)/dt)
            self._last[pid]=(sent,recv,now)
            return {'up_bps':up,'down_bps':down,'sent_total':sent,'recv_total':recv,'scope':'process_etw'}

    @property
    def events_seen(self):
        with self._lock:
            return self._events_seen

    def stop(self):
        try:
            if self.job:
                self.job.stop()
        except Exception:
            pass


class UniversalGpuReader:
    """Windows WDDM sayaçları: NVIDIA + AMD + Intel. NVIDIA varsa nvidia-smi ile zenginleştirir."""
    def __init__(self):
        self.nvidia=shutil.which('nvidia-smi')
        self.last_read=0; self.cache={}; self.temp_cache=None; self.temp_last=0
        self._gpu_busy=False; self._temp_busy=False; self._lock=threading.Lock()

    def _ps(self, command, timeout=5):
        if os.name!='nt': return ''
        flags=subprocess.CREATE_NO_WINDOW
        exe=shutil.which('powershell') or shutil.which('pwsh')
        if not exe: return ''
        try:
            p=subprocess.run([exe,'-NoProfile','-ExecutionPolicy','Bypass','-Command',command],
                             capture_output=True,text=True,timeout=timeout,creationflags=flags)
            return p.stdout if p.returncode==0 else ''
        except Exception: return ''

    def _wddm(self):
        out={}
        cmd=r'''$ErrorActionPreference='SilentlyContinue';
$e=(Get-Counter '\GPU Engine(*)\Utilization Percentage').CounterSamples | Select-Object InstanceName,CookedValue;
$m=(Get-Counter '\GPU Process Memory(*)\Local Usage').CounterSamples | Select-Object InstanceName,CookedValue;
@{engine=$e;memory=$m}|ConvertTo-Json -Compress -Depth 4'''
        raw=self._ps(cmd,7)
        if not raw.strip(): return out
        try:
            obj=json.loads(raw)
            engines=obj.get('engine') or []
            mems=obj.get('memory') or []
            if isinstance(engines,dict): engines=[engines]
            if isinstance(mems,dict): mems=[mems]
            for x in engines:
                inst=str(x.get('InstanceName',''))
                m=re.search(r'pid_(\d+)',inst,re.I)
                if not m: continue
                pid=int(m.group(1)); val=max(0.0,float(x.get('CookedValue') or 0.0))
                d=out.setdefault(pid,{'gpu':0.0,'gpu_mem_bytes':0.0,'source':'Windows WDDM'})
                # Kullanıcı için 0-100 arası anlaşılır değer: en yoğun GPU engine.
                d['gpu']=max(d['gpu'],min(100.0,val))
            for x in mems:
                inst=str(x.get('InstanceName',''))
                m=re.search(r'pid_(\d+)',inst,re.I)
                if not m: continue
                pid=int(m.group(1)); val=max(0.0,float(x.get('CookedValue') or 0.0))
                d=out.setdefault(pid,{'gpu':None,'gpu_mem_bytes':0.0,'source':'Windows WDDM'})
                d['gpu_mem_bytes']=max(d.get('gpu_mem_bytes') or 0.0,val)
        except Exception: pass
        return out

    def _nvidia(self,out):
        if not self.nvidia: return out
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        try:
            p=subprocess.run([self.nvidia,'pmon','-c','1','-s','um'],capture_output=True,text=True,timeout=4,creationflags=flags)
            if p.returncode==0:
                for line in p.stdout.splitlines():
                    s=line.strip()
                    if not s or s.startswith('#'): continue
                    z=s.split()
                    if len(z)<5: continue
                    try: pid=int(z[1])
                    except: continue
                    try: gpu=None if z[3]=='-' else float(z[3])
                    except: gpu=None
                    d=out.setdefault(pid,{'gpu':gpu,'gpu_mem_bytes':None,'source':'NVIDIA nvidia-smi'})
                    if gpu is not None: d['gpu']=gpu
                    d['source']='NVIDIA nvidia-smi + WDDM'
            p=subprocess.run([self.nvidia,'--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4,creationflags=flags)
            if p.returncode==0:
                for line in p.stdout.splitlines():
                    z=[x.strip() for x in line.split(',')]
                    if len(z)>=2:
                        try:
                            pid=int(z[0]); mb=float(z[1]); d=out.setdefault(pid,{'gpu':None,'gpu_mem_bytes':None,'source':'NVIDIA nvidia-smi'})
                            d['gpu_mem_bytes']=mb*1024*1024; d['source']='NVIDIA nvidia-smi + WDDM'
                        except: pass
        except Exception: pass
        return out

    def _gpu_worker(self):
        try:
            data=self._nvidia(self._wddm())
            with self._lock:
                self.cache=data
        finally:
            self._gpu_busy=False

    def read(self):
        now=time.time()
        if now-self.last_read>=GPU_REFRESH_SEC and not self._gpu_busy:
            self.last_read=now; self._gpu_busy=True
            threading.Thread(target=self._gpu_worker,daemon=True).start()
        with self._lock:
            return dict(self.cache)

    def _temp_worker(self):
        temps=[]
        cmd=r'''$ErrorActionPreference='SilentlyContinue';
$all=@();
foreach($ns in 'root\LibreHardwareMonitor','root\OpenHardwareMonitor'){
 try{$all += Get-CimInstance -Namespace $ns -ClassName Sensor | Where-Object {$_.SensorType -eq 'Temperature'} | Select-Object Name,Value}catch{}
}; $all|ConvertTo-Json -Compress'''
        raw=self._ps(cmd,5)
        if raw.strip():
            try:
                obj=json.loads(raw); obj=[obj] if isinstance(obj,dict) else obj
                for x in obj or []:
                    try:
                        v=float(x.get('Value')); name=str(x.get('Name') or 'Sensör')
                        if -20<v<130: temps.append((name,v))
                    except: pass
            except: pass
        if self.nvidia:
            try:
                flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
                p=subprocess.run([self.nvidia,'--query-gpu=name,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4,creationflags=flags)
                if p.returncode==0:
                    for line in p.stdout.splitlines():
                        z=[x.strip() for x in line.split(',')]
                        if len(z)>=2:
                            try: temps.append((f'{z[0]} GPU',float(z[1])))
                            except: pass
            except: pass
        self.temp_cache=max((v for _,v in temps),default=None)
        self._temp_busy=False

    def temperatures(self):
        now=time.time()
        if now-self.temp_last>=TEMP_REFRESH_SEC and not self._temp_busy:
            self.temp_last=now; self._temp_busy=True
            threading.Thread(target=self._temp_worker,daemon=True).start()
        return self.temp_cache

class Chart(QWidget):
    def __init__(self,title,unit='%'):
        super().__init__(); self.title=title; self.unit=unit; self.series={}; self.setMinimumHeight(170); self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
    def set_series(self,s): self.series=s; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing,True); r=self.rect(); p.fillRect(r,QColor(SURFACE)); p.setPen(QColor(BORDER)); p.drawRoundedRect(r.adjusted(0,0,-1,-1),14,14)
        f=QFont('Segoe UI',10); f.setBold(True); p.setFont(f); p.setPen(QColor(TEXT)); p.drawText(15,24,self.title)
        plot=r.adjusted(44,40,-15,-26); p.setPen(QPen(QColor('#353A42'),1))
        for i in range(5):
            y=int(plot.top()+plot.height()*i/4); p.drawLine(plot.left(),y,plot.right(),y)
        vals=[v for arr in self.series.values() for _,v in arr if v is not None and math.isfinite(v)]
        ymax=max(100.0,max(vals) if vals else 100.0) if self.unit=='%' else max(1.0,(max(vals) if vals else 1.0)*1.15)
        colors=['#D4AF37','#7EC8E3','#8FD694','#E49AB0','#C6A0F6','#F5A65B']
        for idx,(name,arr) in enumerate(self.series.items()):
            arr=arr[-MAX_CHART_POINTS:]
            if len(arr)<2: continue
            p.setPen(QPen(QColor(colors[idx%len(colors)]),2)); prev=None; n=max(1,len(arr)-1)
            for i,(_,v) in enumerate(arr):
                if v is None: prev=None; continue
                x=int(plot.left()+plot.width()*i/n); y=int(plot.bottom()-plot.height()*max(0,min(v,ymax))/ymax)
                if prev: p.drawLine(prev[0],prev[1],x,y)
                prev=(x,y)


class PuzzleRadar(QWidget):
    """CPU/RAM/GPU/Disk/Internet kaynak profilini 0-100 skorla gösteren radar grafik."""
    def __init__(self, title='Puzzle Kaynak Profili'):
        super().__init__()
        self.title=title
        self.labels=['CPU','RAM','GPU','Disk','Download','Upload']
        self.values=[0,0,0,0,0,0]
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)

    def set_values(self, values):
        self.values=[max(0.0,min(100.0,float(v or 0))) for v in values[:6]]
        while len(self.values)<6: self.values.append(0.0)
        self.update()

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing,True)
        r=self.rect(); p.fillRect(r,QColor(SURFACE)); p.setPen(QColor(BORDER)); p.drawRoundedRect(r.adjusted(0,0,-1,-1),14,14)
        f=QFont('Segoe UI',10); f.setBold(True); p.setFont(f); p.setPen(QColor(TEXT)); p.drawText(15,24,self.title)
        cx=r.center().x(); cy=r.center().y()+12; radius=max(70,min(r.width(),r.height())*0.31); n=len(self.labels)
        # 20/40/60/80/100 halkaları
        for level in range(1,6):
            rr=radius*level/5
            pts=[]
            for i in range(n):
                a=-math.pi/2 + 2*math.pi*i/n
                pts.append(QPointF(cx+math.cos(a)*rr,cy+math.sin(a)*rr))
            p.setPen(QPen(QColor('#3A4049'),1)); p.setBrush(Qt.NoBrush); p.drawPolygon(QPolygonF(pts))
        # eksenler ve etiketler
        lf=QFont('Segoe UI',8); lf.setBold(True); p.setFont(lf)
        for i,label in enumerate(self.labels):
            a=-math.pi/2 + 2*math.pi*i/n
            x=cx+math.cos(a)*radius; y=cy+math.sin(a)*radius
            p.setPen(QPen(QColor('#4B515B'),1)); p.drawLine(QPointF(cx,cy),QPointF(x,y))
            tx=cx+math.cos(a)*(radius+25); ty=cy+math.sin(a)*(radius+22)
            p.setPen(QColor(MUTED)); p.drawText(int(tx-38),int(ty-9),76,18,Qt.AlignCenter,label)
        # veri alanı
        pts=[]
        for i,v in enumerate(self.values):
            a=-math.pi/2 + 2*math.pi*i/n; rr=radius*v/100.0
            pts.append(QPointF(cx+math.cos(a)*rr,cy+math.sin(a)*rr))
        if pts:
            fill=QColor(GOLD); fill.setAlpha(65)
            p.setBrush(QBrush(fill)); p.setPen(QPen(QColor(GOLD2),2)); p.drawPolygon(QPolygonF(pts))
            p.setBrush(QBrush(QColor(GOLD2)))
            for pt in pts: p.drawEllipse(pt,3.5,3.5)
        # değerler
        vf=QFont('Segoe UI',8); p.setFont(vf)
        y0=r.height()-24; p.setPen(QColor(MUTED))
        summary='   '.join(f'{a}: {b:.0f}' for a,b in zip(self.labels,self.values))
        p.drawText(12,y0,max(10,r.width()-24),18,Qt.AlignCenter,summary)


class PieAnalysis(QWidget):
    """CPU/RAM/GPU/Disk/Download/Upload yoğunluklarını pasta grafikte gösterir."""
    def __init__(self,title='Pasta Analiz — Kaynak Dağılımı'):
        super().__init__(); self.title=title; self.values=[0]*6; self.labels=['CPU','RAM','GPU','Disk','Download','Upload']; self.setMinimumHeight(310)
    def set_values(self,values): self.values=[max(0.0,min(100.0,float(v or 0))) for v in values]; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing,True); r=self.rect(); p.fillRect(r,QColor(SURFACE)); p.setPen(QColor(BORDER)); p.drawRoundedRect(r.adjusted(0,0,-1,-1),14,14)
        f=QFont('Segoe UI',10); f.setBold(True); p.setFont(f); p.setPen(QColor(TEXT)); p.drawText(14,24,self.title)
        total=sum(self.values)
        if total<=0:
            p.setPen(QColor(MUTED)); p.drawText(r.adjusted(0,40,0,0),Qt.AlignCenter,'Analiz için veri toplanıyor…'); return
        colors=[QColor('#D4AF37'),QColor('#7EC8E3'),QColor('#8FD694'),QColor('#E49AB0'),QColor('#C6A0F6'),QColor('#F5A65B')]
        size=min(r.width()*0.46,r.height()-70); x=22; y=48; rect=(int(x),int(y),int(size),int(size)); start=90*16
        for i,v in enumerate(self.values):
            span=-int((v/total)*360*16); p.setBrush(QBrush(colors[i])); p.setPen(QPen(QColor(BG),2)); p.drawPie(*rect,start,span); start+=span
        lx=int(x+size+28); ly=62; p.setPen(QColor(TEXT)); lf=QFont('Segoe UI',9); p.setFont(lf)
        for i,(lab,v) in enumerate(zip(self.labels,self.values)):
            p.setBrush(QBrush(colors[i])); p.setPen(Qt.NoPen); p.drawRoundedRect(lx,ly-10,12,12,3,3); p.setPen(QColor(MUTED)); share=(v/total*100) if total else 0; p.drawText(lx+20,ly,f'{lab}: skor {v:.0f} · dağılım %{share:.1f}'); ly+=31


class Card(QFrame):
    def __init__(self,title,value='—'):
        super().__init__(); self.setObjectName('card'); l=QVBoxLayout(self); l.setContentsMargins(14,11,14,11)
        a=QLabel(title); a.setObjectName('cardTitle'); self.v=QLabel(value); self.v.setObjectName('cardValue'); self.v.setWordWrap(True); l.addWidget(a); l.addWidget(self.v)
    def set(self,v): self.v.setText(v)


class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.db=DB(DB_PATH); self.gpu=UniversalGpuReader(); self.netmon=ProcessNetworkETW(); self.tracked={}; self.logical=max(1,psutil.cpu_count(logical=True) or 1)
        self.prev_net=psutil.net_io_counters(); self.prev_net_ts=time.time(); self.net_up=0.0; self.net_down=0.0
        self.net_sent_total=self.prev_net.bytes_sent; self.net_recv_total=self.prev_net.bytes_recv
        self.setWindowTitle(APP_NAME); self.resize(1550,930); self.setMinimumSize(1100,720)
        root=QWidget(); self.setCentralWidget(root); main=QVBoxLayout(root); main.setContentsMargins(18,16,18,18); main.setSpacing(12)

        h=QHBoxLayout(); tb=QVBoxLayout(); t=QLabel('ELITE PROCESS MONITOR PRO'); t.setObjectName('title'); s=QLabel('NVIDIA • AMD • Intel GPU | CPU • RAM • Disk • Süreç İnterneti (ETW) • Saatlik Trafik • Puzzle Grafik • Pasta Analiz'); s.setObjectName('muted'); tb.addWidget(t); tb.addWidget(s); h.addLayout(tb); h.addStretch()
        self.search=QLineEdit(); self.search.setPlaceholderText('Program ara: chrome, python, obs, vlc veya PID...'); self.search.setMinimumWidth(370); self.search.textChanged.connect(self.refresh_processes); h.addWidget(self.search)
        b=QPushButton('Yenile'); b.clicked.connect(self.refresh_processes); h.addWidget(b); e=QPushButton('HTML Dışa Aktar'); e.setObjectName('gold'); e.clicked.connect(self.export_html); h.addWidget(e); main.addLayout(h)

        cards=QGridLayout(); self.c1=Card('İzlenen Program','0'); self.c2=Card('Toplam CPU','0.0%'); self.c3=Card('Toplam RAM','0 MB'); self.c4=Card('Toplam GPU','N/A'); self.c5=Card('Seçili Program İnterneti','↓ 0 KB/sn\n↑ 0 KB/sn'); self.c6=Card('Sıcaklık','Sensör bekleniyor'); self.c7=Card('Son 1 Saat Program Trafiği','↓ 0 MB\n↑ 0 MB'); self.c8=Card('Son 1 Saat Ort. Hız','↓ 0 KB/sn\n↑ 0 KB/sn')
        for i,c in enumerate([self.c1,self.c2,self.c3,self.c4,self.c5,self.c6,self.c7,self.c8]): cards.addWidget(c,i//4,i%4)
        main.addLayout(cards)

        sp=QSplitter(Qt.Vertical); sp.setChildrenCollapsible(False)
        p1=QFrame(); p1.setObjectName('panel'); l1=QVBoxLayout(p1); top=QHBoxLayout(); x=QLabel('ÇALIŞAN PROGRAMLAR'); x.setObjectName('section'); top.addWidget(x); top.addStretch(); z=QLabel('Ctrl/Shift ile birden fazla program seçebilirsiniz'); z.setObjectName('muted'); top.addWidget(z); l1.addLayout(top)
        self.pt=QTableWidget(0,6); self.pt.setHorizontalHeaderLabels(['PID','Program','Kullanıcı','CPU','RAM','Program Açık']); self.pt.setSelectionBehavior(QAbstractItemView.SelectRows); self.pt.setSelectionMode(QAbstractItemView.ExtendedSelection); self.pt.setEditTriggers(QAbstractItemView.NoEditTriggers); self.pt.verticalHeader().setVisible(False); self.pt.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for c in [0,2,3,4,5]: self.pt.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeToContents)
        l1.addWidget(self.pt); ab=QPushButton('＋ Takibe Ekle'); ab.setObjectName('gold'); ab.clicked.connect(self.add_selected); l1.addWidget(ab,0,Qt.AlignLeft); sp.addWidget(p1)

        p2=QFrame(); p2.setObjectName('panel'); l2=QVBoxLayout(p2); top=QHBoxLayout(); x=QLabel('CANLI TAKİP VE ÖLÇÜM'); x.setObjectName('section'); top.addWidget(x); top.addStretch(); self.range=QComboBox(); self.range.addItems(['Son 10 dakika','Son 1 saat','Son 5 saat','Son 12 saat','Son 24 saat','Tüm kayıt']); self.range.currentIndexChanged.connect(self.update_charts); top.addWidget(self.range); rb=QPushButton('Seçileni Çıkar'); rb.clicked.connect(self.remove_selected); top.addWidget(rb); l2.addLayout(top)
        self.info=QLabel('CPU açıklaması: “Toplam CPU” tüm işlemci kapasitesine göre 0–100%; “Çekirdek eşdeğeri” programın yaklaşık kaç mantıksal çekirdeği kullandığını gösterir.'); self.info.setObjectName('muted'); self.info.setWordWrap(True); l2.addWidget(self.info)
        self.tt=QTableWidget(0,15); self.tt.setHorizontalHeaderLabels(['PID','Program','Toplam CPU','Çekirdek','RAM','RAM %','GPU','GPU Bellek','Disk Oku','Disk Yaz','Program ↓','Program ↑','Program Açık','Ölçüm Süresi','GPU Kaynağı']); self.tt.setSelectionBehavior(QAbstractItemView.SelectRows); self.tt.setSelectionMode(QAbstractItemView.ExtendedSelection); self.tt.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tt.verticalHeader().setVisible(False); self.tt.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for c in [0,2,3,4,5,6,7,8,9,10,11,12,13,14]: self.tt.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeToContents)
        l2.addWidget(self.tt)
        cg=QGridLayout(); self.cpu_chart=Chart('Toplam CPU Kullanımı','%'); self.ram_chart=Chart('RAM Kullanımı',' MB'); self.gpu_chart=Chart('GPU Kullanımı','%'); self.net_chart=Chart('Seçili Program İnternet Hızı (MB/sn)',' MB/sn'); self.puzzle_chart=PuzzleRadar('Puzzle Grafik — Kaynak Kullanım Profili (0–100 yoğunluk skoru)'); self.pie_chart=PieAnalysis('Pasta Analiz — Kaynak Yoğunluğu Dağılımı'); cg.addWidget(self.cpu_chart,0,0); cg.addWidget(self.ram_chart,0,1); cg.addWidget(self.gpu_chart,1,0); cg.addWidget(self.net_chart,1,1); cg.addWidget(self.puzzle_chart,2,0); cg.addWidget(self.pie_chart,2,1); l2.addLayout(cg); sp.addWidget(p2); sp.setStretchFactor(0,4); sp.setStretchFactor(1,6); main.addWidget(sp)

        self.setStyleSheet(self.app_stylesheet()); self.statusBar().showMessage(f'Kayıt veritabanı: {DB_PATH}')
        self.setup_tray()
        if self.netmon.available:
            self.statusBar().showMessage(f'Süreç internet ölçümü AKTİF ({self.netmon.backend}) · Yönetici: EVET · Kayıt: {DB_PATH}')
        else:
            self.statusBar().showMessage('ETW KAPALI · '+self.netmon.error+' · Tanılama: '+str(data_dir()/'etw_diagnostic.txt'))
        self.t1=QTimer(self); self.t1.timeout.connect(self.refresh_processes); self.t1.start(15000)
        self.t2=QTimer(self); self.t2.timeout.connect(self.collect); self.t2.start(SAMPLE_INTERVAL_MS)
        self.t3=QTimer(self); self.t3.timeout.connect(self.update_charts); self.t3.start(15000)
        self.refresh_processes()

    def setup_tray(self):
        self.tray=QSystemTrayIcon(self)
        icon=QApplication.style().standardIcon(QStyle.SP_ComputerIcon); self.setWindowIcon(icon); self.tray.setIcon(icon); self.tray.setToolTip(APP_NAME)
        menu=QMenu(); show=QAction('Programı Aç',self); show.triggered.connect(self.show_normal); menu.addAction(show); export=QAction('HTML Raporu',self); export.triggered.connect(self.export_html); menu.addAction(export); menu.addSeparator(); quit_a=QAction('Tamamen Kapat',self); quit_a.triggered.connect(self.quit_app); menu.addAction(quit_a); self.tray.setContextMenu(menu); self.tray.activated.connect(lambda reason:self.show_normal() if reason==QSystemTrayIcon.DoubleClick else None); self.tray.show(); self._really_quit=False
    def show_normal(self): self.show(); self.raise_(); self.activateWindow()
    def quit_app(self): self._really_quit=True; self.netmon.stop(); self.db.close(); QApplication.quit()

    def app_stylesheet(self):
        return f'''QWidget{{background:{BG};color:{TEXT};font-family:"Segoe UI";font-size:10pt}} QLabel#title{{color:{GOLD2};font-size:22pt;font-weight:800}} QLabel#muted{{color:{MUTED}}} QLabel#section{{color:{GOLD2};font-weight:700;font-size:11pt}} QFrame#panel,QFrame#card{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px}} QLabel#cardTitle{{color:{MUTED};font-size:9pt}} QLabel#cardValue{{color:{GOLD2};font-size:15pt;font-weight:700}} QLineEdit,QComboBox{{background:{SURFACE2};border:1px solid {BORDER};border-radius:10px;padding:9px 12px}} QPushButton{{background:{SURFACE2};border:1px solid {BORDER};border-radius:10px;padding:9px 14px;font-weight:600}} QPushButton:hover{{border-color:{GOLD}}} QPushButton#gold{{background:{GOLD};color:#111;border-color:{GOLD2};font-weight:800}} QPushButton#gold:hover{{background:{GOLD2}}} QTableWidget{{background:{SURFACE};alternate-background-color:{SURFACE2};border:1px solid {BORDER};border-radius:10px;gridline-color:#30343B;selection-background-color:#5c5125}} QHeaderView::section{{background:{SURFACE2};color:{GOLD2};border:none;border-bottom:1px solid {BORDER};padding:8px;font-weight:700}} QTableWidget::item{{padding:5px}} QSplitter::handle{{background:transparent;height:8px}} QStatusBar{{color:{MUTED}}}'''

    def refresh_processes(self):
        q=self.search.text().strip().lower(); rows=[]
        for p in psutil.process_iter(['pid','name','username','memory_info','create_time']):
            try:
                name=p.info['name'] or ''
                if q and q not in name.lower() and q not in str(p.info['pid']): continue
                rows.append((p.info['pid'],name,p.info.get('username') or '',p.info['memory_info'].rss,time.time()-p.info['create_time']))
            except: pass
        rows.sort(key=lambda x:x[1].lower()); self.pt.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[str(row[0]),row[1],row[2].split('\\')[-1], '—', fmt_size(row[3]),fmt_duration(row[4])]
            for c,v in enumerate(vals): self.pt.setItem(r,c,QTableWidgetItem(v))

    def add_selected(self):
        rows=sorted({i.row() for i in self.pt.selectedItems()})
        if not rows: QMessageBox.information(self,'Seçim','Takip etmek için en az bir program seçin.'); return
        for r in rows:
            try:
                pid=int(self.pt.item(r,0).text()); p=psutil.Process(pid); ct=p.create_time(); key=(pid,ct)
                if key in self.tracked: continue
                try: exe=p.exe()
                except: exe=''
                try: p.cpu_percent(None)
                except: pass
                try: io=p.io_counters(); prev_r=io.read_bytes; prev_w=io.write_bytes
                except: prev_r=prev_w=0
                self.tracked[key]={'p':p,'pid':pid,'ct':ct,'name':p.name(),'exe':exe,'added':time.time(),'measured_start':time.time(),'samples':0,'prev_io_ts':time.time(),'prev_r':prev_r,'prev_w':prev_w,'dr':0.0,'dw':0.0}
                self.netmon.ensure_pid(pid)
            except: pass
        self.rebuild()

    def rebuild(self):
        self.tt.setRowCount(len(self.tracked))
        for r,(_,d) in enumerate(self.tracked.items()):
            vals=[str(d['pid']),d['name'],'0.0%','0.00','0 MB','0.0%','N/A','N/A','0 B/sn','0 B/sn','0 B/sn','0 B/sn','—','—','Bekleniyor']
            for c,v in enumerate(vals): self.tt.setItem(r,c,QTableWidgetItem(v))

    def remove_selected(self):
        rows=sorted({i.row() for i in self.tt.selectedItems()},reverse=True); keys=list(self.tracked.keys())
        for r in rows:
            if 0<=r<len(keys):
                d=self.tracked.pop(keys[r],None)
                if d: self.netmon.remove_pid(d['pid'])
        self.rebuild(); self.update_charts()

    def update_network(self,now):
        cur=psutil.net_io_counters(); dt=max(.1,now-self.prev_net_ts)
        self.net_down=max(0,(cur.bytes_recv-self.prev_net.bytes_recv)/dt); self.net_up=max(0,(cur.bytes_sent-self.prev_net.bytes_sent)/dt)
        self.net_sent_total=cur.bytes_sent; self.net_recv_total=cur.bytes_recv
        self.prev_net=cur; self.prev_net_ts=now

    def collect(self):
        now=time.time(); gd=self.gpu.read(); temp=self.gpu.temperatures(); dead=[]; total_norm=tr=0.0; gvals=[]; keys=list(self.tracked.keys())
        for r,key in enumerate(keys):
            d=self.tracked[key]; p=d['p']
            try:
                if not p.is_running() or abs(p.create_time()-d['ct'])>0.01: dead.append(key); continue
                raw_cpu=p.cpu_percent(None); total_cpu=min(100.0,raw_cpu/self.logical); cores=raw_cpu/100.0; ram_b=p.memory_info().rss; ram_mb=ram_b/1048576; rp=p.memory_percent()
                g=gd.get(d['pid'],{}); gpu=g.get('gpu'); gm_b=g.get('gpu_mem_bytes'); gm_mb=None if gm_b is None else gm_b/1048576; gsrc=g.get('source','Windows WDDM' if os.name=='nt' else 'N/A')
                try:
                    io=p.io_counters(); dt=max(.1,now-d['prev_io_ts']); dr=max(0,(io.read_bytes-d['prev_r'])/dt); dw=max(0,(io.write_bytes-d['prev_w'])/dt); d.update(prev_io_ts=now,prev_r=io.read_bytes,prev_w=io.write_bytes,dr=dr,dw=dw)
                except: dr=dw=0.0
                net=self.netmon.sample(d['pid'],now); proc_up=net['up_bps']; proc_down=net['down_bps']
                self.db.add((d['pid'],d['ct'],d['name'],d['exe'],now,raw_cpu,ram_mb,rp,gpu,gm_mb,dr,dw,proc_up,proc_down,temp,gsrc,net['sent_total'],net['recv_total'],net['scope'])); d['samples']+=1
                d['net_up']=proc_up; d['net_down']=proc_down; d['net_sent_total']=net['sent_total']; d['net_recv_total']=net['recv_total']
                total_norm+=total_cpu; tr+=ram_b
                if gpu is not None: gvals.append(gpu)
                measured=max(0,now-d['measured_start']) if d.get('samples',0)>1 else 0
                vals=[fmt_pct(total_cpu),f'{cores:.2f}',fmt_size(ram_b),fmt_pct(rp),fmt_pct(gpu),fmt_size(gm_b),fmt_rate(dr),fmt_rate(dw),fmt_rate(proc_down),fmt_rate(proc_up),fmt_duration(now-d['ct']),fmt_duration(measured),gsrc]
                for c,v in enumerate(vals,2):
                    it=self.tt.item(r,c)
                    if it: it.setText(v)
            except (psutil.NoSuchProcess,psutil.AccessDenied): dead.append(key)
            except Exception: pass
        self.db.flush()
        for k in dead: self.tracked.pop(k,None)
        if dead: self.rebuild()
        self.c1.set(str(len(self.tracked))); self.c2.set(f'{min(100.0,total_norm):.1f}%'); self.c3.set(fmt_size(tr)); self.c4.set('N/A' if not gvals else f'{min(100.0,sum(gvals)):.1f}%'); self.c6.set('Sensör bulunamadı' if temp is None else fmt_temp(temp))
        pups=[d.get('net_up') for d in self.tracked.values() if d.get('net_up') is not None]; pdowns=[d.get('net_down') for d in self.tracked.values() if d.get('net_down') is not None]
        if self.netmon.available:
            self.c5.set(f'↓ {fmt_rate(sum(pdowns))}\n↑ {fmt_rate(sum(pups))}')
            summaries=[self.process_network_summary(d,3600,'Son 1 saat') for d in self.tracked.values()]
            valid=[n for n in summaries if n.get('samples',0)>1]
            if valid:
                self.c7.set(f"↓ {fmt_size(sum(n['down_total'] for n in valid))}\n↑ {fmt_size(sum(n['up_total'] for n in valid))}")
                self.c8.set(f"↓ {fmt_rate(sum((n['down_avg'] or 0) for n in valid))}\n↑ {fmt_rate(sum((n['up_avg'] or 0) for n in valid))}")
            else: self.c7.set('Veri toplanıyor'); self.c8.set('Veri toplanıyor')
        else:
            err=(self.netmon.error or 'ETW kullanılamıyor'); self.c5.set('ETW KAPALI\n'+err[:72]); self.c7.set('Süreç verisi yok'); self.c8.set('Tanılama dosyası\netw_diagnostic.txt')

    def range_sec(self): return [600,3600,18000,43200,86400,None][self.range.currentIndex()]
    def update_charts(self):
        cpu={}; ram={}; gpu={}; sec=self.range_sec(); since=None if sec is None else time.time()-sec
        for _,d in self.tracked.items():
            rows=self.db.history(d['pid'],d['ct'],since)
            if len(rows)>MAX_CHART_POINTS:
                step=max(1,len(rows)//MAX_CHART_POINTS); rows=rows[::step][-MAX_CHART_POINTS:]
            n=f"{d['name']} [{d['pid']}]"; cpu[n]=[(x[0],min(100.0,(x[1] or 0)/self.logical)) for x in rows]; ram[n]=[(x[0],x[2]) for x in rows]; gpu[n]=[(x[0],x[4]) for x in rows]
        self.cpu_chart.set_series(cpu); self.ram_chart.set_series(ram); self.gpu_chart.set_series(gpu)
        net_series={}
        for _,d in self.tracked.items():
            rr=self.db.history(d['pid'],d['ct'],since)
            if len(rr)>MAX_CHART_POINTS:
                step=max(1,len(rr)//MAX_CHART_POINTS); rr=rr[::step][-MAX_CHART_POINTS:]
            name=f"{d['name']} [{d['pid']}]"
            net_series[name+' ↓']=[(x[0],(x[9] or 0)/1048576) for x in rr if len(x)>14 and x[14]=='process_etw']
            net_series[name+' ↑']=[(x[0],(x[8] or 0)/1048576) for x in rr if len(x)>14 and x[14]=='process_etw']
        self.net_chart.set_series(net_series)
        # Puzzle radar: seçili zaman aralığındaki ortalama yoğunlukları 0-100 skorlar.
        all_cpu=[]; all_ram=[]; all_gpu=[]; all_disk=[]
        for _,d in self.tracked.items():
            rr=self.db.history(d['pid'],d['ct'],since)
            all_cpu += [min(100.0,(x[1] or 0)/self.logical) for x in rr if x[1] is not None]
            all_ram += [x[2]*1048576 for x in rr if x[2] is not None]
            all_gpu += [x[4] for x in rr if x[4] is not None]
            all_disk += [max(0,(x[6] or 0)+(x[7] or 0)) for x in rr]
        cpu_score=safe_mean(all_cpu) or 0
        # RAM skoru: izlenen süreçlerin ortalama 4 GB kullanımı 100 puan kabul edilir.
        ram_score=min(100.0,((safe_mean(all_ram) or 0)/(4*1024**3))*100)
        gpu_score=safe_mean(all_gpu) or 0
        # Disk skoru: 50 MB/sn birleşik okuma+yazma = 100 yoğunluk puanı.
        disk_score=min(100.0,((safe_mean(all_disk) or 0)/(50*1024**2))*100)
        nd=[]; nu=[]
        for _,d in self.tracked.items():
            rr=self.db.history(d['pid'],d['ct'],since)
            nd += [x[9] for x in rr if x[9] is not None and len(x)>14 and x[14]=='process_etw']
            nu += [x[8] for x in rr if x[8] is not None and len(x)>14 and x[14]=='process_etw']
        # Ağ skoru yalnız seçili süreçlerin ETW trafiğinden hesaplanır.
        down_score=min(100.0,((safe_mean(nd) or 0)/(12.5*1024**2))*100)
        up_score=min(100.0,((safe_mean(nu) or 0)/(6.25*1024**2))*100)
        scores=[cpu_score,ram_score,gpu_score,disk_score,down_score,up_score]
        self.puzzle_chart.set_values(scores); self.pie_chart.set_values(scores)

    def process_network_summary(self,d,seconds,label):
        since=time.time()-seconds; rows=self.db.history(d['pid'],d['ct'],since)
        # Yalnız v6 ETW süreç kayıtları; eski sistem-geneli kayıtları dışarıda bırak.
        rows=[x for x in rows if len(x)>14 and x[14]=='process_etw' and x[12] is not None and x[13] is not None]
        if len(rows)<2: return {'label':label,'coverage':'Kayıt yok','samples':len(rows)}
        measured=max(0,rows[-1][0]-rows[0][0]); coverage=min(100.0,measured/seconds*100) if seconds else 100.0
        up=[x[8] for x in rows if x[8] is not None]; down=[x[9] for x in rows if x[9] is not None]
        # totals: cumulative ETW counters may reset on app restart, so sum per-sample rate*dt is robust across sessions.
        up_total=down_total=0.0
        for a,b in zip(rows,rows[1:]):
            dt=max(0,b[0]-a[0]); up_total+=(b[8] or 0)*dt; down_total+=(b[9] or 0)*dt
        return {'label':label,'coverage':f'{fmt_duration(measured)} veri (%{coverage:.0f} kapsam)','measured':measured,'samples':len(rows),
                'up_avg':safe_mean(up),'down_avg':safe_mean(down),'up_max':max(up) if up else None,'down_max':max(down) if down else None,
                'up_total':up_total,'down_total':down_total,'up_hourly':(up_total/measured*3600) if measured>0 else 0,'down_hourly':(down_total/measured*3600) if measured>0 else 0}

    def process_hourly_network_rows(self,d,hours=24):
        rows=self.db.history(d['pid'],d['ct'],time.time()-hours*3600)
        rows=[x for x in rows if len(x)>14 and x[14]=='process_etw']
        if len(rows)<2: return []
        buckets={}
        for a,b in zip(rows,rows[1:]):
            dt=max(0,b[0]-a[0]);
            if dt<=0: continue
            key=datetime.fromtimestamp(b[0]).strftime('%d.%m %H:00')
            z=buckets.setdefault(key,{'seconds':0.0,'up':0.0,'down':0.0,'ups':[],'downs':[]})
            z['seconds']+=dt; z['up']+=(b[8] or 0)*dt; z['down']+=(b[9] or 0)*dt
            if b[8] is not None: z['ups'].append(b[8])
            if b[9] is not None: z['downs'].append(b[9])
        return [(k,v['seconds'],v['down'],v['up'],safe_mean(v['downs']),safe_mean(v['ups'])) for k,v in buckets.items()][-24:]

    def network_summary(self,seconds,label):
        since=time.time()-seconds; rows=self.db.system_history(since)
        if len(rows)<2: return {'label':label,'coverage':'Kayıt yok','samples':len(rows)}
        measured=max(0,rows[-1][0]-rows[0][0]); coverage=min(100.0,measured/seconds*100) if seconds else 100.0
        up=[x[1] for x in rows if x[1] is not None]; down=[x[2] for x in rows if x[2] is not None]
        up_total=max(0,(rows[-1][3] or 0)-(rows[0][3] or 0)); down_total=max(0,(rows[-1][4] or 0)-(rows[0][4] or 0))
        return {'label':label,'coverage':f'{fmt_duration(measured)} veri (%{coverage:.0f} kapsam)','measured':measured,'samples':len(rows),
                'up_avg':safe_mean(up),'down_avg':safe_mean(down),'up_max':max(up) if up else None,'down_max':max(down) if down else None,
                'up_total':up_total,'down_total':down_total,'up_hourly':(up_total/measured*3600) if measured>0 else 0,'down_hourly':(down_total/measured*3600) if measured>0 else 0}

    def hourly_network_rows(self,hours=24):
        rows=self.db.system_history(time.time()-hours*3600)
        if len(rows)<2: return []
        buckets={}
        for a,b in zip(rows,rows[1:]):
            if b[0]<=a[0]: continue
            key=datetime.fromtimestamp(b[0]).strftime('%d.%m %H:00')
            d=buckets.setdefault(key,{'start':a[0],'end':b[0],'up':0,'down':0,'ups':[],'downs':[]})
            d['start']=min(d['start'],a[0]); d['end']=max(d['end'],b[0])
            d['up']+=max(0,(b[3] or 0)-(a[3] or 0)); d['down']+=max(0,(b[4] or 0)-(a[4] or 0))
            if b[1] is not None: d['ups'].append(b[1])
            if b[2] is not None: d['downs'].append(b[2])
        out=[]
        for key,d in buckets.items(): out.append((key,max(0,d['end']-d['start']),d['down'],d['up'],safe_mean(d['downs']),safe_mean(d['ups'])))
        return out[-24:]

    def puzzle_analysis(self,d,rows,net):
        cp=[min(100.0,(x[1] or 0)/self.logical) for x in rows if x[1] is not None]; rm=[x[2]*1048576 for x in rows if x[2] is not None]; gp=[x[4] for x in rows if x[4] is not None]; dr=[x[6] for x in rows if x[6] is not None]; dw=[x[7] for x in rows if x[7] is not None]
        ac=safe_mean(cp) or 0; ag=safe_mean(gp) if gp else None; ar=safe_mean(rm) or 0; md=(safe_mean(dr) or 0)+(safe_mean(dw) or 0); pieces=[]
        pieces.append(('CPU','Yüksek' if ac>=70 else 'Orta' if ac>=35 else 'Düşük',f'Ortalama CPU %{ac:.1f}. '+('Program işlemci ağırlıklı çalışıyor.' if ac>=70 else 'İşlemci yükü belirgin.' if ac>=35 else 'İşlemci tarafında hafif yük görülüyor.')))
        pieces.append(('RAM','Yüksek' if ar>=4*1024**3 else 'Orta' if ar>=1024**3 else 'Düşük',f'Ortalama bellek {fmt_size(ar)}. '+('Bellek baskısı oluşturabilir.' if ar>=4*1024**3 else 'Bellek tüketimi dikkat çekici.' if ar>=1024**3 else 'Bellek tüketimi makul.')))
        if ag is None: pieces.append(('GPU','Veri yok','GPU kullanım yüzdesi için yeterli veri oluşmamış.'))
        else: pieces.append(('GPU','Yüksek' if ag>=80 else 'Orta' if ag>=30 else 'Düşük',f'Ortalama GPU %{ag:.1f}. '+('Program GPU ağırlıklı çalışıyor.' if ag>=80 else 'Ekran kartı belirgin kullanılıyor.' if ag>=30 else 'GPU yükü düşük.')))
        pieces.append(('Disk','Yüksek' if md>=50*1024**2 else 'Orta' if md>=5*1024**2 else 'Düşük',f'Ortalama disk trafiği yaklaşık {fmt_rate(md)}.'))
        if net.get('samples',0)>1: pieces.append(('İnternet (program)','Bilgi',f"Bu PID için ETW ölçümü: ortalama ↓ {fmt_rate(net['down_avg'])}, ↑ {fmt_rate(net['up_avg'])}; toplam ↓ {fmt_size(net['down_total'])}, ↑ {fmt_size(net['up_total'])}."))
        heavy=max([('CPU',ac),('GPU',ag or 0),('Disk',min(100,md/(1024**2)))],key=lambda x:x[1])[0]
        return pieces,f'Genel profil: {heavy} tarafı diğer metriklere göre daha baskın görünüyor. Değerleri ölçüm süresi ve kapsam yüzdesiyle birlikte değerlendirin.'

    def period_summary(self,d,seconds,label):
        since=time.time()-seconds; rows=self.db.history(d['pid'],d['ct'],since)
        if not rows: return {'label':label,'coverage':'Kayıt yok'}
        measured=max(0,rows[-1][0]-rows[0][0]); cp=[min(100.0,(x[1] or 0)/self.logical) for x in rows if x[1] is not None]; cores=[(x[1] or 0)/100 for x in rows if x[1] is not None]; rm=[x[2]*1048576 for x in rows if x[2] is not None]; gp=[x[4] for x in rows if x[4] is not None]; dr=[x[6] for x in rows if x[6] is not None]; dw=[x[7] for x in rows if x[7] is not None]
        coverage=min(100.0,measured/seconds*100) if seconds else 100
        return {'label':label,'coverage':f'{fmt_duration(measured)} veri (%{coverage:.0f} kapsam)','cpu':safe_mean(cp),'cores':safe_mean(cores),'ram':safe_mean(rm),'rammax':max(rm) if rm else None,'gpu':safe_mean(gp),'diskr':safe_mean(dr),'diskw':safe_mean(dw),'samples':len(rows)}

    def export_html(self):
        if not self.tracked: QMessageBox.information(self,'HTML Rapor','Önce en az bir programı takibe ekleyin.'); return
        f,_=QFileDialog.getSaveFileName(self,'HTML Raporunu Kaydet',f"elite_process_report_{datetime.now():%Y%m%d_%H%M%S}.html",'HTML Dosyası (*.html)')
        if not f: return
        Path(f).write_text(self.report(),encoding='utf-8'); QMessageBox.information(self,'Tamamlandı',f'Profesyonel HTML raporu oluşturuldu:\n{f}')

    def report(self):
        sections=[]; now=time.time()
        for _,d in self.tracked.items():
            rows=self.db.history(d['pid'],d['ct'],None)
            if not rows: continue
            measured=max(0,rows[-1][0]-rows[0][0]); open_for=now-d['ct']; cp=[min(100.0,(x[1] or 0)/self.logical) for x in rows if x[1] is not None]; cores=[(x[1] or 0)/100 for x in rows if x[1] is not None]; rm=[x[2]*1048576 for x in rows if x[2] is not None]; gp=[x[4] for x in rows if x[4] is not None]; gm=[x[5]*1048576 for x in rows if x[5] is not None]
            periods=[self.period_summary(d,3600,'Son 1 saat'),self.period_summary(d,18000,'Son 5 saat'),self.period_summary(d,43200,'Son 12 saat'),self.period_summary(d,86400,'Son 24 saat')]
            net_periods=[self.process_network_summary(d,3600,'Son 1 saat'),self.process_network_summary(d,18000,'Son 5 saat'),self.process_network_summary(d,43200,'Son 12 saat'),self.process_network_summary(d,86400,'Son 24 saat')]
            net24=net_periods[-1]
            cards=[('Program açık',fmt_duration(open_for)),('Gerçek ölçüm',fmt_duration(measured)),('Ort. toplam CPU',fmt_pct(safe_mean(cp),2)),('Ort. çekirdek', 'N/A' if not cores else f'{mean(cores):.2f} çekirdek'),('Ort. RAM',fmt_size(safe_mean(rm))),('Maks. RAM',fmt_size(max(rm) if rm else None)),('Ort. GPU',fmt_pct(safe_mean(gp),2)),('Maks. GPU belleği',fmt_size(max(gm) if gm else None))]
            if net24.get('samples',0)>1:
                cards += [('24s Program İndirme',fmt_size(net24['down_total'])),('24s Program Yükleme',fmt_size(net24['up_total'])),('Ort. Program ↓',fmt_rate(net24['down_avg'])),('Ort. Program ↑',fmt_rate(net24['up_avg']))]
            cardhtml=''.join(f'<div class="stat"><span>{html.escape(k)}</span><strong>{html.escape(v)}</strong></div>' for k,v in cards)
            trs=''
            for p in periods:
                if 'cpu' not in p:
                    trs+=f'<tr><td>{p["label"]}</td><td colspan="7">{p["coverage"]}</td></tr>'; continue
                trs+=f'''<tr><td>{p['label']}</td><td>{p['coverage']}</td><td>{fmt_pct(p['cpu'],2)}</td><td>{p['cores']:.2f}</td><td>{fmt_size(p['ram'])}</td><td>{fmt_size(p['rammax'])}</td><td>{fmt_pct(p['gpu'],2)}</td><td>↓ {fmt_rate(p['diskr'])} / ↑ {fmt_rate(p['diskw'])}</td></tr>'''
            net_trs=''
            for n in net_periods:
                if n.get('samples',0)<2:
                    net_trs+=f'<tr><td>{n["label"]}</td><td colspan="8">Kayıt yok</td></tr>'; continue
                net_trs += '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>↓ {} / ↑ {}</td></tr>'.format(n['label'],n['coverage'],fmt_rate(n['down_avg']),fmt_rate(n['up_avg']),fmt_rate(n['down_max']),fmt_rate(n['up_max']),fmt_size(n['down_total']),fmt_size(n['up_total']),fmt_size(n['down_hourly']),fmt_size(n['up_hourly']))
            hourly=self.process_hourly_network_rows(d,24)
            hour_trs=''.join('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(h[0],fmt_duration(h[1]),fmt_size(h[2]),fmt_size(h[3]),fmt_rate(h[4]),fmt_rate(h[5])) for h in hourly) or '<tr><td colspan="6">Saatlik ağ verisi henüz oluşmadı.</td></tr>'
            puzzle,puzzle_summary=self.puzzle_analysis(d,rows,net24)
            puzzle_html=''.join(f'<div class="puzzle"><span>{html.escape(a)}</span><b>{html.escape(b)}</b><p>{html.escape(c)}</p></div>' for a,b,c in puzzle)
            warning=''
            if not self.netmon.available:
                warning += '<div class="notice"><b>İnternet ölçümü kapalı:</b> ETW etkin değil. Programı Yönetici olarak çalıştırın. Ağ değerleri bu durumda süreç için raporlanmaz.</div>'
            if measured < open_for*0.8:
                warning=f'<div class="notice"><b>Önemli:</b> Program {fmt_duration(open_for)} süredir açık; ancak bu raporda yalnızca {fmt_duration(measured)} ölçülmüş veri vardır. Bu nedenle 5/12/24 saat satırları yalnızca gerçekten kaydedilmiş süreyi temsil eder.</div>'
            # Grafik için örnek seyrekleştirme
            ds=rows
            if len(ds)>1200:
                step=max(1,len(ds)//1200); ds=ds[::step]
            def svg(vals, normalize_cpu=False):
                vv=[]
                for v in vals:
                    if v is None: vv.append(None)
                    elif normalize_cpu: vv.append(min(100.0,v/self.logical))
                    else: vv.append(v)
                real=[v for v in vv if v is not None]
                if len(real)<2: return '<div class="nodata">Bu metrik için yeterli veri yok.</div>'
                vmax=max(real) or 1; pts=[]
                for i,v in enumerate(vv):
                    if v is None: continue
                    pts.append(f'{i/max(1,len(vv)-1)*900:.1f},{170-(v/vmax*150):.1f}')
                return f'<svg viewBox="0 0 900 180" preserveAspectRatio="none"><polyline points="{" ".join(pts)}"/></svg>'
            netrows=[x for x in rows if len(x)>14 and x[14]=='process_etw']
            if len(netrows)>1200:
                st=max(1,len(netrows)//1200); netrows=netrows[::st]
            def puzzle_radar_svg():
                ac=safe_mean(cp) or 0
                ar=safe_mean(rm) or 0
                ag=safe_mean(gp) or 0
                diskvals=[max(0,(x[6] or 0)+(x[7] or 0)) for x in rows]
                disk_score=min(100.0,((safe_mean(diskvals) or 0)/(50*1024**2))*100)
                ram_score=min(100.0,(ar/(4*1024**3))*100)
                down_score=min(100.0,((net24.get('down_avg') or 0)/(12.5*1024**2))*100) if net24.get('samples',0)>1 else 0
                up_score=min(100.0,((net24.get('up_avg') or 0)/(6.25*1024**2))*100) if net24.get('samples',0)>1 else 0
                vals=[ac,ram_score,ag,disk_score,down_score,up_score]
                labs=['CPU','RAM','GPU','Disk','Download','Upload']
                cx,cy,R=450,190,135; n=6
                grids=[]
                for lv in range(1,6):
                    rr=R*lv/5; pts=[]
                    for i in range(n):
                        a=-math.pi/2+2*math.pi*i/n; pts.append(f'{cx+math.cos(a)*rr:.1f},{cy+math.sin(a)*rr:.1f}')
                    grids.append(f'<polygon points="{" ".join(pts)}" class="radar-grid"/>')
                axes=[]; labels=[]; poly=[]; dots=[]
                for i,(lab,v) in enumerate(zip(labs,vals)):
                    a=-math.pi/2+2*math.pi*i/n
                    x=cx+math.cos(a)*R; y=cy+math.sin(a)*R
                    axes.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" class="radar-axis"/>')
                    lx=cx+math.cos(a)*(R+42); ly=cy+math.sin(a)*(R+35)
                    labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" class="radar-label">{lab} {v:.0f}</text>')
                    rr=R*max(0,min(100,v))/100; px=cx+math.cos(a)*rr; py=cy+math.sin(a)*rr
                    poly.append(f'{px:.1f},{py:.1f}'); dots.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" class="radar-dot"/>')
                return '<div class="radarbox"><svg class="radarsvg" viewBox="0 0 900 390">'+''.join(grids)+''.join(axes)+f'<polygon points="{" ".join(poly)}" class="radar-data"/>'+''.join(dots)+''.join(labels)+'</svg><div class="radarnote"><b>Yoğunluk skoru:</b> CPU/GPU doğrudan yüzdeye yakındır. RAM için 4 GB, Disk için 50 MB/sn, program Download için 100 Mbps ve Upload için 50 Mbps referans yoğunluk kabul edilir. Bu bir bağlantı hız testi değil, kaynak profilini kolay kıyaslamak için 0–100 görsel skordur.</div></div>'
            radar_svg=puzzle_radar_svg()
            def pie_svg():
                ac=safe_mean(cp) or 0; ar=safe_mean(rm) or 0; ag=safe_mean(gp) or 0
                diskvals=[max(0,(x[6] or 0)+(x[7] or 0)) for x in rows]
                vals=[ac,min(100.0,(ar/(4*1024**3))*100),ag,min(100.0,((safe_mean(diskvals) or 0)/(50*1024**2))*100),
                      min(100.0,((net24.get('down_avg') or 0)/(12.5*1024**2))*100) if net24.get('samples',0)>1 else 0,
                      min(100.0,((net24.get('up_avg') or 0)/(6.25*1024**2))*100) if net24.get('samples',0)>1 else 0]
                labs=['CPU','RAM','GPU','Disk','Download','Upload']; cols=['#D4AF37','#7EC8E3','#8FD694','#E49AB0','#C6A0F6','#F5A65B']; total=sum(vals) or 1
                cx,cy,R=210,180,125; start=-math.pi/2; paths=[]; legend=[]
                for i,(lab,v,col) in enumerate(zip(labs,vals,cols)):
                    ang=2*math.pi*(v/total); end=start+ang
                    x1=cx+R*math.cos(start); y1=cy+R*math.sin(start); x2=cx+R*math.cos(end); y2=cy+R*math.sin(end); large=1 if ang>math.pi else 0
                    if ang>0.0001: paths.append(f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {R} {R} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{col}" stroke="#17191D" stroke-width="2"/>')
                    share=v/total*100; legend.append(f'<rect x="410" y="{72+i*40}" width="15" height="15" rx="3" fill="{col}"/><text x="435" y="{85+i*40}" class="pie-label">{lab}: skor {v:.0f} · dağılım %{share:.1f}</text>'); start=end
                return '<div class="piebox"><svg class="piesvg" viewBox="0 0 900 370">'+''.join(paths)+''.join(legend)+'</svg><div class="radarnote"><b>Pasta analiz:</b> Dilimler ham GB/MB değerlerini değil, aynı 0–100 yoğunluk skorlarının göreli dağılımını gösterir. Böylece hangi kaynak türünün profil içinde baskın olduğu kolayca görülür.</div></div>'
            pie_chart_svg=pie_svg()
            sections.append(f'''<section><div class="head"><div><h2>{html.escape(d['name'])}</h2><p>PID {d['pid']} · {html.escape(d['exe'] or 'Yol bilgisi yok')}</p></div><b>Profesyonel Takip Raporu</b></div>{warning}<div class="stats">{cardhtml}</div>
            <h3>Zaman Aralığına Göre Program Performansı</h3><div class="tablewrap"><table><thead><tr><th>Dönem</th><th>Ölçülen veri</th><th>Ort. CPU</th><th>Ort. çekirdek</th><th>Ort. RAM</th><th>Maks. RAM</th><th>Ort. GPU</th><th>Disk hızı</th></tr></thead><tbody>{trs}</tbody></table></div>
            <h3>Program İnternet Analizi — ETW / PID Bazlı</h3><div class="notice"><b>Doğrudan süreç ölçümü:</b> Aşağıdaki Download/Upload değerleri Windows ETW ağ olaylarındaki PID ve byte boyutlarından hesaplanır; sistem toplamı değildir. ETW için programın Yönetici olarak çalışması gerekir.</div>
            <div class="tablewrap"><table><thead><tr><th>Dönem</th><th>Ölçülen veri</th><th>Ort. Download</th><th>Ort. Upload</th><th>Maks. Download</th><th>Maks. Upload</th><th>Toplam Download</th><th>Toplam Upload</th><th>Saatlik Ortalama Transfer</th></tr></thead><tbody>{net_trs}</tbody></table></div>
            <h3>Son 24 Saat — Programın Saat Saat İnternet Trafiği</h3><div class="tablewrap"><table><thead><tr><th>Saat</th><th>Ölçülen süre</th><th>Download</th><th>Upload</th><th>Ort. Download Hızı</th><th>Ort. Upload Hızı</th></tr></thead><tbody>{hour_trs}</tbody></table></div>
            <h3>Puzzle Analiz — Kaynak Kullanım Profili</h3><div class="puzzlegrid">{puzzle_html}</div><div class="explain"><b>Sonuç:</b> {html.escape(puzzle_summary)}</div><h3>Puzzle Grafik — 6 Eksenli Kaynak Profili</h3>{radar_svg}<h3>Pasta (Pie) Analiz Raporu — Kaynak Dağılımı</h3>{pie_chart_svg}
            <div class="explain"><b>Nasıl okunur?</b> “Ort. CPU %17,4” tüm işlemci kapasitesinin yaklaşık %17,4'ünün bu program tarafından kullanıldığı anlamına gelir. “1,39 çekirdek” aynı yükün yaklaşık 1,39 mantıksal çekirdeğe denk geldiğini anlatır. RAM ve GPU belleği 1024 MB'ı geçtiğinde otomatik olarak GB gösterilir. Program internet bölümündeki “Saatlik Ortalama Transfer”, ölçülen dönemdeki gerçek toplam trafiğin saat başına düşen karşılığıdır.</div>
            <div class="chart"><h3>Toplam CPU (%)</h3>{svg([x[1] for x in ds],True)}</div><div class="chart"><h3>RAM</h3>{svg([x[2] for x in ds])}</div><div class="chart"><h3>GPU (%)</h3>{svg([x[4] for x in ds])}</div><div class="chart"><h3>Program Download Hızı (MB/sn)</h3>{svg([(x[9] or 0)/1048576 for x in netrows])}</div><div class="chart"><h3>Program Upload Hızı (MB/sn)</h3>{svg([(x[8] or 0)/1048576 for x in netrows])}</div></section>''')
        return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Elite Process Monitor Pro</title><style>:root{{--bg:#17191D;--s:#202329;--s2:#292D34;--g:#D4AF37;--g2:#F0D777;--t:#F4F4F4;--m:#9DA3AE;--b:#3B4049}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--t);font-family:Segoe UI,Arial,sans-serif;line-height:1.45}}.wrap{{max-width:1400px;margin:auto;padding:28px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-end}}h1,h2{{color:var(--g2)}}section{{background:var(--s);border:1px solid var(--b);border-radius:18px;padding:20px;margin:18px 0;box-shadow:0 12px 34px #0004}}.head{{display:flex;justify-content:space-between;gap:20px}}.head b{{background:var(--g);color:#111;padding:8px 12px;border-radius:999px;height:max-content}}p{{color:var(--m);word-break:break-all}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.stat,.chart,.explain,.notice,.puzzle{{background:var(--s2);border:1px solid var(--b);border-radius:12px;padding:12px;margin-top:10px}}.puzzlegrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.puzzle span{{display:block;color:var(--m);font-size:12px}}.puzzle b{{display:block;color:var(--g2);font-size:18px;margin:4px 0}}.puzzle p{{margin:0;color:#d7d9dd}}.stat span{{display:block;color:var(--m)}}.stat strong{{color:var(--g2);font-size:19px}}.notice{{border-color:#8e7931;color:#f4e8b4}}.explain{{color:#d7d9dd}}.tablewrap{{overflow:auto;border:1px solid var(--b);border-radius:12px}}table{{width:100%;border-collapse:collapse;min-width:950px}}th,td{{padding:11px;border-bottom:1px solid var(--b);text-align:left}}th{{background:#242830;color:var(--g2)}}td{{background:#1e2126}}svg{{width:100%;height:190px;background:#1b1e23;border-radius:10px}}polyline{{fill:none;stroke:var(--g);stroke-width:3;vector-effect:non-scaling-stroke}}.nodata{{padding:40px;text-align:center;color:var(--m)}}.radarbox{{background:#1b1e23;border:1px solid var(--b);border-radius:14px;padding:12px;margin-top:10px}}.radarsvg{{width:100%;height:390px;background:#1b1e23}}.radar-grid{{fill:none;stroke:#3a4049;stroke-width:1}}.radar-axis{{stroke:#4b515b;stroke-width:1}}.radar-data{{fill:rgba(212,175,55,.25);stroke:var(--g2);stroke-width:3}}.radar-dot{{fill:var(--g2)}}.radar-label{{fill:#d7d9dd;font-size:15px;font-weight:700}}.radarnote{{color:var(--m);font-size:13px;padding:4px 8px 8px}}.piebox{{background:#1b1e23;border:1px solid var(--b);border-radius:14px;padding:12px;margin-top:10px}}.piesvg{{width:100%;height:370px;background:#1b1e23}}.pie-label{{fill:#d7d9dd;font-size:15px;font-weight:700}}footer{{color:var(--m);text-align:center;padding:25px}}@media(max-width:900px){{.stats,.puzzlegrid{{grid-template-columns:repeat(2,1fr)}}header,.head{{display:block}}}}@media(max-width:520px){{.wrap{{padding:12px}}.stats,.puzzlegrid{{grid-template-columns:1fr}}}}</style></head><body><div class="wrap"><header><div><h1>ELITE PROCESS MONITOR PRO</h1><p>CPU · RAM · NVIDIA/AMD/Intel GPU · Disk · Süreç İnterneti (ETW) · Saatlik Trafik · Puzzle Grafik · Pasta Analiz · Sıcaklık</p></div><div>{datetime.now():%d.%m.%Y %H:%M:%S}</div></header>{''.join(sections)}<footer>Rapor yalnızca uygulamanın gerçekten kaydettiği ölçümlerden hesaplanır.</footer></div></body></html>'''

    def closeEvent(self,e):
        if getattr(self,'_really_quit',False): self.netmon.stop(); self.db.close(); e.accept(); return
        e.ignore(); self.hide(); self.tray.showMessage(APP_NAME,'Program görev çubuğu bildirim alanında ölçüm yapmaya devam ediyor.',QSystemTrayIcon.Information,2500)


def main():
    app=QApplication(sys.argv); app.setQuitOnLastWindowClosed(False); app.setStyle('Fusion'); w=Main(); w.show(); sys.exit(app.exec())
if __name__=='__main__': main()
