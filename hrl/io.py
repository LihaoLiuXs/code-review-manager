"""Small atomic local-file helpers; no credentials are written here."""
import json
import os
import tempfile
from pathlib import Path


def write_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.hrl-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(value)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default
