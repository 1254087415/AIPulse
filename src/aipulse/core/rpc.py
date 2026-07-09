"""JSON-RPC protocol helpers."""

from typing import Any

from pydantic import BaseModel, Field


class JsonRpcRequest(BaseModel):
    """Incoming JSON-RPC request."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcError(BaseModel):
    """JSON-RPC error object."""

    code: int
    message: str
    data: Any | None = None


class JsonRpcApplicationError(Exception):
    """Raised by handlers to return a specific JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class JsonRpcResponse(BaseModel):
    """Outgoing JSON-RPC response."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: Any | None = None
    error: JsonRpcError | None = None

    @classmethod
    def success(cls, req_id: int | str | None, result: Any) -> "JsonRpcResponse":
        return cls(id=req_id, result=result)

    @classmethod
    def failure(
        cls,
        req_id: int | str | None,
        code: int,
        message: str,
        data: Any | None = None,
    ) -> "JsonRpcResponse":
        return cls(id=req_id, error=JsonRpcError(code=code, message=message, data=data))
