class Error(Exception):
    def __init__(self, msg: str, raw_err: Exception | None = None) -> None:
        super().__init__(msg)

        self._msg = msg
        self._raw_err = raw_err

    def dict(self) -> dict:
        return {'err_msg': self._msg}


class InternalError(Error):
    pass


class InputError(Error):
    pass
