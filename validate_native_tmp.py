"""Native-console full-suite evidence for this checkpoint; remove after review."""
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import unittest

def hashes():
    return {str(p).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path('ascii3d').glob('*')) if p.suffix in ('.py','.wgsl')}

def main():
    from quality_native_smoke_tmp import Console
    console = Console()
    root=Path('benchmarks/continuous-world-native-tests-unused-2026-11-17')
    record={'python':sys.version,'platform':platform.platform(),'source_before':hashes()}
    for code,name in ((-10,'input'),(-11,'output')):
        mode=ctypes.c_ulong()
        record[name+'_console']=bool(ctypes.windll.kernel32.GetConsoleMode(ctypes.windll.kernel32.GetStdHandle(code),ctypes.byref(mode)))
    start=time.perf_counter()
    with root.with_suffix('.txt').open('x',encoding='utf-8') as output:
        result=unittest.TextTestRunner(stream=output,verbosity=2).run(unittest.defaultTestLoader.discover('tests'))
    record.update(tests=result.testsRun,passed=result.wasSuccessful(),skipped=[(str(test), reason) for test, reason in result.skipped],
                  failures=len(result.failures),errors=len(result.errors),seconds=round(time.perf_counter()-start,3),source_after=hashes())
    record['source_unchanged']=record['source_before']==record['source_after']
    with root.with_suffix('.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
    print(json.dumps({k:v for k,v in record.items() if not k.startswith('source_')}))
    sys.exit(0 if result.wasSuccessful() and record['source_unchanged'] else 1)

if __name__ == "__main__":
    if '--native' in sys.argv:
        main()
    else:
        import subprocess
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--native'],
            cwd=Path.cwd(), creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
        print('Hidden native suite PID:', process.pid, flush=True)
        code = process.wait()
        print('Native suite exit:', code, flush=True)
        raise SystemExit(code)
