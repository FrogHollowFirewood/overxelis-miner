"""Public beta validation helpers. No service management or privileged writes."""
from pathlib import Path
import datetime, fcntl, hashlib, json, os, platform, stat, tempfile

VERSION = '1.0.0-beta.2'
EDITION = 'public-source-preview.2'
ROOT = Path(__file__).resolve().parent

def need(ok, message):
    if not ok: raise RuntimeError(message)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def atomic_json(path, value, mode=0o600):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            os.fchmod(f.fileno(), mode)
            json.dump(value, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def verify_package(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / 'SOURCE-MANIFEST.json').read_text())
    need(manifest.get('version') == VERSION, 'Unexpected source package version')
    for name, digest in manifest['files'].items():
        rel = Path(name); f = root / rel
        need(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe source-manifest path')
        need(f.is_file() and not f.is_symlink() and f.resolve().is_relative_to(root.resolve()), 'Missing or unsafe source: ' + name)
        need(sha(f) == digest, 'Source checksum mismatch: ' + name)
    return manifest

def platform_check():
    need(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'This preview requires Linux x86-64')
    need(os.geteuid() != 0, 'Run as a normal user, not root; no sudo is required for this program')
    flags = Path('/proc/cpuinfo').read_text().lower().split()
    need('aes' in flags, 'CPU AES-NI support is required')

def conflict_check():
    import miner
    miner.guard_cpu_miners()
    known = {'overxelis.py', 'overxelis_beta2.py', 'overxelis_miner.py', 'overxelis_rig.py',
             'campaign_miner.py', 'experimental_miner.py', 'scoped_benchmark.py',
             'verified_work_benchmark.py', 'verified_work_benchmark_v6.py', 'build_public.py', 'qualify_public.py'}
    for d in Path('/proc').glob('[0-9]*'):
        if int(d.name) in (os.getpid(), os.getppid()): continue
        try:
            comm = (d / 'comm').read_text().strip().lower()
            args = [x.decode(errors='replace') for x in (d / 'cmdline').read_bytes().split(b'\0') if x]
        except (FileNotFoundError, ProcessLookupError): continue
        except PermissionError: raise RuntimeError('Cannot inspect CPU workloads; refusing an uncertain concurrent start')
        tokens = {Path(x).name for x in args[:6] if '\n' not in x}
        gpu_only = any(x in args for x in ('--disable-cpu', '--gpu-only', '--no-cpu'))
        if tokens & known or (comm.startswith(('bzminer', 'gb-jetsam', 'cpuminer', 'minerd')) and not gpu_only):
            raise RuntimeError('Another CPU miner/test was detected; stop it normally first (PID ' + d.name + ')')

def take_lock():
    # One per-user lock shared by public builds on this computer. Never truncate.
    folder = Path.home() / '.cache' / 'overxelis'
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    st = folder.lstat()
    need(stat.S_ISDIR(st.st_mode) and not folder.is_symlink() and st.st_uid == os.getuid() and not st.st_mode & 0o077,
         'Unsafe ~/.cache/overxelis permissions; expected a private directory owned by you')
    p = folder / 'cpu.lock'
    fd = os.open(p, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        s = os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and s.st_nlink == 1, 'Unsafe lock file')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd); raise
