import time
from dataclasses import dataclass


@dataclass(frozen=True)
class GameServerRequestContext:
    requester_id: int | None
    channel_id: int | None
    requester_name: str | None = None
    source: str = "unknown"


@dataclass(frozen=True)
class PendingGameServerOperation:
    operation: str
    server_id: str
    requested_by: int
    channel_id: int
    requested_at: float
    expires_at: float


class GameServerOperationAuthorizer:
    def authorize(self, request_context: GameServerRequestContext | None, operation: str, server_id: str) -> tuple[bool, str | None]:
        return True, None


class GameServerOperationService:
    def __init__(self, timeout_seconds: int = 60, authorizer: GameServerOperationAuthorizer | None = None):
        self.timeout_seconds = timeout_seconds
        self.authorizer = authorizer or GameServerOperationAuthorizer()
        self._pending_operations: dict[tuple[int, int], PendingGameServerOperation] = {}

    def authorize(self, request_context: GameServerRequestContext | None, operation: str, server_id: str) -> tuple[bool, str | None]:
        return self.authorizer.authorize(request_context, operation, server_id)

    def create_pending(self, operation: str, server_id: str, request_context: GameServerRequestContext | None) -> PendingGameServerOperation | None:
        key = self._build_key(request_context)
        if key is None:
            return None

        now = time.time()
        pending = PendingGameServerOperation(
            operation=operation,
            server_id=server_id,
            requested_by=key[0],
            channel_id=key[1],
            requested_at=now,
            expires_at=now + self.timeout_seconds,
        )
        self._pending_operations[key] = pending
        return pending

    def peek_pending_state(self, request_context: GameServerRequestContext | None) -> tuple[PendingGameServerOperation | None, bool]:
        key = self._build_key(request_context)
        if key is None:
            return None, False

        pending = self._pending_operations.get(key)
        if pending is None:
            return None, False
        if pending.expires_at <= time.time():
            del self._pending_operations[key]
            return None, True
        return pending, False

    def peek_pending(self, request_context: GameServerRequestContext | None) -> PendingGameServerOperation | None:
        pending, _ = self.peek_pending_state(request_context)
        return pending

    def consume_pending(self, request_context: GameServerRequestContext | None) -> PendingGameServerOperation | None:
        key = self._build_key(request_context)
        if key is None:
            return None

        pending = self.peek_pending(request_context)
        if pending is None:
            return None
        del self._pending_operations[key]
        return pending

    def cancel_pending(self, request_context: GameServerRequestContext | None) -> PendingGameServerOperation | None:
        key = self._build_key(request_context)
        if key is None:
            return None
        pending = self.peek_pending(request_context)
        if pending is None:
            return None
        return self._pending_operations.pop(key, None)

    def _build_key(self, request_context: GameServerRequestContext | None) -> tuple[int, int] | None:
        if request_context is None:
            return None
        if request_context.requester_id is None or request_context.channel_id is None:
            return None
        return request_context.requester_id, request_context.channel_id