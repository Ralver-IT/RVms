"""
Exceptions used throughout the RVsp package.

All custom exceptions inherit from RvspError so callers can catch
the entire family with a single handler if desired.
"""


class BaseError(Exception):
    """Base class for all RVsp-specific errors."""
    pass


class RvspConfigError(BaseError):
    """
    Configuration or initialization errors:
      - Missing tenant ID / client ID / client secret
      - Bad environment variables
      - MSAL token acquisition failure (e.g., missing app roles)
    """
    pass


class GraphError(BaseError):
    """
    Raised when a Microsoft Graph call fails at the HTTP layer.

    Attributes:
        status_code (int): HTTP status code
        response_text (str): Raw response body from Graph
    """

    def __init__(self, message: str, status_code: int, response_text: str):
        super().__init__(f"{message} (status {status_code}): {response_text}")
        self.status_code = status_code
        self.response_text = response_text


class SharePointPathError(BaseError):
    """
    Raised when a SharePoint path or server-relative URL
    cannot be parsed or resolved to a driveItem path.
    """
    pass


class SharePointNotFoundError(BaseError):
    """
    Raised when a SharePoint file/folder/site/library is not found.
    Typically corresponds to Graph 404 responses.
    """
    pass


class SharePointPermissionError(BaseError):
    """
    Raised for Graph 401/403 responses related to SharePoint access.
    """
    pass


class SharePointConflictError(BaseError):
    """
    Raised for conflict conditions:
      - Upload conflict with conflictBehavior = "fail"
      - Attempt to create an existing folder/file with 'fail' behavior
      - Chunk upload failures that indicate a conflict
    """
    pass


def translate_graph_error(target: str, e: GraphError) -> None:
    """
    Translate a low-level GraphError into a more specific
    SharePoint exception, based on HTTP status code.

    Args:
        target: Human-readable description of the resource
                (e.g. "site /sites/Finance", "item 'foo/bar.docx'").
        e: The GraphError instance to translate.

    Raises:
        SharePointNotFoundError
        SharePointPermissionError
        SharePointConflictError
        GraphError (re-raised if we don't have a special mapping)
    """
    msg = f"{target} (Graph status {e.status_code})"

    if e.status_code == 404:
        raise SharePointNotFoundError(f"Not found: {msg}") from e

    if e.status_code in (401, 403):
        raise SharePointPermissionError(f"Permission denied: {msg}") from e

    if e.status_code == 409:
        raise SharePointConflictError(f"Conflict: {msg}") from e

    # For all other codes, bubble up the original GraphError
    raise e
