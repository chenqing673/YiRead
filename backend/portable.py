"""Double-click entry point for the Windows portable release."""
import ctypes
import logging
from core.runtime import APP_DIR
from server import start_server


def main():
    try:
        log_dir = APP_DIR / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=str(log_dir / "startup.log"), encoding="utf-8", level=logging.ERROR)
        print("YiRead - close this window to stop the local service.", flush=True)
        start_server(open_browser=True)
    except Exception as exc:
        logging.exception("YiRead startup failed")
        ctypes.windll.user32.MessageBoxW(
            None,
            f"YiRead 启动失败：{exc}\n\n请将程序解压到可写目录，并检查 8765 端口是否被占用。\n详细信息见 data/startup.log。",
            "YiRead", 0x10,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
