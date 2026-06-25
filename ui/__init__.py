"""UI layer — desktop interface (supports both PySide6 and Tkinter backends)."""

__all__ = ["MainWindow", "TkApp"]


def __getattr__(name):
    """Lazy import — avoid requiring both PySide6 and Tkinter at load time."""
    if name == "MainWindow":
        from ui.main_window import MainWindow as _mw
        return _mw
    if name == "TkApp":
        from ui.tk_app import TkApp as _ta
        return _ta
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
