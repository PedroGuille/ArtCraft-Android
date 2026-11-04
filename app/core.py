"""Load the previously validated source compiler without copying its logic."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
sys.path.insert(0,str(ROOT/'engine/pipeline'))
import lucy as legacy
bootstrap=legacy.tools
pipeline=legacy.pipeline
