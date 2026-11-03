"""Synthetic RPM demonstration; not a safety contract for real equipment."""
from .contract import DomainContract

MECHANICAL = DomainContract(
    name='mechanical', action='set_parameter', parameter='rpm',
    evidence_sources=('vibration_sensor', 'digital_twin', 'inspection'),
    readback_path='machine.sensors', success_field='status', success_value='normal',
    envelope=(0, 3000),
)
