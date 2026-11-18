"""Deployment process supervisor; no acquisition/identification code here."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--user', default='ubuntu')
    args = parser.parse_args()
    if args.host.startswith('-') or args.user.startswith('-'):
        parser.error('Invalid SSH host/user')
    root = Path(__file__).resolve().parents[1]
    logs = root / 'logs'
    logs.mkdir(exist_ok=True)
    logger = logging.getLogger('deploy')
    logger.setLevel(logging.INFO)
    logger.addHandler(RotatingFileHandler(logs / 'supervisor.log', maxBytes=2_000_000, backupCount=3))
    logger.addHandler(logging.StreamHandler())
    commands = {
        'backend': [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', '8000', '--no-proxy-headers'],
        'tunnel': ['ssh', '-N', '-T', '-i', str(Path(args.key).resolve()),
                   '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=30',
                   '-o', 'ServerAliveCountMax=3', '-o', 'ConnectTimeout=15',
                   '-o', 'IdentitiesOnly=yes',
                   '-R', '127.0.0.1:18000:127.0.0.1:8000', f'{args.user}@{args.host}']
    }
    processes = {}
    outputs = {}
    def stop(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        while True:
            for name, command in commands.items():
                process = processes.get(name)
                if process is None or process.poll() is not None:
                    if process is not None:
                        logger.warning('%s exited (%s); restarting', name, process.returncode)
                        outputs[name].close()
                    # Bound subprocess logs on each restart (keep previous run).
                    path = logs / f'{name}.log'
                    if path.exists():
                        path.replace(logs / f'{name}.previous.log')
                    outputs[name] = path.open('ab')
                    processes[name] = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                                       stdout=outputs[name], stderr=subprocess.STDOUT)
                    logger.info('Started %s pid=%s', name, processes[name].pid)
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info('Stopping deployment')
    finally:
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
        for process in processes.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for output in outputs.values():
            output.close()


if __name__ == '__main__':
    main()
