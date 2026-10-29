#!/usr/bin/env python3
"""OverXelis Miner: configurable, foreground Linux CPU-mining source preview."""
from pathlib import Path
import argparse, datetime, getpass, json, math, os, re, signal, sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from public_common import VERSION, EDITION, need, sha, utc, verify_package, platform_check, conflict_check, take_lock
import miner
import topology
import overxelis_fee as fee

DEFAULT_POOL = 'stratum+tcp://xel-us.kryptex.network:7019'

def validate_settings(value):
    need(isinstance(value, dict), 'Configuration must be a JSON object')
    checked = miner.validate_config(value)
    # Shape/sanity check only, not a XELIS address checksum or ownership check.
    address = checked['wallet']
    need(address.startswith('xel:') and re.fullmatch(r'xel:[a-z0-9]{20,200}', address) is not None,
         'Enter your own mainnet xel: payout address (not a seed phrase or placeholder)')
    need(re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', checked['worker']) is not None, 'Worker: 1–64 letters, numbers, dots, dashes or underscores')
    n = checked.get('threads')
    need(type(n) is int and 1 <= n <= 1024, 'threads must be an integer from 1 to 1024')
    need(checked.get('page_mode') in ('ordinary', 'hugetlb'), 'page_mode must be ordinary or hugetlb')
    return checked

def configure(path):
    need(sys.stdin.isatty(), 'Configuration wizard requires an interactive terminal')
    need(not path.exists() and not path.is_symlink(), 'Configuration already exists; edit it instead of overwriting it')
    print('OverXelis Miner ' + VERSION + ' — ' + EDITION)
    print('No private key, seed phrase, exchange password, or payment is needed.')
    print('1% scheduled developer mining: 99 active user minutes, then up to 60 seconds.\n')
    wallet = input('Your XELIS mainnet payout address (xel:...): ').strip()
    pool = input('Pool URL [' + DEFAULT_POOL + ']: ').strip() or DEFAULT_POOL
    worker = input('Worker name [overxelis-cpu]: ').strip() or 'overxelis-cpu'
    password = getpass.getpass('Pool worker password [x; input hidden]: ') or 'x'
    default_threads = len(topology.select())
    n = input('CPU threads [' + str(default_threads) + ']: ').strip()
    pages = input('Memory mode [ordinary; or hugetlb if already configured]: ').strip() or 'ordinary'
    cfg = validate_settings({'wallet': wallet, 'pool': pool, 'worker': worker, 'password': password,
                            'threads': int(n) if n else default_threads, 'page_mode': pages})
    topology.select(cfg['threads'])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(cfg, f, indent=2); f.write('\n')
    print('Saved ' + str(path) + '. Nothing is mining. Review the settings before launch.')

class Logger:
    def __init__(self):
        folder = ROOT / 'logs'; folder.mkdir(mode=0o700, exist_ok=True)
        self.path = folder / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + str(os.getpid()) + '.log')
        self.file = self.path.open('x', buffering=1)
        os.chmod(self.path, 0o600)
    def __call__(self, message):
        line = '[' + utc() + '] ' + message
        self.file.write(line + '\n'); print(line, flush=True)
    def close(self): self.file.close()

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--configure', action='store_true')
    modes.add_argument('--check', action='store_true', help='validate source/config without networking or hashing')
    modes.add_argument('--self-test', action='store_true', help='qualified-library fixed-vector tests, no pool')
    p.add_argument('--config', type=Path, default=ROOT / 'config.json')
    p.add_argument('--accept-dev-fee', action='store_true', help='acknowledge the disclosed 1% mining-time policy')
    p.add_argument('--duration', type=float, default=0, help='0: until Ctrl+C; otherwise a finite run in seconds')
    p.add_argument('--version', action='version', version='OverXelis Miner ' + VERSION + ' (' + EDITION + ')')
    a = p.parse_args(argv)
    engine = log = None; fd = None; code = 0
    try:
        need(sys.version_info >= (3,10), 'Python 3.10 or newer is required')
        need(math.isfinite(a.duration) and (a.duration == 0 or 1 <= a.duration <= 86400), 'duration must be 0 or 1–86400 seconds')
        verify_package(ROOT)
        if a.configure:
            platform_check(); configure(a.config); return 0
        cfg = None if a.self_test else validate_settings(json.loads(a.config.read_text()))
        if a.check:
            cpus = topology.select(cfg['threads'])
            print(json.dumps({'version': VERSION, 'edition': EDITION, 'config_valid': True, 'threads': len(cpus),
                              'page_mode': cfg['page_mode'], 'wallet_suffix': cfg['wallet'][-8:],
                              'hashing_started': False, 'network_started': False}))
            return 0
        platform_check()
        need(a.self_test or a.accept_dev_fee, 'Add --accept-dev-fee to acknowledge the disclosed developer time allocation')
        fd = take_lock(); conflict_check()
        library = ROOT / 'build/liboverxelis.so'
        b = json.loads((ROOT / 'build/build.json').read_text())
        q = json.loads((ROOT / 'evidence/kernel-qualification.json').read_text())
        need(b.get('status') == 'built_pending_qualification' and q.get('passed') and
             b['library_sha256'] == q['library_sha256'] == sha(library) and
             b['source_manifest_sha256'] == sha(ROOT / 'SOURCE-MANIFEST.json'),
             'Run build_public.py and qualify_public.py successfully before mining')
        need(miner.load_native(library).nx_selftest() == 0, 'Native hash self-test failed')
        if a.self_test:
            print('Native hash self-test PASSED. No pool connection was made.'); return 0
        log = Logger()
        log('OverXelis Miner Version ' + VERSION + ' | ' + EDITION)
        log('Experimental source preview; no guaranteed speed or earnings.')
        log('Developer fee: 99 active USER minutes then a FEE window up to 60 seconds; no catch-up.')
        log('Fee destination: ' + fee.FEE_POOL + ' | ' + fee.FEE_WALLET)
        log('Gross local rate includes both roles. Restart resets the beta fee schedule.')
        log('User pool: ' + cfg['pool'] + ' | Worker: ' + cfg['worker'] + ' | Payout suffix: ' + cfg['wallet'][-8:])
        def stopped(*_): raise KeyboardInterrupt
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, stopped)
        cpus = topology.select(cfg['threads'])
        engine = miner.NativeEngine(cpus, 1, miner.PAGES[cfg['page_mode']], library)
        need(engine.pages() == (len(cpus) if cfg['page_mode'] == 'hugetlb' else 0), 'Requested memory mode unavailable; no silent fallback')
        log('Workers ready: %d | Huge-page workers: %d/%d | Ctrl+C stops mining' % (len(cpus), engine.pages(), len(cpus)))
        display = fee.FeeDisplay(engine, log, 10)
        miner.VERSION = 'OverXelisMiner/' + VERSION
        fee.run_pool(engine, cfg, a.duration or float('inf'), display)
    except KeyboardInterrupt:
        code = 130
        if log: log('Stop requested; closing this miner only.')
    except Exception as error:
        code = 1
        # Avoid dumping socket/credential content supplied by a pool.
        message = 'STOP: ' + type(error).__name__ + ': ' + str(error)
        log(message) if log else print(message, file=sys.stderr)
    finally:
        if engine:
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, signal.SIG_IGN)
            engine.pause(); engine.close()
            if log: log('All native workers closed; no service or autostart was installed.')
        if log: log.close()
        if fd is not None: os.close(fd)
    return code

if __name__ == '__main__': raise SystemExit(main())
