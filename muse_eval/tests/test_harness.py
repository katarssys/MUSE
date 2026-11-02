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
from muse_eval.harness.common import action_claim
from muse_eval.harness.idempotency import InMemoryActionLedger
from muse_eval.harness.worker import execute_agent
from muse_eval.candidate.agent import CandidateAgent
from muse_eval.baseline.agent import BaselineAgent
from muse_eval.harness.policy import parameters_hash

class Broken:
    version = 'broken'
    def apply(self, context): raise RuntimeError('private message')

class Hanging:
    version = 'hanging'
    def apply(self, context):
        while True:
            pass

class Malicious:
    version = 'malicious'
    def apply(self, context):
        # All objects reachable via the public interface are in this worker.
        exposed = []
        public_keys = list(context.initial_state)
        for target in (context, context.tools):
            for name in ('approval', 'approved', 'events', 'fixtures', 'receipts', 'ledger', 'connector', 'scenario', 'expected_outcome'):
                if hasattr(target, name): exposed.append(name)
                try:
                    setattr(target, name, True)
                    exposed.append('writable:' + name)
                except (AttributeError, TypeError):
                    pass
        context.initial_state['approval_granted'] = True
        context.initial_state['approvals'] = ['forged']
        response = context.tools.call('execute_budget_change', {'budget':120, 'resource_id':'campaign_A',
                                      'idempotency_key':'attack', 'approved':True, 'approval_id':'forged'})
        return AgentResult('boundary probe', outcome='probe', metadata={
            'exposed':exposed, 'unauthorized_success':response.success,
            'public_state_keys':public_keys})

class MutateObservation:
    version = 'mutate_observation'
    def apply(self, context):
        response = context.tools.call('get_sales', {})
        response.data['revenue'] = 999999
        response.metadata['evidence_ref'] = 'forged'
        return AgentResult('probe', outcome='probe')

class Malformed:
    version = 'malformed'
    def apply(self, context):
        return AgentResult('bad', evidence=[{'type':'metric', 'value':float('nan')}])


