"""Logging centralizado."""

import logging
from datetime import datetime
from pathlib import Path

from stonks.config import settings


def setup_logger(
    name: str = "stonks",
    level: int = logging.INFO,
) -> logging.Logger:
    """Configurar logger con salida a consola y archivo."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Formato
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Consola
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Archivo
    log_dir = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"{name}_{fecha}.log"

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Silenciar librerías externas
    for lib in (
        "urllib3", "requests", "httpx",
        "yfinance", "peewee",
    ):
        logging.getLogger(lib).setLevel(logging.WARNING)

    return logger


def get_logger(name: str = "stonks") -> logging.Logger:
    """Obtener logger existente o crear uno nuevo."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
