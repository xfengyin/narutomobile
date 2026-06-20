import json
from pathlib import Path
from datetime import datetime


def get_format_timestamp():
    now = datetime.now()
    date = now.strftime("%Y.%m.%d")
    time = now.strftime("%H.%M.%S")
    milliseconds = f"{now.microsecond // 1000:03d}"

    return f"{date}-{time}.{milliseconds}"


jL = json.load
jD = json.dump
root = Path(__file__).resolve().parent.parent.parent

is_debug = any(root.glob("MFAAvalonia*"))
logo = (root / "docs" / "imgs" / "logo.png").absolute()
