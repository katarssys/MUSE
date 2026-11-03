"""Synthetic deployment contract; resources include cluster and service scope."""
from .contract import DomainContract

DEVOPS = DomainContract(
    name='devops', action='deploy', parameter='version',
    evidence_sources=('release_validation', 'deployment_plan'),
    readback_path='deployment.health', success_field='health', success_value='healthy',
)
