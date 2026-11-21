"""API web del robot Clementoni AIRO (FastAPI)."""

from .service import CATALOGO, RobotService, Traductor

__all__ = ["CATALOGO", "RobotService", "Traductor"]
