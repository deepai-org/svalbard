"""Bounded regression of the current design's interfaces and model bindings.

This is not full-chip feasibility acceptance. Deliberately simplified and
adverse fixtures retain their own assumptions; no old chip composition runs.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from design_definition import load_design

P=Path(__file__).resolve().parents[2]
CHECKS={
    'design_and_pad_contracts': ['test_contract', 'test_shared_pad_controls',
        *['test_design_definition.'+name for name in (
            'DesignDefinitionTests','ResolvedConfigurationTests','ScenarioBindingTests',
            'ReceiverSnapshotTests','HypotheticalCircuitTests','PacketFactoryTests','SharedNetworkTests','ConverterOwnershipTests','OperatingAssumptionTests','NarrowbandConfigurationTests','WiredConfigurationTests','TransmitterConfigurationTests','ExplicitExperimentTests','SnapshotEntryTests','WiredProbeSnapshotTests','PreemphasisSnapshotTests','USBInventorySnapshotTests','PacketScreenSnapshotTests','TransmitScreenSnapshotTests','ConverterScreenSnapshotTests','CDRScreenSnapshotTests','USBPacketSnapshotTests','CommonEnvelopeSnapshotTests','RFChainSnapshotTests','FilterProbeSnapshotTests','CurrentProbeSnapshotTests','TurnaroundSnapshotTests','DirectionControlSnapshotTests','TransportAssumptionSnapshotTests','HostFollowTransportSnapshotTests','FeedRFProbeSnapshotTests','PhaseBoundSnapshotTests','USBFeedSnapshotTests','ReferenceCampaignSnapshotTests','ReferenceRequirementSnapshotTests','ReferenceStartupSnapshotTests','HandoverSnapshotTests','FiniteReplaySnapshotTests','ExtendedReplaySnapshotTests','RetuneSnapshotTests','ClockLossSnapshotTests','HandoverPackageOverrideTests','MonitorRecoverySnapshotTests','USBSupplySnapshotTests','ClockScreenSnapshotTests','DecouplingSnapshotTests','HostSpectrumRateBindingTests','HostChargeOwnershipTests','RevisionCommandSnapshotTests')]],
    'inventory_and_converter_binding': ['test_baseline_envelope.CommonEnvelopeMigrationTests',
        'test_design_definition.CampaignSnapshotPropagationTests',
        'test_wifi_client_exchange.SharedDesignTests'],
    'stream_control_and_qualification': ['test_resource_configuration', 'test_direct_stream', 'test_live_control',
                                          'test_receive_qualification','test_usb_selected_timing.ResolvedUSBClockTests'],
    'timing_and_rf_budgets': ['test_timing_services', 'test_rf_quality_budget',
                             'test_rf_air_timing', 'test_video_alignment'],
}


def iteration_main():
    if not __debug__:
        raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic();budget=30.
    output=P/'evidence/architecture-iteration.json'
    sources=(list((P/'system_model').rglob('*.py'))+
             list((P/'verification').rglob('*.py'))+
             [P/'spec/contract.json',P/'spec/analog-architecture.json'])
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}
    report=dict(status='running',scope=__doc__.strip(),design_provenance=load_design().provenance(),
        wall_budget_s=budget,checks=[],source_sha256=hashes,full_chip_closure=False,
        physical_qualification=False,omitted=[
            'Complete unit-test discovery and standalone simulation campaigns.',
            'Joined loaded-clock, packet, converter feedback and recovery waveforms.',
            'Standards interoperability, transistor, package and layout qualification.'])
    def save():
        output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for name,modules in CHECKS.items():
            remaining=budget-(time.monotonic()-start)
            if remaining<=0:
                raise TimeoutError('Architecture iteration exceeded 30-second budget')
            before=time.monotonic()
            result=subprocess.run([sys.executable,'-m','unittest',*modules],
                cwd=P/'verification',
                env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),
                text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                timeout=remaining)
            row=dict(name=name,modules=modules,elapsed_s=time.monotonic()-before,
                     returncode=result.returncode,diagnostic=result.stdout[-6000:])
            report['checks'].append(row);save()
            if result.returncode:
                raise RuntimeError(name+' failed: '+result.stdout[-2000:])
            print(name,'passed',round(row['elapsed_s'],3),'s',flush=True)
        if any(hashlib.sha256((P/f).read_bytes()).hexdigest()!=h for f,h in hashes.items()):
            raise RuntimeError('Sources changed during regression')
        report['status']='passed'
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:
        report['elapsed_s']=time.monotonic()-start;save()


if __name__=='__main__':
    import argparse
    argparse.ArgumentParser(description=__doc__).parse_args()
    iteration_main()
