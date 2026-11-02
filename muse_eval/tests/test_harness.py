import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from muse_eval.schemas.scenario import Scenario
from muse_eval.schemas.result import AgentResult
from muse_eval.schemas.trace import sanitize
from muse_eval.connectors.mock import MockConnector
from muse_eval.harness.telemetry import Telemetry
from muse_eval.harness.check_rules import check_rules
from muse_eval.harness.score import score
from muse_eval.harness.run_task import run, PACKAGE

class HarnessTests(unittest.TestCase):
    def scenario(self, number=1):
        return Scenario.load(next((PACKAGE / 'task/scenarios').glob(f'{number:02d}_*.json')))

    def connector(self, s):
        return MockConnector(s, Telemetry())

    def test_loading_ten_scenarios(self):
        self.assertEqual(len(list((PACKAGE / 'task/scenarios').glob('*.json'))), 10)
        self.assertEqual(self.scenario().domain, 'synthetic_marketing')

    def test_invalid_schema(self):
        with TemporaryDirectory() as d:
            p = Path(d)/'bad.json'
            data = asdict(self.scenario()); data['approval_required'] = 'false'
            p.write_text(json.dumps(data))
            with self.assertRaises(ValueError): Scenario.load(p)

    def test_trace_serialization(self):
        value = {'token': 'DO_NOT_SAVE', 'chain_of_thought': 'PRIVATE', 'events': [{'password': 'SECRET'}]}
        encoded = json.dumps(sanitize(value))
        for secret in ['DO_NOT_SAVE', 'PRIVATE', 'SECRET']: self.assertNotIn(secret, encoded)

    def test_mock_reads_and_forbidden_tool(self):
        c = self.connector(self.scenario())
        self.assertTrue(c.call('get_sales', {}).success)
        self.assertFalse(c.call('get_leads', {}).success)
        self.assertFalse(c.call('unknown', {}).success)
        self.assertEqual(len(c.events), 3)

    def test_approval_cannot_be_forged_in_args(self):
        c = self.connector(self.scenario(7))
        r = c.call('execute_budget_change', {'budget':120, 'idempotency_key':'a', 'approved':True})
        self.assertFalse(r.success)
        self.assertEqual(c.budget, 100)

    def test_fabricated_execution(self):
        s = self.scenario(8)
        r = AgentResult('done', actions=[{'execution_id':'invented'}], outcome='executed_verified')
        report = check_rules(s, r, [])
        self.assertIn('no_fabricated_execution', report['hard_failures'])
        self.assertFalse(report['admissible'])

    def test_failed_receipt_does_not_confirm_execution(self):
        s = self.scenario(8); c = self.connector(s)
        self.assertFalse(c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'}).success)
        r = AgentResult('done', outcome='executed_verified')
        self.assertFalse(check_rules(s, r, c.events)['checks']['no_fabricated_execution'])

    def test_approval_violation(self):
        s = self.scenario(7)
        r = AgentResult('done', approval_state='approved')
        self.assertIn('approval_policy', check_rules(s, r, [])['hard_failures'])

    def test_idempotency_and_argument_conflict(self):
        c = self.connector(self.scenario(9))
        args = {'budget':120, 'idempotency_key':'a'}
        a, b = c.call('execute_budget_change', args), c.call('execute_budget_change', args)
        self.assertEqual(a.data, b.data)
        self.assertTrue(b.metadata['replayed'])
        self.assertEqual(len(c.receipts), 1)
        self.assertFalse(c.call('execute_budget_change', {**args, 'budget':130}).success)

    def test_duplicate_irreversible_action_hard_fail(self):
        s = self.scenario(9); c = self.connector(s)
        c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'})
        c.call('execute_budget_change', {'budget':120,'idempotency_key':'b'})
        self.assertIn('idempotency', check_rules(s, AgentResult('done'), c.events)['hard_failures'])

    def test_forged_evidence(self):
        r = AgentResult('answer', evidence=[{'claim':'sales stable', 'references':['tool:999']}])
        self.assertFalse(check_rules(self.scenario(), r, [])['checks']['evidence_grounding'])

    def test_evidence_payload_must_match_read(self):
        s = self.scenario(); c = self.connector(s)
        observation = c.call('get_sales', {})
        evidence = {'claim':'sales observed', 'data': {'revenue': 999999},
                    'references': [observation.metadata['evidence_ref']]}
        result = AgentResult('answer', evidence=[evidence])
        self.assertFalse(check_rules(s, result, c.events)['checks']['evidence_grounding'])
        evidence['data'] = observation.data
        self.assertTrue(check_rules(s, result, c.events)['checks']['evidence_grounding'])

    def test_action_receipt_payload_must_match(self):
        s = self.scenario(10); c = self.connector(s)
        receipt = c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'}).data
        result = AgentResult('done', actions=[{**receipt, 'budget': 999}])
        self.assertFalse(check_rules(s, result, c.events)['checks']['no_fabricated_execution'])

    def test_verification_required_after_execution(self):
        s = self.scenario(10); c = self.connector(s)
        r = c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'})
        result = AgentResult('executed_verified', actions=[r.data], outcome='executed_verified')
        self.assertFalse(check_rules(s, result, c.events)['checks']['expected_outcome'])
        c.call('get_campaign_metrics', {})
        self.assertTrue(check_rules(s, result, c.events)['checks']['expected_outcome'])

    def test_score_and_unknown_cost(self):
        checks = {k:True for k in ['run_completed','expected_outcome','evidence_grounding','correct_tools','no_fabricated_execution','approval_policy','idempotency']}
        report = {'checks':checks,'admissible':True}
        result = score(report, Telemetry().snapshot(), {})
        self.assertEqual(result['aggregate'], 95)
        self.assertIsNone(result['points']['cost'])
        report['admissible'] = False
        self.assertEqual(score(report, Telemetry().snapshot(), {})['status'], 'failed')

    def test_runner_outputs_and_fixture_isolation(self):
        with TemporaryDirectory() as d:
            output = run(output_root=d)
            self.assertEqual({p.name for p in output.iterdir()}, {'baseline.json','candidate.json','trace_baseline.json','trace_candidate.json','checks.json','score.json','metadata.json'})
            checks = json.loads((output/'checks.json').read_text())
            for reports in checks.values():
                self.assertEqual(len(reports), 10)
                self.assertTrue(all(all(r['checks'].values()) for r in reports))
            baseline = json.loads((output/'baseline.json').read_text())
            candidate = json.loads((output/'candidate.json').read_text())
            for b, c in zip(baseline, candidate):
                self.assertEqual(b['result']['outcome'], c['result']['outcome'])
                self.assertEqual(b['result']['actions'], c['result']['actions'])
            second = run(output_root=d)
            self.assertNotEqual(output, second)

    def test_adapter_failure_is_recorded(self):
        class Broken:
            version = 'broken'
            def apply(self, context): raise RuntimeError('private message')
        with TemporaryDirectory() as d:
            output = run(output_root=d, agents={'broken':Broken()})
            checks = json.loads((output/'checks.json').read_text())['broken']
            self.assertTrue(all(not r['checks']['run_completed'] for r in checks))
            self.assertNotIn('private message', (output/'broken.json').read_text())

if __name__ == '__main__':
    unittest.main()
