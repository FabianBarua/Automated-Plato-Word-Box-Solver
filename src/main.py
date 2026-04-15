import logging
import os
import sys

from ui.app import App


def _setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)-18s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Console handler — INFO level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    # File handler — DEBUG level, write to %APPDATA% so it works from Program Files
    log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WordBoxSolver")
    os.makedirs(log_dir, exist_ok=True)
    fh = logging.FileHandler(os.path.join(log_dir, "debug.log"), mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)


if __name__ == "__main__":
    _setup_logging()
    log = logging.getLogger("main")
    log.info("Application starting")

    app = App()
    app.mainloop()

    # Cleanup on exit
    log.info("Application closing — cleanup")
    app.is_solving = False
    app.is_paused = False
    app.is_scanning = False
    app.controller.device_manager.stop_scrcpy()
    log.info("Goodbye")
