"""Astra bypass regressions and A–J perturbations; no new benchmark scenarios."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from muse_eval.schemas.result import AgentResult, TaskContext
from muse_eval.schemas.scenario import Scenario
from muse_eval.harness.run_task import PACKAGE, run
from muse_eval.harness.common import Observations, action_claim
from muse_eval.harness.check_rules import check_rules
from muse_eval.harness.policy import parameters_hash
from muse_eval.harness.render import apply_trusted_presentation
from muse_eval.harness.telemetry import Telemetry
from muse_eval.harness.worker import execute_agent
from muse_eval.harness.idempotency import InMemoryActionLedger
from muse_eval.connectors.mock import MockConnector
from muse_eval.candidate.agent import CandidateAgent
from muse_eval.baseline.agent import BaselineAgent

class FreeTextAttacker:
    version = 'free_text_attacker'
    def apply(self, context):
        return AgentResult('Budget successfully changed; creative fatigue proven.',
                           decision_summary='Budget successfully changed.',outcome='executed_verified')

class EvaluatorP02Tests(unittest.TestCase):
    def scenario(self, number):
        return Scenario.load(next((PACKAGE/'task/scenarios').glob(f'{number:02d}_*.json')))

    def connector(self, s, ledger=None):
        return MockConnector(s,Telemetry(),ledger)

    def collect(self, s):
        c = self.connector(s)
        obs = Observations(TaskContext(s.id,s.user_request,s.initial_state,tuple(s.available_tools),c))
        obs.read('get_campaign_metrics'); obs.read('get_sales')
        return c,obs

    def finance_report(self, s):
        c,obs = self.collect(s)
        # Correct declaration cannot bypass the independent financial oracle.
        result = AgentResult('reconciled',evidence=obs.claims,outcome='revenue_basis_reconciled')
        return check_rules(s,result,c.events)

    def test_A_balanced_financial_perturbations_pass(self):
        for gross,returns,fee in [(2300,100,200),(4000,300,40),(1000,0,0),(12,7,3)]:
            with self.subTest(gross=gross):
                s=self.scenario(12);ads=s.fixture_data['get_campaign_metrics'];sales=s.fixture_data['get_sales']
                ads['reported_revenue']=gross
                sales.update(gross=gross,returns=returns,commission=fee,net=gross-returns-fee,revenue=gross-returns-fee)
                self.assertTrue(all(self.finance_report(s)['checks'].values()))

    def test_B_equation_broken_one_minor_unit_fails_despite_correct_label(self):
        s=self.scenario(12)
        s.fixture_data['get_sales']['commission']+=1
        report=self.finance_report(s)
        self.assertTrue(report['checks']['evidence_grounding'])
        self.assertFalse(report['oracle']['passed'])
        self.assertFalse(report['checks']['expected_outcome'])

    def test_C_currency_mismatch_rejects_reconciliation(self):
        s=self.scenario(12);s.fixture_data['get_sales']['currency']='KZT'
        self.assertFalse(self.finance_report(s)['checks']['expected_outcome'])

    def test_D_both_currencies_missing_not_compatible(self):
        s=self.scenario(12)
        for tool in ('get_campaign_metrics','get_sales'):s.fixture_data[tool].pop('currency')
        report=self.finance_report(s)
        self.assertFalse(report['oracle']['passed'])
        self.assertFalse(report['checks']['expected_outcome'])

    def test_E_revenue_contradicts_net_rejected(self):
        s=self.scenario(12);s.fixture_data['get_sales']['revenue']+=1
        self.assertFalse(self.finance_report(s)['checks']['expected_outcome'])

    def test_F_wrong_resource_and_budget_never_satisfy_target(self):
        actual=self.scenario(10);c=self.connector(actual)
        result,complete,_=execute_agent(CandidateAgent(),actual,c)
        self.assertTrue(complete)
        for resource,budget in [('campaign_B',120),('campaign_A',150),('campaign_B',150)]:
            with self.subTest(resource=resource,budget=budget):
                request=deepcopy(actual);request.initial_state.update(resource_id=resource,requested_budget=budget)
                report=check_rules(request,result,c.events)
                self.assertFalse(report['checks']['target_correctness'])
                self.assertFalse(report['checks']['expected_outcome'])

    def test_G_approval_120_request_150_rejected(self):
        s=self.scenario(13);c=self.connector(s)
        proposal=c.call('propose_budget_change',{'resource_id':'campaign_A','budget':150})
        self.assertEqual(proposal.data['status'],'approval_required')
        self.assertFalse(c.call('execute_budget_change',{'resource_id':'campaign_A','budget':150,
                                  'idempotency_key':'changed','approval_id':'approval-120'}).success)
        self.assertEqual(c.budget,100)

    def async_trace(self, transitions):
        s=self.scenario(14);s.fixture_data['async_transitions']=transitions
        if transitions[-1]=='executed':
            s.expected_outcome='executed_verified';s.success_conditions['predicate']='verified_execution'
            s.success_conditions.pop('expected_final_state',None)
        c,obs=self.collect(s)
        proposal=c.call('propose_budget_change',{'resource_id':'campaign_A','budget':120})
        receipt=c.call('execute_budget_change',{'resource_id':'campaign_A','budget':120,'idempotency_key':'a',
                          'approval_id':proposal.data['approval_id']})
        result=AgentResult('declared',evidence=obs.claims,actions=[action_claim('campaign_A',120,receipt)],outcome=s.expected_outcome)
        observations=[]
        for expected in transitions:
            observations.append(obs.read('get_campaign_metrics'))
            result.actions[-1]['status']='VERIFIED' if expected=='executed' else 'FAILED' if expected=='failed' else 'ACCEPTED'
            report=check_rules(s,result,c.events)
            self.assertEqual(report['checks']['expected_outcome'],expected==transitions[-1] and expected in {'executed','failed'})
        self.assertTrue(all(report['checks'].values()))
        return c,observations

    def test_H_async_pending_pending_executed(self):
        c,reads=self.async_trace(['pending','pending','executed'])
        self.assertEqual([d['current_budget'] for d in reads],[100,100,120])
        self.assertEqual(c.budget,120)

    def test_I_async_pending_failed(self):
        c,reads=self.async_trace(['pending','failed'])
        self.assertEqual([d['operation_status'] for d in reads],['pending','failed'])
        self.assertEqual(c.budget,100)

    def test_J_missing_revenue_sufficient_true_no_reconciliation(self):
        s=self.scenario(12);s.fixture_data['get_sales'].pop('revenue')
        self.assertFalse(self.finance_report(s)['checks']['expected_outcome'])
        c=self.connector(s);result,complete,_=execute_agent(CandidateAgent(),s,c)
        self.assertTrue(complete)
        self.assertEqual(result.outcome,'insufficient_data')

    def test_finance_insufficient_flag_prevents_reconciliation(self):
        s=self.scenario(12);s.fixture_data['get_sales']['sufficient']=False
        self.assertFalse(self.finance_report(s)['checks']['expected_outcome'])

    def test_finance_sources_and_metric_basis_are_required(self):
        for tool,field,value in [('get_campaign_metrics','revenue_basis','net'),('get_sales','revenue_basis','gross'),
                                 ('get_campaign_metrics','reported_revenue',750)]:
            with self.subTest(tool=tool,field=field):
                s=self.scenario(12);s.fixture_data[tool][field]=value
                self.assertFalse(self.finance_report(s)['checks']['expected_outcome'])

    def test_label_only_cannot_fake_any_of_fourteen_outcomes(self):
        for number in range(1,15):
            with self.subTest(scenario=number):
                s=self.scenario(number);r=AgentResult('correct label',outcome=s.expected_outcome)
                self.assertFalse(check_rules(s,r,[])['checks']['expected_outcome'])

    def test_async_failure_requires_proposal_write_and_failed_read(self):
        s=self.scenario(14);c=self.connector(s)
        result,complete,_=execute_agent(CandidateAgent(),s,c)
        self.assertTrue(complete)
        self.assertTrue(check_rules(s,result,c.events)['checks']['expected_outcome'])
        for removed in ['propose_budget_change','execute_budget_change','failed_read']:
            with self.subTest(removed=removed):
                events=[e for e in c.events if not (e['selected_tool']==removed or
                    removed=='failed_read' and e['tool_result']['data'].get('operation_status')=='failed')]
                self.assertFalse(check_rules(s,result,events)['checks']['expected_outcome'])

    def test_async_failed_state_cannot_hide_changed_budget(self):
        s=self.scenario(14);c=self.connector(s)
        result,complete,_=execute_agent(CandidateAgent(),s,c)
        self.assertTrue(complete)
        changed=deepcopy(c.events)
        last=changed[-1]['tool_result']['data']
        self.assertEqual(last['operation_status'],'failed')
        last['current_budget']=120
        # Keep matching metric claims so this specifically exercises the final-state oracle.
        last_ref=changed[-1]['tool_result']['metadata']['evidence_ref']
        for claim in result.evidence:
            if last_ref in claim['source_refs'] and claim['metric']=='current_budget':claim['value']=120
        report=check_rules(s,result,changed)
        self.assertTrue(report['checks']['required_evidence'])
        self.assertFalse(report['checks']['expected_outcome'])

    def test_later_failed_read_cannot_hide_behind_earlier_success(self):
        s=self.scenario(10);c=self.connector(s)
        result,complete,_=execute_agent(CandidateAgent(),s,c)
        self.assertTrue(complete)
        changed=deepcopy(c.events)
        later=deepcopy(changed[-1]);later['tool_result']['data']['current_budget']=100
        later['tool_result']['data']['operation_status']='failed'
        later['tool_result']['metadata']['evidence_ref']='later-failure'
        changed.append(later)
        self.assertFalse(check_rules(s,result,changed)['checks']['expected_outcome'])

    def test_resource_state_isolation(self):
        s=self.scenario(10);s.approval_required=False
        s.initial_state['resources']={'campaign_A':{'budget':100},'campaign_B':{'budget':200}}
        c=self.connector(s)
        r=c.call('execute_budget_change',{'resource_id':'campaign_B','budget':150,'idempotency_key':'b'})
        self.assertTrue(r.success)
        a=c.call('get_campaign_metrics',{'resource_id':'campaign_A'})
        b=c.call('get_campaign_metrics',{'resource_id':'campaign_B'})
        self.assertEqual(a.data['current_budget'],100)
        self.assertEqual(b.data['current_budget'],150)
        self.assertEqual(b.data['resource_id'],'campaign_B')
        self.assertFalse(c.call('get_campaign_metrics',{'resource_id':'unknown'}).success)

    def test_missing_required_claims_cannot_pass_business_outcome(self):
        for number in (2,12):
            s=self.scenario(number);c=self.connector(s)
            result,complete,_=execute_agent(CandidateAgent(),s,c)
            self.assertTrue(complete)
            self.assertTrue(check_rules(s,result,c.events)['checks']['expected_outcome'])
            result.evidence=[result.evidence[0]]
            report=check_rules(s,result,c.events)
            self.assertTrue(report['checks']['evidence_grounding'])
            self.assertFalse(report['checks']['required_evidence'])
            self.assertFalse(report['checks']['expected_outcome'])

    def test_free_text_cannot_override_structured_verdict(self):
        s=self.scenario(7);c=self.connector(s)
        result,complete,_=execute_agent(CandidateAgent(),s,c)
        self.assertTrue(complete)
        result.final_answer='Budget successfully changed; creative fatigue proven.'
        result.decision_summary='Budget successfully changed.'
        report=check_rules(s,result,c.events)
        apply_trusted_presentation(result,report)
        self.assertNotIn('successfully changed',result.final_answer)
        self.assertNotIn('fatigue proven',result.decision_summary)
        self.assertIn('no execution is confirmed',result.final_answer)
        with TemporaryDirectory() as d:
            p=Path(d)/'scenarios';p.mkdir();(p/'case.json').write_text(json.dumps(asdict(s)))
            output=run(p,Path(d)/'output',agents={'attack':FreeTextAttacker()})
            exported=json.loads((output/'attack.json').read_text())[0]['result']
            self.assertNotIn('successfully changed',exported['final_answer'])
            self.assertNotIn('fatigue proven',exported['decision_summary'])
            self.assertIn('disqualified',exported['final_answer'])

    def test_single_use_approval_denies_new_key_and_new_connector(self):
        s=self.scenario(10);ledger=InMemoryActionLedger();c=self.connector(s,ledger)
        args={'resource_id':'campaign_A','budget':120,'idempotency_key':'first','approval_id':'approval-120'}
        first=c.call('execute_budget_change',args)
        self.assertTrue(first.success)
        self.assertTrue(c.call('execute_budget_change',args).metadata['replayed'])
        self.assertFalse(c.call('execute_budget_change',{**args,'idempotency_key':'second'}).success)
        c2=self.connector(s,ledger)
        self.assertFalse(c2.call('execute_budget_change',{**args,'idempotency_key':'second'}).success)
        self.assertEqual(len(ledger.entries),1)

    def test_reusable_approval_is_explicit(self):
        s=self.scenario(10);s.fixture_data['approvals'][0]['reusable']=True;c=self.connector(s)
        for key in ('one','two'):
            self.assertTrue(c.call('execute_budget_change',{'budget':120,'idempotency_key':key}).success)

    def test_evaluator_independently_detects_approval_reuse(self):
        s=self.scenario(10);c=self.connector(s)
        c.call('execute_budget_change',{'budget':120,'idempotency_key':'one'})
        # Red-team forged trusted transcript models a connector defect: evaluator
        # must independently fail consumption even if the broker had allowed it.
        forged=deepcopy(c.events[0]);forged['tool_result']['data']['receipt_id']='second'
        forged['tool_result']['data']['idempotency_key']='two'
        forged['tool_result']['metadata']['evidence_ref']='tool:2'
        report=check_rules(s,AgentResult('done'),c.events+[forged])
        self.assertFalse(report['checks']['approval_policy'])
        self.assertFalse(report['admissible'])

    def test_baseline_restores_missing_sales_guard_and_readback(self):
        for number in (9,10,11,14):
            with self.subTest(scenario=number):
                s=self.scenario(number);c=self.connector(s)
                result,complete,_=execute_agent(BaselineAgent(),s,c)
                self.assertTrue(complete)
                self.assertTrue(all(check_rules(s,result,c.events)['checks'].values()))

if __name__=='__main__':unittest.main()
