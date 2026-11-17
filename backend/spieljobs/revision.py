"""Identify the loaded source snapshot so local launchers reject stale workers."""
from hashlib import sha256
from pathlib import Path


def runtime_revision():
    root=Path(__file__).parent
    snapshot=b''.join(path.read_bytes() for path in sorted(path for path in root.iterdir() if path.suffix in ('.py','.json')))
    digest=sha256(snapshot+(root.parent/'requirements.txt').read_bytes()).hexdigest()[:12]
    return 'iran-mvp-' + digest


RUNTIME_REVISION = runtime_revision()
