import sys
import os

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import unittest
import tempfile
import datetime
from nava.core.schemas import AgentState, AgentType, Receipt, ResultEnum
from nava.skills.manager import SkillManager, SkillTrustState
from nava.skills.promotion import SkillPromoter, PromotionCandidate


class TestStep4SkillPromotion(unittest.TestCase):
    def setUp(self):
        os.environ["NAVA_TEST_MODE"] = "1"
        self.tmpdir = tempfile.TemporaryDirectory()
        self.skills_dir = os.path.join(self.tmpdir.name, "skills")
        self.ledger_path = os.path.join(self.tmpdir.name, "trusted_plugins.json")
        os.makedirs(self.skills_dir, exist_ok=True)
        
        self.skill_manager = SkillManager(search_paths=[self.skills_dir], ledger_path=self.ledger_path)
        self.promoter = SkillPromoter(self.skill_manager, base_skills_dir=self.skills_dir)
        
        self.agent = AgentState(
            agent_id="agt-data-scraper-1",
            role="DataScraperAgent",
            type=AgentType.DYNAMIC,
            goal="Scrape weekly sales figures and export CSV",
            permission_scope=["filesystem.write", "filesystem.read"],
            credential_scope=[],
            tool_scope=["file.write", "file.read"],
            depth=1,
            ttl=datetime.timedelta(minutes=5),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
            budget_ref="task-sales-1"
        )
        
        from nava.core.schemas import RiskAssessment, RiskTier, RiskDecision
        dummy_risk = RiskAssessment(
            assessment_id="risk-1",
            tool_request_id="req-1",
            total_score=10,
            tier=RiskTier.LOW,
            decision=RiskDecision.AUTO_EXECUTE
        )
        
        self.receipts = [
            Receipt(
                receipt_id="rcpt-1",
                task_id="task-sales-1",
                agent_id=self.agent.agent_id,
                parent_agent_id="root",
                tool_name="file.read",
                action_summary="Read sales data",
                risk_assessment=dummy_risk,
                result=ResultEnum.SUCCESS,
                result_data={"status": "extracted sales raw data"},
                executed_at=datetime.datetime.utcnow()
            ),
            Receipt(
                receipt_id="rcpt-2",
                task_id="task-sales-1",
                agent_id=self.agent.agent_id,
                parent_agent_id="root",
                tool_name="file.write",
                action_summary="Save sales CSV",
                risk_assessment=dummy_risk,
                result=ResultEnum.SUCCESS,
                result_data={"status": "saved sales.csv"},
                executed_at=datetime.datetime.utcnow()
            )
        ]

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_skill_promoter_creates_candidate_without_auto_promoting(self):
        """Invariant: Tasks are NOT auto-promoted; promoter creates candidate waiting for user decision."""
        candidate = self.promoter.evaluate_and_propose_candidate(
            agent_state=self.agent,
            receipts=self.receipts,
            goal=self.agent.goal
        )
        
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.agent_id, self.agent.agent_id)
        self.assertEqual(len(self.promoter.list_candidates()), 1)
        
        # Invariant: Skills directory must remain clean until user approves
        self.assertEqual(len(self.skill_manager.get_all_skills()), 0)

    def test_skill_promoter_reject_candidate(self):
        """Verify user can dismiss/reject a promotion candidate."""
        self.promoter.evaluate_and_propose_candidate(
            agent_state=self.agent,
            receipts=self.receipts,
            goal=self.agent.goal
        )
        self.assertEqual(len(self.promoter.list_candidates()), 1)
        
        rejected = self.promoter.reject_candidate(self.agent.agent_id)
        self.assertTrue(rejected)
        self.assertEqual(len(self.promoter.list_candidates()), 0)

    def test_skill_promoter_user_approved_promotion(self):
        """Verify user-approved promotion writes SKILL.md, YAML frontmatter, and hash-locks into ledger."""
        self.promoter.evaluate_and_propose_candidate(
            agent_state=self.agent,
            receipts=self.receipts,
            goal=self.agent.goal
        )
        
        # User approves candidate with custom name
        promoted_skill = self.promoter.promote_candidate(
            identifier=self.agent.agent_id,
            custom_name="weekly_sales_exporter",
            custom_description="Exports weekly sales reports to CSV format"
        )
        
        self.assertIsNotNone(promoted_skill)
        self.assertEqual(promoted_skill.name, "weekly_sales_exporter")
        self.assertEqual(promoted_skill.trust_state, SkillTrustState.TRUSTED)
        
        # Verify file on disk
        skill_file = os.path.join(self.skills_dir, "weekly_sales_exporter", "SKILL.md")
        self.assertTrue(os.path.exists(skill_file))
        
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("name: weekly_sales_exporter", content)
            self.assertIn("tools: ['file.read', 'file.write']", content)
            self.assertIn("permissions: ['filesystem.read', 'filesystem.write']", content)

    def test_skill_manager_export_skill_prompt_context(self):
        """Verify trusted skills are properly formatted for agent/planner reasoning context."""
        self.promoter.evaluate_and_propose_candidate(
            agent_state=self.agent,
            receipts=self.receipts,
            goal=self.agent.goal
        )
        self.promoter.promote_candidate(
            identifier=self.agent.agent_id,
            custom_name="sales_scraper",
            custom_description="Scrapes sales"
        )
        
        prompt_ctx = self.skill_manager.export_skill_prompt_context()
        self.assertIn("[APPROVED USER SKILLS]", prompt_ctx)
        self.assertIn("Skill: sales_scraper", prompt_ctx)

    def test_promoted_skill_tamper_detection(self):
        """Verify modifying a promoted SKILL.md flips trust to UNTRUSTED_MODIFIED (Section 30)."""
        self.promoter.evaluate_and_propose_candidate(
            agent_state=self.agent,
            receipts=self.receipts,
            goal=self.agent.goal
        )
        self.promoter.promote_candidate(
            identifier=self.agent.agent_id,
            custom_name="tamper_test_skill",
            custom_description="Testing tamper detection"
        )
        
        skill_file = os.path.join(self.skills_dir, "tamper_test_skill", "SKILL.md")
        
        # Tamper with file
        with open(skill_file, "a", encoding="utf-8") as f:
            f.write("\n<!-- INJECTED MALICIOUS PROMPT -->\n")
            
        # Refresh manager
        self.skill_manager.refresh_skills()
        tampered_skill = self.skill_manager.get_skill("tamper_test_skill")
        self.assertEqual(tampered_skill.trust_state, SkillTrustState.UNTRUSTED_MODIFIED)


if __name__ == "__main__":
    unittest.main()
