"""Synthetic campaign declarations; no Ads or sales API integration."""
from .contract import DomainContract, EvidenceField, MetricComparison, MetricTerm


MARKETING = DomainContract(
    name='marketing', action='change_budget', parameter='budget',
    evidence_sources=('campaign_metrics', 'sales_report'),
    readback_path='campaign.budget', success_field='status', success_value='applied',
    envelope=(0, 100000),
    evidence_fields=(
        EvidenceField('campaign_metrics', 'cpc_previous', 'number'),
        EvidenceField('campaign_metrics', 'cpc_current', 'number'),
        EvidenceField('campaign_metrics', 'revenue', 'number'),
        EvidenceField('campaign_metrics', 'basis', 'string', 'gross'),
        EvidenceField('sales_report', 'revenue', 'number'),
        EvidenceField('sales_report', 'discounts', 'number'),
        EvidenceField('sales_report', 'refunds', 'number'),
        EvidenceField('sales_report', 'basis', 'string', 'net'),
    ) + tuple(EvidenceField(source, name, 'string')
              for source in ('campaign_metrics', 'sales_report')
              for name in ('currency', 'unit', 'period', 'scope')),
    # Explicit gross -> net reconciliation. No exchange rate or basis is inferred.
    comparisons=(MetricComparison(
        MetricTerm('sales_report', 'revenue'),
        (MetricTerm('campaign_metrics', 'revenue'),
         MetricTerm('sales_report', 'discounts', -1),
         MetricTerm('sales_report', 'refunds', -1)),
        compatible_fields=('currency', 'unit', 'period', 'scope'),
    ),),
)
