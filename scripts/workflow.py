"""Run from the checkout with its isolated Python environment."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hrl.cli import main
if __name__ == '__main__':
    raise SystemExit(main('workflow'))