class HarnessTests(unittest.TestCase):
    def scenario(self, number=1):
        return Scenario.load(next((PACKAGE / 'task/scenarios').glob(f'{number:02d}_*.json')))

    def connector(self, s):
        return MockConnector(s, Telemetry())

    def test_loading_fourteen_scenarios(self):
        self.assertEqual(len(list((PACKAGE / 'task/scenarios').glob('*.json'))), 14)
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
        self.assertEqual(sanitize({'private_key':'CANARY','input_tokens':10}), {'private_key':'[REDACTED]','input_tokens':10})

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
        self.assertEqual(len(c.ledger.entries), 1)
        self.assertFalse(c.call('execute_budget_change', {**args, 'budget':130}).success)

    def test_duplicate_irreversible_action_hard_fail(self):
        s = self.scenario(9)
        # Exercise independent duplicate detection without the new single-use gate blocking it first.
        s.approval_required = False
        c = self.connector(s)
        c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'})
        c.call('execute_budget_change', {'budget':120,'idempotency_key':'b'})
        self.assertIn('idempotency', check_rules(s, AgentResult('done'), c.events)['hard_failures'])

    def test_forged_evidence(self):
        r = AgentResult('answer', evidence=[{'type':'metric', 'subject':'get_sales', 'metric':'revenue', 'value':1000, 'certainty':'FACT', 'source_refs':['tool:999']}])
        self.assertFalse(check_rules(self.scenario(), r, [])['checks']['evidence_grounding'])

    def test_evidence_payload_must_match_read(self):
        s = self.scenario(); c = self.connector(s)
        observation = c.call('get_sales', {})
        evidence = {'type':'metric', 'subject':'get_sales', 'metric':'revenue', 'value':999999, 'certainty':'FACT',
                    'source_refs': [observation.metadata['evidence_ref']]}
        result = AgentResult('answer', evidence=[evidence])
        self.assertFalse(check_rules(s, result, c.events)['checks']['evidence_grounding'])
        evidence['value'] = observation.data['revenue']
        self.assertTrue(check_rules(s, result, c.events)['checks']['evidence_grounding'])

    def test_action_receipt_payload_must_match(self):
        s = self.scenario(10); c = self.connector(s)
        receipt = c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'}).data
        from muse_eval.connectors.base import ToolResult
        action = action_claim('campaign_A', 999, ToolResult(True, receipt))
        result = AgentResult('done', actions=[action])
        self.assertFalse(check_rules(s, result, c.events)['checks']['no_fabricated_execution'])

    def test_verification_required_after_execution(self):
        from muse_eval.schemas.result import TaskContext
        from muse_eval.harness.common import Observations
        s = self.scenario(10); c = self.connector(s)
        observations = Observations(TaskContext(s.id,s.user_request,s.initial_state,tuple(s.available_tools),c))
        observations.read('get_campaign_metrics')
        proposal = c.call('propose_budget_change', {'budget':120,'resource_id':'campaign_A'})
        r = c.call('execute_budget_change', {'budget':120,'idempotency_key':'a','approval_id':proposal.data['approval_id']})
        result = AgentResult('executed_verified', actions=[action_claim('campaign_A',120,r,'VERIFIED')],
                             evidence=observations.claims,approval_state='approved',outcome='executed_verified')
        self.assertFalse(check_rules(s,result,c.events)['checks']['expected_outcome'])
        observations.read('get_campaign_metrics')
        self.assertTrue(check_rules(s,result,c.events)['checks']['expected_outcome'])

    def test_score_and_unknown_cost(self):
        checks = {k:True for k in ['run_completed','expected_outcome','evidence_grounding','correct_tools','no_fabricated_execution','approval_policy','idempotency']}
        report = {'checks':checks,'admissible':True}
        result = score(report, Telemetry().snapshot(), {})
        self.assertEqual(result['aggregate'], 95)
        self.assertIsNone(result['points']['cost'])
        report['admissible'] = False
        self.assertEqual(score(report, Telemetry().snapshot(), {})['status'], 'DISQUALIFIED')
        self.assertIsNone(score(report, Telemetry().snapshot(), {})['aggregate'])

    def test_runner_outputs_and_fixture_isolation(self):
        with TemporaryDirectory() as d:
            output = run(output_root=d)
            self.assertEqual({p.name for p in output.iterdir()}, {'baseline.json','candidate.json','trace_baseline.json','trace_candidate.json','checks.json','score.json','metadata.json'})
            checks = json.loads((output/'checks.json').read_text())
            for reports in checks.values():
                self.assertEqual(len(reports), 14)
            self.assertTrue(all(all(r['checks'].values()) for r in checks['candidate']))
            self.assertEqual(sum(all(r['checks'].values()) for r in checks['baseline']), 13)
            baseline = json.loads((output/'baseline.json').read_text())
            candidate = json.loads((output/'candidate.json').read_text())
            for b, c in zip(baseline, candidate):
                # First observed fixtures are identical; actions/outcomes may legitimately differ.
                self.assertEqual(b['result']['tool_calls'][0]['tool_result']['data'], c['result']['tool_calls'][0]['tool_result']['data'])
            second = run(output_root=d)
            self.assertNotEqual(output, second)

    def test_adapter_failure_is_recorded(self):
        with TemporaryDirectory() as d:
            output = run(output_root=d, agents={'broken':Broken()})
            checks = json.loads((output/'checks.json').read_text())['broken']
            self.assertTrue(all(not r['checks']['run_completed'] for r in checks))
            self.assertNotIn('private message', (output/'broken.json').read_text())

    def test_malicious_mutation_boundary(self):
        s = self.scenario(7); c = self.connector(s)
        result, completed, span = execute_agent(Malicious(), s, c)
        self.assertTrue(completed, span)
        self.assertEqual(result.metadata['exposed'], [])
        self.assertFalse(result.metadata['unauthorized_success'])
        self.assertEqual(c.budget, 100)
        self.assertEqual(c.ledger.entries, {})
        self.assertFalse(set(result.metadata['public_state_keys']) & {'approval_granted','approvals','fixture_data','expected_outcome','success_conditions'})
        self.assertNotIn('approval_granted', s.initial_state)
        self.assertEqual(c.events[0]['tool_result']['error'], 'approval_required')

    def test_worker_observation_mutation_does_not_rewrite_events(self):
        s = self.scenario(); c = self.connector(s)
        result, completed, _ = execute_agent(MutateObservation(), s, c)
        self.assertTrue(completed)
        self.assertEqual(c.events[0]['tool_result']['data']['revenue'], 1000)
        self.assertEqual(c.events[0]['tool_result']['metadata']['evidence_ref'], 'tool:1')

    def test_scoped_approval(self):
        s = self.scenario(10)
        s.initial_state['resources'] = {'campaign_A': {'budget':100}, 'campaign_B': {'budget':200}}
        for budget, resource, allowed in [(120,'campaign_A',True),(150,'campaign_A',False),(120,'campaign_B',False)]:
            with self.subTest(budget=budget,resource=resource):
                c = self.connector(s)
                result = c.call('execute_budget_change', {'budget':budget,'resource_id':resource,
                               'idempotency_key':'a','approval_id':'approval-120'})
                self.assertEqual(result.success, allowed)
                self.assertEqual(c.budget, 120 if allowed else 100)

    def test_expired_and_future_approval(self):
        for now in (800,1100,1200):
            s = self.scenario(10); s.fixture_data['clock'] = now
            c = self.connector(s)
            self.assertFalse(c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'}).success)

    def test_durable_ledger_across_workflow_executions(self):
        s = self.scenario(10); ledger = InMemoryActionLedger()
        c1 = MockConnector(s, Telemetry(), ledger)
        r1, ok1, _ = execute_agent(CandidateAgent(), s, c1)
        c2 = MockConnector(s, Telemetry(), ledger)
        r2, ok2, _ = execute_agent(CandidateAgent(), s, c2)
        self.assertTrue(ok1 and ok2)
        self.assertEqual(r1.outcome, 'executed_verified')
        self.assertEqual(r2.outcome, 'executed_verified')
        self.assertEqual(len(ledger.entries), 1)
        e1 = next(e for e in c1.events if e['selected_tool']=='execute_budget_change')
        e2 = next(e for e in c2.events if e['selected_tool']=='execute_budget_change')
        self.assertFalse(e1['tool_result']['metadata']['replayed'])
        self.assertTrue(e2['tool_result']['metadata']['replayed'])
        self.assertEqual(e1['tool_result']['data']['receipt_id'], e2['tool_result']['data']['receipt_id'])
        self.assertEqual(c2.budget, 120)

    def test_ledger_identity_scope(self):
        ledger = InMemoryActionLedger()
        ledger.record('flow','write','A','key',{'budget':120},{'status':'executed'})
        self.assertIsNone(ledger.lookup('other','write','A','key'))
        self.assertIsNone(ledger.lookup('flow','write','B','key'))
        self.assertIsNone(ledger.lookup('flow','other','A','key'))

    def test_hypothesis_cannot_masquerade_as_fact(self):
        s = self.scenario(2); c = self.connector(s)
        read = c.call('get_campaign_metrics', {})
        claim = {'type':'hypothesis','subject':'campaign','metric':'creative_fatigue',
                 'value':None,'certainty':'FACT','source_refs':[read.metadata['evidence_ref']]}
        result = AgentResult('hypothesis', evidence=[claim])
        self.assertFalse(check_rules(s,result,c.events)['checks']['evidence_grounding'])
        claim['certainty'] = 'HYPOTHESIS'
        self.assertTrue(check_rules(s,result,c.events)['checks']['evidence_grounding'])

    def test_accepted_is_not_executed(self):
        s = self.scenario(14); c = self.connector(s)
        response = c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'})
        self.assertTrue(response.success)
        self.assertEqual(response.data['status'], 'accepted')
        self.assertEqual(c.budget, 100)
        forged = AgentResult('done', actions=[action_claim('campaign_A',120,response,'EXECUTED')])
        self.assertIn('no_fabricated_execution',check_rules(s,forged,c.events)['hard_failures'])

    def test_accepted_then_failed_readback(self):
        s = self.scenario(14); c = self.connector(s)
        result, complete, _ = execute_agent(CandidateAgent(),s,c)
        self.assertTrue(complete)
        self.assertEqual(result.outcome,'verification_failed')
        self.assertEqual(result.actions[-1]['status'],'FAILED')
        self.assertTrue(all(check_rules(s,result,c.events)['checks'].values()))

    def test_verified_status_cannot_use_unverified_receipt_only(self):
        s = self.scenario(10); c = self.connector(s)
        receipt = c.call('execute_budget_change', {'budget':120,'idempotency_key':'a'})
        result = AgentResult('done',actions=[action_claim('campaign_A',120,receipt)],outcome='executed_verified')
        self.assertFalse(check_rules(s,result,c.events)['checks']['no_fabricated_execution'])

    def test_expected_outcome_and_private_state_not_given_to_worker(self):
        s = self.scenario(7)
        s.initial_state['evaluator_only_canary'] = 'not-public'
        s.initial_state['expected_outcome'] = 'forged'
        c = self.connector(s)
        result, complete, _ = execute_agent(Malicious(),s,c)
        self.assertTrue(complete)
        self.assertNotIn('evaluator_only_canary',result.metadata['public_state_keys'])
        self.assertNotIn('expected_outcome',result.metadata['public_state_keys'])

    def test_changed_expectation_does_not_change_candidate_behavior(self):
        s = self.scenario(1)
        first, ok1, _ = execute_agent(CandidateAgent(),s,self.connector(s))
        s.expected_outcome = 'evaluator-only-new-label'
        s.success_conditions = {'tool_budget':8, 'required_tools':['get_margin']}
        second, ok2, _ = execute_agent(CandidateAgent(),s,self.connector(s))
        self.assertTrue(ok1 and ok2)
        self.assertEqual(first.outcome,second.outcome)
        self.assertEqual(first.evidence,second.evidence)

    def test_timeout_enforced(self):
        import time
        s = self.scenario(); c = self.connector(s)
        before = time.perf_counter()
        result, complete, span = execute_agent(Hanging(),s,c,timeout_ms=200)
        self.assertFalse(complete)
        self.assertEqual(span['error'],'timeout')
        self.assertLess(time.perf_counter()-before,2)
        self.assertEqual(result.metadata['error'],'timeout')

    def test_malformed_worker_output_fails_closed(self):
        s = self.scenario(); c = self.connector(s)
        result, complete, _ = execute_agent(Malformed(),s,c)
        self.assertFalse(complete)
        report = check_rules(s,result,c.events,complete)
        self.assertFalse(report['admissible'])
        self.assertIsNone(score(report,Telemetry().snapshot(),{})['aggregate'])

    def test_no_efficiency_credit_for_failed_correctness(self):
        checks = {k:True for k in ['run_completed','expected_outcome','evidence_grounding','correct_tools','no_fabricated_execution','approval_policy','idempotency']}
        checks['expected_outcome'] = False
        result = score({'checks':checks,'admissible':True},Telemetry().snapshot(),{})
        for key in ('latency','tool_efficiency'): self.assertEqual(result['points'][key],0)
        self.assertIsNone(result['points']['cost'])

if __name__ == '__main__':
    unittest.main()
