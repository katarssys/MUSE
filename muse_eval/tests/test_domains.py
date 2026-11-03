"""Synthetic contract regressions; no live infrastructure or machinery."""
import ast
from dataclasses import replace
from pathlib import Path
import subprocess
import unittest

from muse_eval.domains import contract
from muse_eval.domains.contract import (
    Approval, DomainContract, Evidence, Request, SyntheticWorkflow,
)
from muse_eval.domains.devops import DEVOPS
from muse_eval.domains.mechanical import MECHANICAL


class DomainTests(unittest.TestCase):
    def setup_flow(self, definition=DEVOPS, value='v2'):
        flow = SyntheticWorkflow(definition)
        req = Request('scope/resource', definition.action, definition.parameter, value, 'op-1')
        approval = Approval(req.resource, req.action, req.parameter, req.value)
        evidence = [Evidence(s, req.resource, True) for s in definition.evidence_sources]
        return flow, req, approval, evidence

    def test_contract_validation(self):
        for changes in ({'name': ''}, {'action': ''}, {'parameter': ''},
                        {'evidence_sources': ()}, {'evidence_sources': ('a', 'a')},
                        {'readback_path': ''}, {'success_field': ''},
                        {'success_value': ''}, {'approval_required': 'yes'},
                        {'envelope': (3, 1)}, {'envelope': (0, float('nan'))},
                        {'envelope': (False, 3)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(DEVOPS, **changes)

    def test_request_validation(self):
        for value in (True, float('inf'), '', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Request('r', 'a', 'p', value, 'k')

    def test_d1_accepted_deployment_unhealthy(self):
        flow, req, approval, evidence = self.setup_flow()
        result = flow.submit(req, evidence, approval)
        self.assertEqual(result.status, 'accepted')
        self.assertEqual(result.receipt.request, req)
        self.assertEqual(flow.verify(result.receipt).status, 'accepted')
        flow.observe(DEVOPS.readback_path, req.resource, result.receipt.id,
                     {'version': 'v2', 'health': 'unhealthy'})
        final = flow.verify(result.receipt)
        self.assertEqual(final.status, 'verification_failed')
        self.assertEqual(final.receipt, result.receipt)

    def test_d2_wrong_scope_approval_and_duplicate_operation(self):
        flow, req, approval, evidence = self.setup_flow()
        denied = flow.submit(req, evidence, replace(approval, resource='other/service'))
        self.assertEqual(denied.status, 'approval_required')
        self.assertEqual(flow.side_effect_count, 0)
        accepted = flow.submit(req, evidence, approval)
        replay = flow.submit(req, evidence, approval)
        self.assertEqual(replay.receipt, accepted.receipt)
        self.assertEqual(flow.side_effect_count, 1)
        changed = replace(req, value='v3')
        self.assertEqual(flow.submit(changed, evidence, replace(approval, value='v3')).status,
                         'idempotency_conflict')
        self.assertEqual(flow.side_effect_count, 1)

    def test_m1_missing_inspection_retains_uncertainty(self):
        flow, req, approval, evidence = self.setup_flow(MECHANICAL, 1500)
        result = flow.submit(req, evidence[:-1], approval)
        self.assertEqual(result.status, 'insufficient_evidence')
        self.assertEqual(result.uncertainty, ('inspection',))
        self.assertIsNone(result.receipt)
        self.assertEqual(flow.side_effect_count, 0)

    def test_m2_accepted_change_unsafe_readback(self):
        flow, req, approval, evidence = self.setup_flow(MECHANICAL, 1500)
        result = flow.submit(req, evidence, approval)
        self.assertEqual(result.status, 'accepted')
        self.assertEqual(result.receipt.request, req)
        flow.observe(MECHANICAL.readback_path, req.resource, result.receipt.id,
                     {'rpm': 1500, 'status': 'normal'})
        self.assertEqual(flow.verify(result.receipt).status, 'verified')
        flow.observe(MECHANICAL.readback_path, req.resource, result.receipt.id,
                     {'rpm': 4000, 'status': 'normal'})
        self.assertEqual(flow.verify(result.receipt).status, 'verification_failed')
        self.assertEqual(flow.submit(req, evidence, approval).status, 'verification_failed')
        self.assertEqual(flow.side_effect_count, 1)

    def test_readback_correlation(self):
        flow, req, approval, evidence = self.setup_flow()
        receipt = flow.submit(req, evidence, approval).receipt
        for path, resource, rid in ((DEVOPS.readback_path, 'wrong', receipt.id),
                                    ('wrong.path', req.resource, receipt.id),
                                    (DEVOPS.readback_path, req.resource, 'unknown')):
            with self.subTest(path=path, resource=resource, rid=rid), self.assertRaises(ValueError):
                flow.observe(path, resource, rid, {'version': 'v2', 'health': 'healthy'})
        self.assertEqual(flow.verify(receipt).status, 'accepted')

    def test_readback_requires_exact_parameter_and_complete_state(self):
        flow, req, approval, evidence = self.setup_flow()
        receipt = flow.submit(req, evidence, approval).receipt
        for state in ({}, {'health': 'healthy', 'version': 'v1'},
                      {'health': 'unhealthy', 'version': 'v2'}):
            flow.observe(DEVOPS.readback_path, req.resource, receipt.id, state)
            self.assertEqual(flow.verify(receipt).status, 'verification_failed')

    def test_evidence_scope_and_latest_negative(self):
        flow, req, approval, evidence = self.setup_flow()
        wrong = [replace(e, resource='other') for e in evidence]
        self.assertEqual(flow.submit(req, wrong, approval).status, 'insufficient_evidence')
        evidence.append(replace(evidence[0], sufficient=False))
        self.assertEqual(flow.submit(req, evidence, approval).status, 'insufficient_evidence')
        self.assertEqual(flow.side_effect_count, 0)

    def test_approval_binds_action_parameter_and_value(self):
        flow, req, approval, evidence = self.setup_flow()
        for changes in ({'action': 'delete'}, {'parameter': 'other'}, {'value': 'v1'}):
            self.assertEqual(flow.submit(req, evidence, replace(approval, **changes)).status,
                             'approval_required')
        self.assertEqual(flow.side_effect_count, 0)

    def test_constraints_reject_invalid_requested_value(self):
        for value in (-1, 4000, '1500'):
            flow, req, approval, evidence = self.setup_flow(MECHANICAL, value)
            self.assertEqual(flow.submit(req, evidence, approval).status, 'constraint_rejected')
            self.assertEqual(flow.side_effect_count, 0)

    def test_domain_independence_third_contract(self):
        definition = DomainContract('inventory', 'restock', 'quantity', ('stock_audit',),
                                    'inventory.read', 'status', 'available', (0, 100))
        for c, value in ((DEVOPS, 'v2'), (MECHANICAL, 1500), (definition, 10)):
            with self.subTest(domain=c.name):
                flow, req, approval, evidence = self.setup_flow(c, value)
                receipt = flow.submit(req, evidence, approval).receipt
                flow.observe(c.readback_path, req.resource, receipt.id,
                             {c.parameter: value, c.success_field: c.success_value})
                self.assertEqual(flow.verify(receipt).status, 'verified')

    def test_generic_core_has_no_domain_dispatch(self):
        tree = ast.parse(Path(contract.__file__).read_text())
        self.assertFalse(any(isinstance(node, ast.Constant) and isinstance(node.value, str)
                             and node.value.lower() in {'devops', 'mechanical'}
                             for node in ast.walk(tree)))
        engine = next(node for node in tree.body
                      if isinstance(node, ast.ClassDef) and node.name == 'SyntheticWorkflow')
        self.assertFalse(any(isinstance(node, ast.Attribute) and node.attr == 'name'
                             for node in ast.walk(engine)))

    def test_frozen_and_existing_p1_core_unchanged(self):
        root = Path(__file__).resolve().parents[2]
        # Task starting commit, not a moving branch ref. Compare actual bytes,
        # including unstaged changes, so this guard cannot pass by staging edits.
        paths = ('muse_eval/harness', 'muse_eval/task/scenarios', 'muse_eval/schemas',
                 'muse_eval/connectors', 'muse_eval/baseline', 'muse_eval/candidate',
                 'muse_eval/agents/model')
        base = '951237878d0fd225b4b072f51692afe637fa9c5e'
        for directory in paths:
            tracked = subprocess.check_output(
                ['git', 'ls-tree', '-r', '--name-only', base, '--', directory], cwd=root, text=True)
            for name in tracked.splitlines():
                if name == 'muse_eval/agents/model/prompts.py':
                    continue  # Intentional P1 prompt maintenance is covered by dedicated tests.
                with self.subTest(path=name):
                    expected = subprocess.check_output(['git', 'show', f'{base}:{name}'], cwd=root)
                    actual = (root / name).read_bytes()
                    # Git stores text with LF while Windows checkouts may materialize
                    # CRLF. Preserve content-integrity checking without treating an
                    # EOL-only checkout transformation as a source modification.
                    self.assertEqual(actual.replace(b'\r\n', b'\n'),
                                     expected.replace(b'\r\n', b'\n'))
