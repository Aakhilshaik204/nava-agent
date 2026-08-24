import os
import sys

def main():
    """CLI entrypoint for `nava` command when installed via pip or pipx."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from nava.ui.cowork_tui import CoworkTUI
    tui = CoworkTUI()
    tui.run()

if __name__ == "__main__":
    main()
