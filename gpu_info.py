"""
Detecção de hardware: GPU realmente presente (nome + VRAM) e RAM do sistema.

Para escolher o modelo de IA local, o que mais importa na inferência por CPU
(padrão do llama.cpp) é a RAM. A GPU é mostrada só como informação.
"""

import os
import subprocess


def _flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _norm(s):
    return "".join(c for c in (s or "").lower() if c.isalnum())


def _present_gpus():
    """Nomes das GPUs atualmente presentes (via WMI/CIM)."""
    if os.name != "nt":
        return []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | "
             "Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=12, creationflags=_flags(),
        )
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def _nvidia_smi():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8, creationflags=_flags(),
        )
        line = out.stdout.strip().splitlines()[0]
        name, mem = [x.strip() for x in line.split(",")]
        return name, round(float(mem) / 1024.0, 1)
    except Exception:
        return None


def _registry_all():
    """Lista (DriverDesc, vram_gb) de todas as entradas de vídeo do registro."""
    if os.name != "nt":
        return []
    result = []
    try:
        import winreg
        base = (r"SYSTEM\CurrentControlSet\Control\Class"
                r"\{4d36e968-e325-11ce-bfc1-08002be10318}")
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
        for i in range(16):
            try:
                sk = winreg.OpenKey(root, f"{i:04d}")
            except OSError:
                continue
            try:
                mem, _ = winreg.QueryValueEx(sk, "HardwareInformation.qwMemorySize")
                try:
                    name, _ = winreg.QueryValueEx(sk, "DriverDesc")
                except FileNotFoundError:
                    name = "GPU"
                gb = round(mem / (1024 ** 3), 1)
                if gb > 0:
                    result.append((name, gb))
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(sk)
    except Exception:
        pass
    return result


def detect_gpu():
    """Retorna {'name', 'vram_gb', 'source'} da GPU PRESENTE (não das antigas)."""
    present = _present_gpus()

    # NVIDIA presente -> nvidia-smi dá a VRAM certa
    if present and any(k in " ".join(present).lower()
                       for k in ("nvidia", "geforce", "rtx", "gtx", "quadro")):
        r = _nvidia_smi()
        if r:
            return {"name": r[0], "vram_gb": r[1], "source": "nvidia-smi"}

    reg = _registry_all()

    if present:
        # casa o nome presente com a entrada do registro (para pegar a VRAM)
        for pname in present:
            for rname, gb in reg:
                if _norm(pname) == _norm(rname) or _norm(pname) in _norm(rname) \
                        or _norm(rname) in _norm(pname):
                    return {"name": pname, "vram_gb": gb, "source": "wmi+registry"}
        return {"name": present[0], "vram_gb": None, "source": "wmi"}

    if reg:
        name, gb = max(reg, key=lambda x: x[1])
        return {"name": name, "vram_gb": gb, "source": "registry"}
    return {"name": None, "vram_gb": None, "source": None}


def system_ram_gb():
    """RAM total do sistema em GB (ou None)."""
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(st)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return round(st.ullTotalPhys / (1024 ** 3), 1)
        # Outros SOs
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
                     / (1024 ** 3), 1)
    except Exception:
        return None
