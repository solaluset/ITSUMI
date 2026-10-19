from .config import Model


class BasicResponse(Model):
    success: bool


class StatusResponse(Model):
    failures: list[str]
