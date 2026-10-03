from .config import Model


class StatusResponse(Model):
    failures: list[str]
