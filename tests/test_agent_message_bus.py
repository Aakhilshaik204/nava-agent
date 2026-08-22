import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nava.core.message_bus import AgentMessageBus, AgentMessage, MessageType

class TestAgentMessageBus(unittest.TestCase):
    def setUp(self):
        self.bus = AgentMessageBus()

    def test_message_bus_pub_sub(self):
        """Verify channels route messages only to subscribed agents."""
        received = []

        def on_task_msg(msg: AgentMessage):
            received.append(msg)

        self.bus.subscribe("task:1:code", on_task_msg, subscriber_id="sub-coder")

        # Publish to matching channel
        msg1 = AgentMessage(
            sender_id="agt-1",
            sender_role="CodingAgent",
            channel="task:1:code",
            msg_type=MessageType.DATA_SHARE,
            payload={"file": "auth.py", "lines": 42}
        )
        self.bus.publish(msg1)

        # Publish to non-matching channel
        msg2 = AgentMessage(
            sender_id="agt-2",
            sender_role="BrowserAgent",
            channel="task:1:browser",
            msg_type=MessageType.DATA_SHARE,
            payload={"url": "https://example.com"}
        )
        self.bus.publish(msg2)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload["file"], "auth.py")

    def test_progress_broadcasting(self):
        """Verify broadcast_progress calculates percentages and notifies listeners."""
        progress_events = []

        def on_progress(msg: AgentMessage):
            progress_events.append(msg)

        self.bus.subscribe("broadcast:progress", on_progress)

        self.bus.broadcast_progress(
            agent_id="agt-research-1",
            role="ResearchAgent",
            step=2,
            max_steps=10,
            thought="Navigating to news sources...",
            tool="browser.navigate",
            status="RUNNING"
        )

        self.assertEqual(len(progress_events), 1)
        ev = progress_events[0]
        self.assertEqual(ev.sender_role, "ResearchAgent")
        self.assertEqual(ev.payload["step"], 2)
        self.assertEqual(ev.payload["percentage"], 20)
        self.assertEqual(ev.payload["tool"], "browser.navigate")

    def test_peer_review_and_feedback_loop(self):
        """Verify CodingAgent to ReviewerAgent peer review handshake with correlation IDs."""
        reviews_received = []
        feedback_received = []

        def on_review_req(msg: AgentMessage):
            if msg.msg_type == MessageType.PEER_REVIEW_REQUEST:
                reviews_received.append(msg)
                # Reviewer automatically responds with feedback
                self.bus.send_review_feedback(
                    reviewer_id="agt-reviewer-1",
                    reviewer_role="ReviewerAgent",
                    request_msg_id=msg.message_id,
                    approved=True,
                    feedback="Code clean, tests passing, no AST vulnerabilities found.",
                    suggested_fixes=[]
                )

        def on_feedback(msg: AgentMessage):
            if msg.msg_type == MessageType.PEER_REVIEW_FEEDBACK:
                feedback_received.append(msg)

        self.bus.subscribe("peer_review", on_review_req, subscriber_id="reviewer")
        self.bus.subscribe("peer_review", on_feedback, subscriber_id="coder")

        # CodingAgent submits diff for review
        req_id = self.bus.request_peer_review(
            sender_id="agt-coder-1",
            sender_role="CodingAgent",
            file_path="src/auth.py",
            diff_text="+ def login(): return True"
        )

        self.assertEqual(len(reviews_received), 1)
        self.assertEqual(len(feedback_received), 1)
        
        fb = feedback_received[0]
        self.assertEqual(fb.correlation_id, req_id)
        self.assertTrue(fb.payload["approved"])
        self.assertIn("Code clean", fb.payload["feedback"])

    def test_global_listener_for_ui_streaming(self):
        """Verify global listener captures all events across all channels in real time."""
        all_streamed = []

        def global_streamer(msg: AgentMessage):
            all_streamed.append(msg)

        self.bus.add_global_listener(global_streamer)

        self.bus.broadcast_progress("agt-1", "CodingAgent", 1, 5, "Writing patch...")
        self.bus.request_peer_review("agt-1", "CodingAgent", "app.py", "diff")

        self.assertEqual(len(all_streamed), 2)
        history = self.bus.get_all_events()
        self.assertEqual(len(history), 2)

if __name__ == "__main__":
    unittest.main()
