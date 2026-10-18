import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from design import PROJECT, resolve
from circuits import wired_transmit
from extract_audit import extracted_graph,export_extracted


class DesignBoundary(unittest.TestCase):
    def setUp(self):
        self.architecture = json.loads((PROJECT / 'spec/analog-architecture.json').read_text())
        self.contract = json.loads((PROJECT / 'spec/contract.json').read_text())

    def test_electrical_inventory_does_not_turn_coverage_into_acceptance(self):
        from run_first_pass import electrical_findings
        with TemporaryDirectory() as directory:
            root=Path(directory)
            # Even a complete transient with all state names has no safety verdict.
            data={'transient_complete':True,'states':{s:{} for s in
                ('active','disabled','reset','unpowered','brownout','reconfiguration')}}
            path=root/'wired-receive-usb-screen.json'
            path.write_text(json.dumps(data))
            first=electrical_findings(root)
            self.assertEqual(first['rf_transmit']['status'],'missing_screen')
            self.assertEqual(first['wired_receive_usb']['status'],'incomplete_electrical_acceptance')
            self.assertEqual(first['wired_receive_usb']['recorded_limit_checks'],[])
            budget=resolve()['families']['wired_receive_usb']['electrical_parameters']['capacitance_f_per_leg']
            data['loading']={'serial_bypass':{
                'odd_mode_effective_capacitance_f_per_leg':[budget*1.1,budget*.9]}}
            path.write_text(json.dumps(data))
            second=electrical_findings(root)['wired_receive_usb']
            self.assertEqual(second['recorded_limit_checks'][0]['status'],'recorded_limit_miss')
            self.assertIn('core_terminal_voltage_current_duration_limits',second['unresolved'])

    def test_current_bus_width_policy_rejects_typoes_and_unbuildable_banks(self):
        from layout import trunk_geometry
        spec=json.loads((PROJECT/'spec/schematic-implementation.json').read_text())
        selected=spec['io_pad_first_pass']['layout_parameters']['wired_transmit']['trunk_width_overrides_um']
        meta=json.loads((PROJECT/'analog/pads/generated/wired-transmit-layout.json').read_text())
        nets=set(meta['net_track_x_um'])
        tracks,widths=trunk_geometry(nets,width_overrides_um=selected)
        self.assertTrue(all(widths[n]==w for n,w in selected.items()))
        ordered=sorted(nets,key=tracks.get)
        self.assertTrue(all(tracks[b]-widths[b]/2>tracks[a]+widths[a]/2 for a,b in zip(ordered,ordered[1:])))
        with self.assertRaises(ValueError):trunk_geometry(nets,width_overrides_um={'TERM_P_typo':8.})
        with self.assertRaises(ValueError):trunk_geometry(nets,width_overrides_um={n:12. for n in nets})

    def test_tmds_power_uses_its_branch_owner_and_override(self):
        from run_first_pass import tx_macro_power_budget
        with TemporaryDirectory() as directory:
            root=Path(directory)
            data={'macro_supply_currents':{'modes':{'TMDS':{
                'mean_currents_a':{'Xpad':0,'XBUF':0,'XCTL':0,'XDRIVE_MAIN_P':0,'XDRIVE_TMDS_P':.030},
                'mean_total_vdd_draw_a':.030}}}}
            (root/'wired-transmit-screen.json').write_text(json.dumps(data))
            result=tx_macro_power_budget(root)['modes']['TMDS']['blocks']
            override=self.architecture['resource_policy']['branch_current_overrides_ma']['wired_tmds']
            self.assertEqual(result['tmds']['wired_mode_allocation_ma'],override['tmds'])
            self.assertEqual(result['wiredtx']['wired_mode_allocation_ma'],override['wiredtx'])
            self.assertTrue(result['tmds']['measured_macro_alone_exceeds_allocation'])
            self.assertFalse(result['wiredtx']['measured_macro_alone_exceeds_allocation'])

    def test_ac_coupled_peer_preserves_chip_and_retains_charge(self):
        from transmit_fixture import build
        with TemporaryDirectory() as directory:
            root=Path(directory)
            direct=root/'direct.spice';ac=root/'ac.spice'
            build(direct,Path('/unused/pdk'))
            manifest=build(ac,Path('/unused/pdk'),external_network='ac_coupled')
            remove=lambda text:'\n'.join(line for line in text.splitlines()
                if not line.startswith(('RDIFF_LOAD ','RPEER_','VPEER ','CCOUPLE_')))
            self.assertEqual(remove(direct.read_text()),remove(ac.read_text()))
            caps=[line for line in ac.read_text().splitlines() if line.startswith('CCOUPLE_')]
            self.assertEqual(len(caps),2)
            for leg,line in zip(('P','N'),caps):
                self.assertEqual(line.split()[1:3],['BOARD_'+leg,'RECEIVER_'+leg])
                self.assertNotIn('IC=',line.upper())
                self.assertEqual(float(line.split()[3]),manifest['external_network']['coupling_f_per_leg'])
            self.assertEqual(manifest['external_network']['peer_power'],'independent_continuously_present')

    def test_external_pullup_changes_only_retained_board_network(self):
        from transmit_fixture import build
        with TemporaryDirectory() as directory:
            root=Path(directory);pdk=Path('/unused/pdk')
            first=root/'differential.spice';second=root/'pullup.spice'
            build(first,pdk);manifest=build(second,pdk,external_network='split_pullup')
            remove=lambda text:'\n'.join(line for line in text.splitlines()
                if not line.startswith(('RDIFF_LOAD ','RPEER_','VPEER ')))
            self.assertEqual(remove(first.read_text()),remove(second.read_text()))
            peer=next(line for line in second.read_text().splitlines() if line.startswith('VPEER '))
            self.assertNotIn('VDD',peer)
            self.assertNotIn('PWL',peer)
            self.assertEqual(manifest['external_network']['peer_power'],'independent_continuously_present')
            self.assertEqual(manifest['external_network']['resistance_ohm_per_leg'],
                self.architecture['blocks']['tmds']['parameters']['external_pullup_ohm_per_leg'])

    def test_macro_supply_observer_preserves_interfaces_and_excludes_gaps(self):
        import numpy as np
        from transmit_sequence_connected import instrument_macro_supplies,macro_supply_summary
        deck='.subckt load IN VDD VSS\nRLOAD VDD VSS 1000\n.ends load\nXLOAD DATA VDD VSS load\n'
        measured,probes=instrument_macro_supplies(deck)
        self.assertIn('RLOAD VDD VSS 1000',measured)
        self.assertIn('XLOAD DATA MEASURE_XLOAD_VDD VSS load',measured)
        self.assertIn('VSUPPLY_XLOAD VDD MEASURE_XLOAD_VDD 0',measured)
        x=np.zeros((4,13));x[:,0]=np.array([0,1,10,11])*1e-9;x[:,6]=-.01
        currents=np.column_stack((x[:,0],np.array([1,3,5,7])*1e-3))
        result=macro_supply_summary(x,currents,probes,{'active':[[0,1],[10,11]]})['modes']['active']
        self.assertAlmostEqual(result['mean_currents_a']['XLOAD'],.004)
        self.assertAlmostEqual(result['mean_other_top_level_vdd_draw_a'],.006)
        self.assertAlmostEqual(result['observed_duration_s'],2e-9)
        with self.assertRaisesRegex(ValueError,'supply domain'):
            instrument_macro_supplies(deck.replace('XLOAD DATA VDD','XLOAD DATA OTHER_RAIL'))

    def test_ideal_driver_energy_separates_delivery_from_absorption(self):
        import numpy as np
        from transmit_sequence_connected import ideal_drive_sources,ideal_drive_summary
        deck='.subckt internal A B\nBHIDDEN A B V=1\n.ends internal\nBOUT OUT VSS V=1\n'
        sources=ideal_drive_sources(deck)
        self.assertEqual([v['name'] for v in sources],['BOUT'])
        # A source delivering one watt then absorbing one watt has zero net
        # energy; the positive burden must not disappear by cancellation.
        data=np.array([[0,1,-1],[1,1,-1],[2,1,1],[3,1,1]],dtype=float)
        result=ideal_drive_summary(data,sources)['sources']['BOUT']
        self.assertEqual(result['net_delivered_energy_j'],0)
        self.assertEqual(result['delivered_energy_j'],1.5)
        self.assertEqual(result['absorbed_energy_j'],1.5)
        self.assertEqual(result['peak_absolute_current_a'],1)

    def test_brownout_reports_pad_exposure_despite_logical_disable(self):
        import numpy as np
        from transmit_sequence_connected import brownout_summary
        x=np.zeros((4,13))
        x[:,0]=np.arange(4)*1e-9
        x[:,12]=[3.3,1.5,1.5,0]
        x[:,10:12]=[[1.6,1.6],[-.7,-.2],[-.4,-.1],[-.9,-.9]]
        x[1:3,5]=.4
        result=brownout_summary(x,2.5)
        self.assertEqual(result['samples'],2)
        self.assertAlmostEqual(result['duration_s'],2e-9)
        self.assertEqual(result['traffic_ready_max_v'],0)
        self.assertEqual(result['termination_enable_max_v'],.4)
        self.assertEqual(result['pad_below_local_ground_max_v'],.7)
        self.assertEqual(result['pad_above_local_supply_max_v'],0)
        x[:,12]=3.3
        self.assertEqual(brownout_summary(x,2.5)['status'],'not_reached')

    def test_coverage_cannot_omit_shared_brownout_requirement(self):
        from run_first_pass import integrated_model_inventory
        with TemporaryDirectory() as directory:
            root=Path(directory)
            stem='wired-transmit'
            (root/(stem+'-extracted-c.spice')).write_text('* fixture model\n')
            (root/(stem+'.gds')).write_bytes(b'fixture only')
            (root/(stem+'-layout.json')).write_text('{}')
            screen=root/(stem+'-screen.json')
            states={name:{} for name in ('active_main','disabled','reset','unpowered','reconfiguration')}
            screen.write_text(json.dumps(dict(states=states,transient_complete=True)))
            item=integrated_model_inventory(root)['wired_transmit']
            self.assertEqual(item['missing_required_states'],['brownout'])
            self.assertFalse(item['all_required_state_names_present'])
            states['brownout']={}
            screen.write_text(json.dumps(dict(states=states,transient_complete=True)))
            item=integrated_model_inventory(root)['wired_transmit']
            self.assertTrue(item['all_required_state_names_present'])
            # State names alone still cannot establish model or layout acceptance.
            self.assertFalse(item['model_bytes_match_recorded_screen_input'])
            self.assertFalse(item['exported_layout_device_graph_matches_current_model'])

    def test_protection_audit_detects_diode_polarity_and_mim_terminal_faults(self):
        from protection_device_audit import supplemental_graphs
        records=['scale 1000 1 0.5',
            'device ndiode diode_nd2ps_06v0 0 0 1 1 a=900000 p=10360 "VSS" "PAD_P" 0 0 "VSS" 0 0',
            'device csubckt cap_mim_2f0_m4m5_noshield 0 0 1 1 l=6320 w=6320 "None" "RAIL" 0 0 "VSS" 0 0']
        correct='D0 VSS PAD_P diode_nd2ps_06v0 area=22.5p pj=51.8u\nX0 RAIL VSS cap_mim_2f0_m4m5_noshield c_width=31.6u c_length=31.6u\n'
        with TemporaryDirectory() as directory:
            model=Path(directory)/'model.spice';model.write_text(correct)
            actual,simulated,_=supplemental_graphs(records,model)
            self.assertEqual(actual,simulated)
            for altered in (correct.replace('D0 VSS PAD_P','D0 PAD_P VSS'),
                            correct.replace('X0 RAIL VSS','X0 PAD_P VSS')):
                model.write_text(altered)
                actual,simulated,_=supplemental_graphs(records,model)
                self.assertNotEqual(actual,simulated)

    def test_physical_alias_rejected(self):
        sites = self.contract['assembly_policy']['candidate_signal_sites']
        sites['RF_RX_P'] = sites['RF_TX_P']
        with self.assertRaisesRegex(ValueError, 'Multiple signals'):
            resolve(self.architecture, self.contract)

    def test_missing_bond_site_rejected(self):
        self.contract['assembly_policy']['candidate_signal_sites']['REF_IN'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'no provider site'):
            resolve(self.architecture, self.contract)

    def test_changed_architecture_propagates(self):
        self.architecture['blocks']['rfpad']['parameters']['capacitance_f_per_leg'] = .8e-12
        family = resolve(self.architecture, self.contract)['families']['rf_receive']
        self.assertEqual(family['electrical_parameters']['capacitance_f_per_leg'], .8e-12)
        self.assertEqual([p['side'] for p in family['pads']], ['west', 'west'])

    def test_extractor_audit_preserves_wrong_body(self):
        # The independent audit must not silently repair an extracted body
        # terminal from the intended schematic or assume every NMOS is grounded.
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.ext'
            path.write_text('device msubckt nfet_06v0 0 0 1 1 l=140 w=1600 "BAD_BODY" "G" 1 0 "S" 1 0,0 "D" 1 0,0\n')
            graph=extracted_graph(path)
            record=next(iter(graph))
            self.assertEqual(record[4],'BAD_BODY')
            self.assertEqual(record[-2:],(8.,.7))

    def test_fractional_device_count_rejected(self):
        with self.assertRaises(ValueError):
            wired_transmit(steering_units=2.5)

    def test_physical_export_units_and_body_are_from_extraction(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'physical.ext';output=root/'physical.spice'
            source.write_text('scale 1000 1 0.5\nport "P" 1 0 0 1 1 m1\n'
                'port "VSS" 2 0 0 1 1 m1\nsubstrate "VSS" 0 0 0 0 m1\n'
                'node "P" 0 1000 0 0 m1\ncap "P" "VSS" 2000\n'
                'equiv "D_ALIAS" "P"\n'
                'device msubckt nfet_06v0 0 0 1 1 l=140 w=1600 "BAD_BODY" "G" 1 0 "S" 1 40000,400 "D_ALIAS" 1 80000,600\n')
            export_extracted(source,output)
            text=output.read_text()
            self.assertIn('X0 P G S BAD_BODY nfet_06v0 w=8u l=0.7u ad=2p as=1p pd=3u ps=2u',text)
            self.assertIn('P VSS 1e-15',text)
            self.assertIn('P VSS 2e-15',text)
            export_extracted(source,output,capacitance=False)
            self.assertFalse(any(s.startswith('C') for s in output.read_text().splitlines()))

    def test_rf_route_preserves_protection_and_capacitance(self):
        from rf_route import augment
        generated=Path(__file__).parent/'generated'
        for family in ('rf_receive','rf_transmit'):
            stem=family.replace('_','-')
            original=(generated/(stem+'-extracted-c.spice')).read_text()
            route=generated/(stem+'-route-resistance.json')
            # The overlay may change only the wrapper, never the extracted
            # protection graph, nonlinear wells or physical capacitances.
            physical=original[original.index('.subckt pad_flat '):]
            for corner in ('nominal','high_resistance','low_resistance'):
                model,evidence=augment(original,family,route,'core',corner)
                self.assertEqual(model[model.index('.subckt pad_flat '):],physical)
                self.assertIn('XPHYSICAL LOCAL_PAD_RETURN ESD_RAIL COREPAD_P COREPAD_N pad_flat',model)
                for leg in ('P','N'):
                    line=next(l.split() for l in model.splitlines() if l.startswith('RBOND_'+leg+' '))
                    self.assertEqual(line[1:3],['PAD_'+leg,'COREPAD_'+leg])
                    self.assertAlmostEqual(float(line[3]),evidence['legs'][leg]['corners'][corner]['metal_only_ohm'])
                self.assertIn('RRETURN LOCAL_PAD_RETURN VSS ',model)
            with self.assertRaisesRegex(ValueError,'another pad extraction'):
                augment(original+'\n* changed extraction\n',family,route,'core')
            with self.assertRaisesRegex(ValueError,'core endpoint'):
                augment(original,family,route,'bond')

    def test_wired_route_preserves_devices_and_separates_protection(self):
        import re
        from wired_tx_route import augment
        original=(PROJECT/'analog/pads/generated/wired-transmit-extracted-c.spice').read_text()
        branches={leg:dict(common_bond_lead_ohm=8,core_branch_ohm=2,
                           protection_branch_ohm=7) for leg in ('P','N')}
        routed,counts=augment(original,branches)
        self.assertEqual(len([x for x in routed.splitlines() if x.startswith('RROUTE_')]),6)
        restored=[]
        for line in routed.splitlines():
            if line.startswith('RROUTE_'):continue
            for leg in ('P','N'):
                line=line.replace('ROUTE_PRIMARY_'+leg,'PAD_'+leg).replace('ROUTE_CORE_'+leg,'PAD_'+leg)
            restored.append(line.split())
        joined=re.sub(r'\n\s*\+\s*',' ',original)
        self.assertEqual(restored,[line.split() for line in joined.splitlines()])
        for leg in ('P','N'):
            self.assertEqual(counts[leg]['protection_diodes'],8)
        for line in routed.splitlines():
            if line.startswith('D') and 'ROUTE_' in line:
                self.assertIn('ROUTE_PRIMARY_',line)
            if line.startswith('X') and 'ROUTE_' in line:
                self.assertIn('ROUTE_CORE_',line)
        with self.assertRaises(ValueError):
            augment(original.replace('D0 VSS PAD_N','D0 VSS OTHER'),branches)

    def test_physical_export_rejects_unhandled_device(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'physical.ext'
            source.write_text('scale 1000 1 0.5\nsubstrate "VSS" 0 0 0 0 m1\ndevice unsupported 0\n')
            with self.assertRaisesRegex(ValueError,'Unsupported device'):
                export_extracted(source,root/'physical.spice')


if __name__ == '__main__':
    unittest.main()
