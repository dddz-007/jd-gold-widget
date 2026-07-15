import os
import sys

os.environ["JD_GOLD_SKIP_AUTO_STARTUP"] = "1"

from gold_widget_app import main


if __name__ == "__main__":
    code = main(allow_gui=False)
    if code != 0 and getattr(sys, "frozen", False) and len(sys.argv) <= 1:
        try:
            input("按 Enter 退出...")
        except EOFError:
            pass
    raise SystemExit(code)
