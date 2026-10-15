function he_reference_vectors(output_dir)
% Optional external reference generation, NOT executed/qualified in this repo.
% Requires MATLAB WLAN Toolbox. No MATLAB dependency in the chip model.
% APIs: mathworks.com/help/wlan/ref/wlanhesuconfig.html,
% wlanhetbconfig.html and wlanwaveformgenerator.html.
% Export full PHY waveforms and random PSDUs, not an association/MAC exchange.
arguments
    output_dir (1,:) char
end
if ~exist(output_dir,'dir'), mkdir(output_dir); end
rng(842,'twister');
for mcs=0:7
    cfg=wlanHESUConfig('ChannelBandwidth','CBW20','MCS',mcs, ...
        'NumTransmitAntennas',1,'NumSpaceTimeStreams',1, ...
        'ChannelCoding','BCC','APEPLength',256);
    export_one(cfg,sprintf('he_su_mcs%d',mcs),output_dir);
end
% Lower/center/upper small RUs exercise analog response across the whole band.
allocations=[26 1;26 5;26 9;52 1;52 4;106 1;106 2;242 1];
for k=1:size(allocations,1)
    for mcs=[0 7]
        cfg=wlanHETBConfig('ChannelBandwidth','CBW20', ...
            'RUSize',allocations(k,1),'RUIndex',allocations(k,2), ...
            'MCS',mcs,'NumTransmitAntennas',1,'NumSpaceTimeStreams',1, ...
            'ChannelCoding','BCC');
        export_one(cfg,sprintf('he_tb_ru%d_index%d_mcs%d', ...
            allocations(k,1),allocations(k,2),mcs),output_dir);
    end
end
end

function export_one(cfg,name,output_dir)
psdu=randi([0 1],8*wlanPSDULength(cfg),1,'int8');
waveform=wlanWaveformGenerator(psdu,cfg,'OversamplingFactor',4);
sample_hz=4*wlanSampleRate(cfg);
configuration=struct(cfg);
generator_release=version;
scope='Reference PHY vector; random PSDU; not MAC interoperability evidence';
save(fullfile(output_dir,[name '.mat']),'waveform','sample_hz','psdu', ...
    'configuration','generator_release','scope','-v7');
end
