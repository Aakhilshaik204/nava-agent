import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.abspath("src"))

from nava.ui.cowork_tui import CoworkTUI

def main():
    tui = CoworkTUI()
    tui.run()

if __name__ == "__main__":
    main()
