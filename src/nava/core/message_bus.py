import time
import uuid
import threading
from enum import Enum
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from pydantic import BaseModel, Field

class MessageType(str, Enum):
    PROGRESS = "PROGRESS"
    PEER_REVIEW_REQUEST = "PEER_REVIEW_REQUEST"
    PEER_REVIEW_FEEDBACK = "PEER_REVIEW_FEEDBACK"
    DATA_SHARE = "DATA_SHARE"
    SYSTEM_EVENT = "SYSTEM_EVENT"

class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:10]}")
    sender_id: str
    sender_role: Optional[str] = None
    recipient_id: Optional[str] = None
    channel: str
    msg_type: MessageType
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None

class AgentMessageBus:
    """
    Thread-Safe Inter-Agent Pub/Sub Message Bus (Blueprint Section 24 & Claude Cowork Pillar B).
    Enables dynamic subagents to communicate across channels, broadcast live progress,
    and execute closed-loop peer review and self-correction.
    """
    def __init__(self):
        self._lock = threading.RLock()
        # channel_name -> list of (subscriber_id, callback)
        self._subscribers: Dict[str, List[tuple]] = {}
        # Global message history
        self._history: List[AgentMessage] = []
        # Listeners for all events (e.g. Frontend WebSocket/SSE streamers)
        self._global_listeners: List[Callable[[AgentMessage], None]] = []

    def subscribe(self, channel: str, callback: Callable[[AgentMessage], None], subscriber_id: Optional[str] = None) -> None:
        """Subscribes an agent callback to a specific channel."""
        with self._lock:
            sub_id = subscriber_id or str(uuid.uuid4())
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._subscribers[channel].append((sub_id, callback))

    def unsubscribe(self, channel: str, subscriber_id: str) -> None:
        """Removes a subscriber from a channel."""
        with self._lock:
            if channel in self._subscribers:
                self._subscribers[channel] = [
                    (s_id, cb) for s_id, cb in self._subscribers[channel] if s_id != subscriber_id
                ]

    def add_global_listener(self, callback: Callable[[AgentMessage], None]) -> None:
        """Registers a global listener that receives every published message (e.g. for UI streaming)."""
        with self._lock:
            self._global_listeners.append(callback)

    def publish(self, message: AgentMessage) -> str:
        """
        Publishes a message to its designated channel, notifying all registered subscribers
        and global listeners.
        """
        with self._lock:
            self._history.append(message)
            channel_subs = list(self._subscribers.get(message.channel, []))
            global_listeners = list(self._global_listeners)

        # Notify channel subscribers
        for sub_id, callback in channel_subs:
            try:
                callback(message)
            except Exception as e:
                print(f"[AgentMessageBus] Error in subscriber {sub_id} on {message.channel}: {e}")

        # Notify global listeners (e.g. WebSocket streamers)
        for listener in global_listeners:
            try:
                listener(message)
            except Exception as e:
                print(f"[AgentMessageBus] Error in global listener: {e}")

        return message.message_id

    def broadcast_progress(
        self, 
        agent_id: str, 
        role: str, 
        step: int, 
        max_steps: int, 
        thought: str, 
        tool: Optional[str] = None, 
        status: str = "RUNNING"
    ) -> AgentMessage:
        """Broadcasts live progress metrics from an active agent to the global stream."""
        percentage = min(100, int((step / max(1, max_steps)) * 100))
        msg = AgentMessage(
            sender_id=agent_id,
            sender_role=role,
            channel="broadcast:progress",
            msg_type=MessageType.PROGRESS,
            payload={
                "step": step,
                "max_steps": max_steps,
                "percentage": percentage,
                "thought": thought,
                "tool": tool,
                "status": status
            }
        )
        self.publish(msg)
        return msg

    def request_peer_review(
        self, 
        sender_id: str, 
        sender_role: str, 
        file_path: str, 
        diff_text: str, 
        channel: str = "peer_review"
    ) -> str:
        """Publishes a peer review request from a worker agent (e.g. CodingAgent)."""
        msg = AgentMessage(
            sender_id=sender_id,
            sender_role=sender_role,
            channel=channel,
            msg_type=MessageType.PEER_REVIEW_REQUEST,
            payload={
                "file_path": file_path,
                "diff_text": diff_text,
                "lines_count": len(diff_text.splitlines())
            }
        )
        return self.publish(msg)

    def send_review_feedback(
        self, 
        reviewer_id: str, 
        reviewer_role: str, 
        request_msg_id: str, 
        approved: bool, 
        feedback: str, 
        suggested_fixes: Optional[List[str]] = None,
        channel: str = "peer_review"
    ) -> str:
        """Publishes peer review feedback (approval or changes requested)."""
        msg = AgentMessage(
            sender_id=reviewer_id,
            sender_role=reviewer_role,
            channel=channel,
            msg_type=MessageType.PEER_REVIEW_FEEDBACK,
            correlation_id=request_msg_id,
            payload={
                "approved": approved,
                "feedback": feedback,
                "suggested_fixes": suggested_fixes or []
            }
        )
        return self.publish(msg)

    def get_channel_history(self, channel: str, limit: int = 50) -> List[AgentMessage]:
        """Returns recent message history for a specific channel."""
        with self._lock:
            filtered = [m for m in self._history if m.channel == channel]
            return filtered[-limit:]

    def get_all_events(self, limit: int = 100) -> List[AgentMessage]:
        """Returns all recent messages across all channels."""
        with self._lock:
            return self._history[-limit:]
