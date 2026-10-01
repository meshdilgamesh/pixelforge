#!/usr/bin/env python3
"""PixelForge entry point.

  python pixelforge.py                    launch the local web UI
  python pixelforge.py image.jpg -t 4k    CLI upscaling (see --help)
  python pixelforge.py update             check for + apply updates
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "update":
        from pixelforge.update import apply

        apply()
        return
    if argv and argv[0] == "ui":
        argv = argv[1:]
        import argparse

        p = argparse.ArgumentParser(prog="pixelforge ui")
        p.add_argument("--port", type=int, default=8477)
        p.add_argument("--no-open", action="store_true", help="don't open the browser")
        args = p.parse_args(argv)
        from pixelforge.server import serve

        serve(open_browser=not args.no_open, port=args.port)
        return
    if not argv:
        from pixelforge.server import serve

        serve()  # running with no arguments = open the app
        return
    from pixelforge.cli import main as cli_main

    cli_main(argv)


if __name__ == "__main__":
    main()
