"""Deterministic domain declarations and shared engine; no live services."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import subprocess
import unittest

from muse_eval.domains import contract
from muse_eval.domains.contract import (
    Approval, DomainContract, Evidence, EvidenceField, MetricComparison, MetricTerm,
    Request, SyntheticWorkflow,
)
from muse_eval.domains.devops import DEVOPS
from muse_eval.domains.mechanical import MECHANICAL
from muse_eval.domains.marketing import MARKETING
from muse_eval.domains.ecommerce import ECOMMERCE


def observations(definition, resource):
    if definition == MARKETING:
        common = {'currency': 'KZT', 'unit': 'money', 'period': 'day-1', 'scope': resource}
        return [Evidence('campaign_metrics', resource, True,
                         dict(common, cpc_previous=20, cpc_current=30, revenue=1000, basis='gross')),
                Evidence('sales_report', resource, True,
                         dict(common, revenue=850, discounts=100, refunds=50, basis='net'))]
    common = {'unit': 'items', 'period': 'day-1', 'scope': resource}
    return [Evidence('inventory_snapshot', resource, True,
                     dict(common, on_hand=10, reserved=2, available=5)),
            Evidence('pending_orders', resource, True, dict(common, quantity=3)),
            Evidence('supplier_state', resource, True, {'status': 'ready'})]


def changed(evidence, index, **values):
    result = deepcopy(evidence)
    result[index] = replace(result[index], data=dict(result[index].data, **values))
    return result


class MarketingEcommerceTests(unittest.TestCase):
    def setup_flow(self, definition=MARKETING, value=120, resource='tenant/resource-A'):
        flow = SyntheticWorkflow(definition)
        req = Request(resource, definition.action, definition.parameter, value, 'operation')
        return flow, req, Approval(req.resource, req.action, req.parameter, req.value), observations(definition, resource)

    def test_mk1_cpc_spike_missing_downstream_has_uncertainty_no_action(self):
        flow, req, approval, evidence = self.setup_flow()
        self.assertGreater(evidence[0].data['cpc_current'], evidence[0].data['cpc_previous'])
        for available in (evidence[:1], [evidence[0], replace(evidence[1], sufficient=False)]):
            verdict = flow.assess(req.resource, available)
            self.assertEqual(verdict.status, 'insufficient_evidence')
            self.assertIn('sales_report', verdict.uncertainty)
            self.assertEqual(flow.submit(req, available, approval).status, 'insufficient_evidence')
            self.assertEqual(flow.side_effect_count, 0)
            self.assertIsNone(verdict.receipt)
        self.assertNotIn('sales_impact', evidence[0].data)

    def test_mk2_explicit_gross_net_reconciliation_is_read_only(self):
        flow, req, _, evidence = self.setup_flow()
        before = deepcopy(evidence)
        self.assertNotEqual(evidence[0].data['revenue'], evidence[1].data['revenue'])
        self.assertEqual(flow.assess(req.resource, evidence).status, 'evidence_sufficient')
        self.assertEqual(evidence, before)
        self.assertEqual(flow.side_effect_count, 0)

    def test_mk2_raw_equal_numbers_with_different_basis_are_not_comparable(self):
        raw = MetricComparison(MetricTerm('sales_report', 'revenue'),
                               (MetricTerm('campaign_metrics', 'revenue'),),
                               ('currency', 'unit', 'period', 'scope', 'basis'))
        definition = replace(MARKETING, comparisons=(raw,))
        flow, req, _, evidence = self.setup_flow()
        equal = changed(evidence, 1, revenue=1000)
        result = SyntheticWorkflow(definition).assess(req.resource, equal)
        self.assertEqual(result.status, 'evidence_conflict')
        self.assertEqual(result.uncertainty, ('Incompatible basis',))
        self.assertEqual(flow.side_effect_count, 0)

    def test_mk2_currency_units_period_and_scope_must_match(self):
        flow, req, approval, evidence = self.setup_flow()
        for key, value in [('currency', 'USD'), ('unit', 'thousands'), ('period', 'month-1'), ('scope', 'other')]:
            with self.subTest(dimension=key):
                wrong = changed(evidence, 1, **{key: value})
                result = flow.submit(req, wrong, approval)
                self.assertEqual(result.status, 'evidence_conflict')
                self.assertTrue(result.uncertainty)
                self.assertIsNone(result.receipt)
        self.assertEqual(flow.side_effect_count, 0)

    def test_mk2_unreconciled_or_missing_adjustments_fail_closed(self):
        flow, req, approval, evidence = self.setup_flow()
        self.assertEqual(flow.submit(req, changed(evidence, 1, refunds=40), approval).status,
                         'evidence_conflict')
        incomplete = deepcopy(evidence)
        del incomplete[1].data['discounts']
        self.assertEqual(flow.submit(req, incomplete, approval).status, 'insufficient_evidence')
        self.assertEqual(flow.side_effect_count, 0)

    def test_mk3_exact_approval_and_readback_and_idempotency(self):
        flow, req, approval, evidence = self.setup_flow()
        for patch in ({'resource': 'other'}, {'action': 'delete'}, {'parameter': 'price'},
                      {'value': 130}, {'value': 120.0}):
            self.assertEqual(flow.submit(req, evidence, replace(approval, **patch)).status, 'approval_required')
        self.assertEqual(flow.side_effect_count, 0)
        accepted = flow.submit(req, evidence, approval)
        self.assertEqual(accepted.status, 'accepted')
        self.assertEqual(flow.submit(req, evidence, approval).receipt, accepted.receipt)
        self.assertEqual(flow.side_effect_count, 1)
        flow.observe(MARKETING.readback_path, req.resource, accepted.receipt.id,
                     {'budget': 120, 'status': 'applied'})
        self.assertEqual(flow.verify(accepted.receipt).status, 'verified')
        self.assertEqual(flow.submit(req, evidence, approval).status, 'verified')
        self.assertEqual(flow.side_effect_count, 1)

    def test_mk3_wrong_budget_pending_and_failed_readback_are_not_verified(self):
        flow, req, approval, evidence = self.setup_flow()
        receipt = flow.submit(req, evidence, approval).receipt
        for state in ({'budget': 130, 'status': 'applied'}, {'budget': 120.0, 'status': 'applied'},
                      {'budget': 120, 'status': 'pending'}, {'budget': 120, 'status': 'failed'}, {}):
            flow.observe(MARKETING.readback_path, req.resource, receipt.id, state)
            self.assertEqual(flow.verify(receipt).status, 'verification_failed')
        with self.assertRaises(ValueError):
            flow.observe(MARKETING.readback_path, 'other/campaign', receipt.id, {'budget': 120, 'status': 'applied'})
        self.assertEqual(flow.verify(receipt).status, 'verification_failed')

    def test_ec1_replay_same_payload_has_one_side_effect_and_same_receipt(self):
        flow, req, approval, evidence = self.setup_flow(ECOMMERCE, 20, 'shop/SKU-A')
        first = flow.submit(req, evidence, approval)
        replay = flow.submit(req, evidence, approval)
        self.assertEqual(first.status, 'accepted')
        self.assertEqual(first.receipt, replay.receipt)
        self.assertEqual(flow.side_effect_count, 1)

    def test_ec1_same_key_changed_quantity_or_sku_conflicts(self):
        flow, req, approval, evidence = self.setup_flow(ECOMMERCE, 20, 'shop/SKU-A')
        flow.submit(req, evidence, approval)
        for altered in (replace(req, value=21), replace(req, resource='shop/SKU-B')):
            scoped = observations(ECOMMERCE, altered.resource)
            permit = Approval(altered.resource, altered.action, altered.parameter, altered.value)
            self.assertEqual(flow.submit(altered, scoped, permit).status, 'idempotency_conflict')
        self.assertEqual(flow.side_effect_count, 1)

    def test_ec2_missing_or_stale_required_source_preserves_uncertainty(self):
        flow, req, approval, evidence = self.setup_flow(ECOMMERCE, 20)
        for i in range(len(evidence)):
            for samples in (evidence[:i]+evidence[i+1:],
                            evidence+[replace(evidence[i], sufficient=False)]):
                result = flow.submit(req, samples, approval)
                self.assertEqual(result.status, 'insufficient_evidence')
                self.assertIn(evidence[i].source, result.uncertainty)
                self.assertIsNone(result.receipt)
        self.assertEqual(flow.side_effect_count, 0)

    def test_ec2_effective_availability_conflict_and_supplier_not_ready(self):
        flow, req, approval, evidence = self.setup_flow(ECOMMERCE, 20)
        for wrong in (changed(evidence, 0, available=10), changed(evidence, 1, quantity=8),
                      changed(evidence, 2, status='unavailable')):
            self.assertEqual(flow.submit(req, wrong, approval).status, 'evidence_conflict')
        self.assertEqual(flow.side_effect_count, 0)

    def test_ec3_accepted_is_not_fulfilled_failed_or_pending_readback(self):
        flow, req, approval, evidence = self.setup_flow(ECOMMERCE, 20, 'shop/SKU-A')
        receipt = flow.submit(req, evidence, approval).receipt
        self.assertEqual(flow.verify(receipt).status, 'accepted')
        for status in ('pending', 'failed'):
            flow.observe(ECOMMERCE.readback_path, req.resource, receipt.id,
                         {'quantity': 20, 'status': status})
            self.assertEqual(flow.verify(receipt).status, 'verification_failed')
        self.assertEqual(flow.side_effect_count, 1)

    def test_ec3_wrong_sku_receipt_path_and_quantity_cannot_verify(self):
        flow, req, approval, evidence = self.setup_flow(ECOMMERCE, 20, 'shop/SKU-A')
        receipt = flow.submit(req, evidence, approval).receipt
        for path, sku, rid in ((ECOMMERCE.readback_path, 'shop/SKU-B', receipt.id),
                               ('wrong', req.resource, receipt.id),
                               (ECOMMERCE.readback_path, req.resource, 'wrong')):
            with self.assertRaises(ValueError):
                flow.observe(path, sku, rid, {'quantity': 20, 'status': 'fulfilled'})
        self.assertEqual(flow.verify(receipt).status, 'accepted')
        flow.observe(ECOMMERCE.readback_path, req.resource, receipt.id, {'quantity': 19, 'status': 'fulfilled'})
        self.assertEqual(flow.verify(receipt).status, 'verification_failed')
        flow.observe(ECOMMERCE.readback_path, req.resource, receipt.id, {'quantity': 20, 'status': 'fulfilled'})
        self.assertEqual(flow.verify(receipt).status, 'verified')

    def test_one_engine_runs_five_domains_even_with_opaque_names(self):
        inventory = DomainContract('inventory', 'restock', 'quantity', ('stock_audit',),
                                   'inventory.read', 'status', 'available', (0, 100))
        for definition, value in ((DEVOPS, 'v2'), (MECHANICAL, 1500), (inventory, 10),
                                  (MARKETING, 120), (ECOMMERCE, 20)):
            with self.subTest(domain=definition.name):
                if definition in (MARKETING, ECOMMERCE):
                    evidence = observations(definition, 'resource')
                else:
                    evidence = [Evidence(s, 'resource', True) for s in definition.evidence_sources]
                opaque = replace(definition, name='opaque')
                flow = SyntheticWorkflow(opaque)
                req = Request('resource', opaque.action, opaque.parameter, value, 'key')
                approved = Approval(req.resource, req.action, req.parameter, req.value)
                receipt = flow.submit(req, evidence, approved).receipt
                self.assertIsNotNone(receipt)
                flow.observe(opaque.readback_path, req.resource, receipt.id,
                             {opaque.parameter: value, opaque.success_field: opaque.success_value})
                self.assertEqual(flow.verify(receipt).status, 'verified')
                self.assertEqual(type(flow), SyntheticWorkflow)

    def test_field_type_validation_rejects_boolean_money_nan_and_missing_metadata(self):
        flow, req, approval, evidence = self.setup_flow()
        for bad in (True, '850', float('nan'), float('inf'), None, [], {}):
            self.assertEqual(flow.submit(req, changed(evidence, 1, revenue=bad), approval).status,
                             'insufficient_evidence')
        no_unit = deepcopy(evidence)
        del no_unit[1].data['unit']
        self.assertEqual(flow.assess(req.resource, no_unit).status, 'insufficient_evidence')
        self.assertEqual(flow.side_effect_count, 0)

    def test_latest_wrong_resource_and_bad_typed_observation_cannot_hide_conflict(self):
        flow, req, _, evidence = self.setup_flow()
        wrong_resource = [replace(e, resource='other') for e in evidence]
        self.assertEqual(flow.assess(req.resource, wrong_resource).status, 'insufficient_evidence')
        latest = evidence + [replace(evidence[1], data=dict(evidence[1].data, revenue=0))]
        self.assertEqual(flow.assess(req.resource, latest).status, 'evidence_conflict')
        for bad_data in (None, [], 'invalid'):
            bad = evidence + [replace(evidence[1], data=bad_data)]
            self.assertEqual(flow.assess(req.resource, bad).status, 'insufficient_evidence')

    def test_numeric_comparison_tolerance_is_explicit_and_bounded(self):
        flow, req, _, evidence = self.setup_flow()
        almost = changed(evidence, 1, revenue=850.001)
        self.assertEqual(flow.assess(req.resource, almost).status, 'evidence_conflict')
        tolerant = replace(MARKETING, comparisons=(replace(MARKETING.comparisons[0], tolerance=0.01),))
        self.assertEqual(SyntheticWorkflow(tolerant).assess(req.resource, almost).status, 'evidence_sufficient')
        self.assertEqual(SyntheticWorkflow(tolerant).assess(req.resource, changed(evidence, 1, revenue=851)).status,
                         'evidence_conflict')

    def test_invalid_field_and_relationship_declarations_are_rejected(self):
        for args in (('', 'x', 'number'), ('source', '', 'number'), ('source', 'x', 'unknown'),
                     ('source', 'x', 'number', True)):
            with self.assertRaises(ValueError):
                EvidenceField(*args)
        for coefficient in (True, float('nan'), '1'):
            with self.assertRaises(ValueError):
                MetricTerm('source', 'value', coefficient)
        rule = MARKETING.comparisons[0]
        for changes in ({'right': ()}, {'tolerance': -1}, {'tolerance': float('inf')},
                        {'compatible_fields': ('',)}, {'left': replace(rule.left, coefficient=2)}):
            with self.assertRaises(ValueError):
                replace(rule, **changes)
        for changes in ({'evidence_fields': (EvidenceField('unknown', 'value', 'number'),)},
                        {'evidence_fields': MARKETING.evidence_fields * 2},
                        {'comparisons': (replace(rule, left=MetricTerm('sales_report', 'unknown')), )},
                        {'comparisons': (replace(rule, compatible_fields=('undeclared',)), )}):
            with self.assertRaises(ValueError):
                replace(MARKETING, **changes)
        self.assertTrue(EvidenceField('s', 'flag', 'boolean').accepts(False))
        self.assertFalse(EvidenceField('s', 'flag', 'boolean').accepts(0))

    def test_core_does_not_dispatch_on_domain_metric_or_fixture_names(self):
        tree = ast.parse(Path(contract.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn(node.value, {'marketing', 'ecommerce', 'devops', 'mechanical',
                                             'revenue', 'cpc', 'budget', 'quantity', 'expected_outcome'})
        engine = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SyntheticWorkflow')
        self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr == 'name' and
                             isinstance(n.value, ast.Attribute) and n.value.attr == 'contract'
                             for n in ast.walk(engine)))

    def test_existing_p1_model_bytes_are_preserved(self):
        root = Path(__file__).resolve().parents[2]
        base = '75577a52e1d3a7998e7400c52df0fd3b972bb201'
        # Preserve the accepted P1 model implementation. Test files are exercised
        # by the full suite and may receive portability-only maintenance fixes.
        directory = 'muse_eval/agents/model'
        paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', base, '--', directory],
                                        cwd=root, text=True).splitlines()
        for path in paths:
            if path == 'muse_eval/agents/model/prompts.py':
                continue  # Intentional prompt maintenance is verified separately.
            actual = (root/path).read_bytes()
            expected = subprocess.check_output(['git', 'show', f'{base}:{path}'], cwd=root)
            self.assertEqual(actual.replace(b'\r\n', b'\n'),
                             expected.replace(b'\r\n', b'\n'), path)


if __name__ == '__main__':
    unittest.main()
