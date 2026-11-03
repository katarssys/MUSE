"""Synthetic restock declarations; no shop, supplier or warehouse integration."""
from .contract import DomainContract, EvidenceField, MetricComparison, MetricTerm


ECOMMERCE = DomainContract(
    name='ecommerce', action='restock', parameter='quantity',
    evidence_sources=('inventory_snapshot', 'pending_orders', 'supplier_state'),
    readback_path='inventory.fulfillment', success_field='status', success_value='fulfilled',
    envelope=(1, 10000),
    evidence_fields=(
        EvidenceField('inventory_snapshot', 'on_hand', 'number'),
        EvidenceField('inventory_snapshot', 'reserved', 'number'),
        EvidenceField('inventory_snapshot', 'available', 'number'),
        EvidenceField('pending_orders', 'quantity', 'number'),
        EvidenceField('supplier_state', 'status', 'string', 'ready'),
    ) + tuple(EvidenceField(source, name, 'string')
              for source in ('inventory_snapshot', 'pending_orders')
              for name in ('unit', 'period', 'scope')),
    comparisons=(MetricComparison(
        MetricTerm('inventory_snapshot', 'available'),
        (MetricTerm('inventory_snapshot', 'on_hand'),
         MetricTerm('inventory_snapshot', 'reserved', -1),
         MetricTerm('pending_orders', 'quantity', -1)),
        compatible_fields=('unit', 'period', 'scope'),
    ),),
)
