"""Shared pipelined RX testbench and mutation checks for mask/rank/prefix/pipe RTL."""

def run_check(variant):
    if variant not in ("mask", "rank", "prefix", "pipe"):
        raise ValueError("Unknown RX implementation")
    import pathlib, sys, subprocess
    sys.path.insert(0, '/src/verification')
    from block_rx_vectors import receiver_vectors
    out = pathlib.Path('/out')
    rows = receiver_vectors()
    (out / 'vectors.txt').write_text(''.join(rows))
    n = len(rows)
    (out / 'test.sv').write_text('''module tb;
reg clk=0,rst_n,mode8,in_valid,wire_ready,iq_ready,command_ready;reg[79:0]words;
wire[79:0]wire_words,iq_words;wire[3:0]wire_count,iq_count;wire wire_valid,iq_valid,command_valid,fault;wire[3:0]opcode;wire[7:0]argument;
integer f,r,n;reg reset;reg[79:0]ew,eq;reg[3:0]cw,cq,op;reg wv,qv,cv,ef;reg[7:0]arg;
pt_block_rx_mask dut(.*);
initial begin f=$fopen("/out/vectors.txt","r");n=0;
while(!$feof(f))begin
r=$fscanf(f,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\\n",reset,mode8,in_valid,wire_ready,iq_ready,command_ready,words,ew,eq,cw,cq,wv,qv,cv,op,arg,ef);
if(r!=17)$fatal(1,"vector");rst_n=!reset;#1;
if({wire_words,iq_words,wire_count,iq_count,wire_valid,iq_valid,command_valid,opcode,argument}!=={ew,eq,cw,cq,wv,qv,cv,op,arg})$fatal(1,"RX effects %0d",n);
clk=1;#1;if(fault!==ef)$fatal(1,"RX fault %0d",n);clk=0;#1;n=n+1;end
$display("PASS RX cycles=%0d",n);$finish;end endmodule
'''.replace('_mask', '_' + variant))
    rtl = ['/src/rtl/' + f for f in ('pt_lane_compact.sv', ('pt_block_route.sv' if variant=='pipe' else 'pt_block_route_mask.sv'.replace('_mask', '_' + variant)), 'pt_block_header.sv', 'pt_block_rx_mask.sv'.replace('_mask', '_' + variant))]

    def run(files, name):
        exe = str(out / name)
        subprocess.run(['iverilog', '-g2012', '-I/src/rtl', '-s', 'tb', '-o', exe, *files, str(out / 'test.sv')], check=True)
        return subprocess.run(['vvp', exe], capture_output=True, text=True)
    r = run(rtl, 'test')
    assert r.returncode == 0, r.stdout + r.stderr
    assert f'cycles={n}' in r.stdout
    print(r.stdout)
    s = pathlib.Path(rtl[-1]).read_text()
    assert s.count('allowed&&capacity') == 1
    (out / 'bad.sv').write_text(s.replace('allowed&&capacity', 'allowed'))
    r = run(rtl[:-1] + [str(out / 'bad.sv')], 'bad')
    assert r.returncode != 0 and 'RX effects' in r.stdout
    print('PASS capacity-bypass mutation rejected')
    assert s.count('&&(beat!=0||command_ready)') == 1
    (out / 'bad_command.sv').write_text(s.replace('&&(beat!=0||command_ready)', ''))
    r = run(rtl[:-1] + [str(out / 'bad_command.sv')], 'bad_command')
    assert r.returncode != 0 and 'RX effects' in r.stdout
    print('PASS command-readiness bypass rejected')
    assert s.count('!fault&&stage_valid&&') == 1
    (out / 'bad_stage.sv').write_text(s.replace('!fault&&stage_valid&&', '!fault&&in_valid&&'))
    r = run(rtl[:-1] + [str(out / 'bad_stage.sv')], 'bad_stage')
    assert r.returncode != 0 and ('RX effects' in r.stdout or 'RX fault' in r.stdout)
    print('PASS live-valid instead of stored-valid mutation rejected')
    if variant!='pipe':
        assert s.count('mask_for(mode8,input_beat,') == 2
        (out / 'bad_mask.sv').write_text(s.replace('mask_for(mode8,input_beat,', "mask_for(mode8,3'(input_beat+1),"))
        r = run(rtl[:-1] + [str(out / 'bad_mask.sv')], 'bad_mask')
        assert r.returncode != 0 and 'RX effects' in r.stdout
        print('PASS next-beat mask mutation rejected')
    subprocess.run(['yosys', '-Q', '-T', '-p', 'read_verilog -sv -I/src/rtl ' + ' '.join(rtl) + '; synth -top pt_block_rx_mask; check -assert'.replace('_mask', '_' + variant)], stdout=(out / 'synthesis.log').open('w'), check=True)
