from typing import Callable, Literal

UploadState = Literal["starting", "finished", "failed"]

OnProgress = Callable[[dict], None]
OnState = Callable[[UploadState, dict], None]
