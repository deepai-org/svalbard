FROM docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
USER root
ENTRYPOINT []
RUN groupadd --gid 1000 agent && useradd --uid 1000 --gid agent --create-home --shell /bin/bash agent \
 && python3 -m venv /opt/rewardkit \
 && /opt/rewardkit/bin/pip install --no-cache-dir "harbor-rewardkit==0.1.7"
ENV PATH="/opt/rewardkit/bin:/foss/tools/bin:/foss/tools/klayout:${PATH}"
ENV LD_LIBRARY_PATH="/foss/tools/iverilog/lib:/foss/tools/klayout:/foss/tools/ngspice/lib"
COPY input_files/ /app/input_files/
RUN chown -R root:root /app/input_files && chmod -R a-w /app/input_files \
 && mkdir -p /app/output && chown -R agent:agent /app/output
WORKDIR /app
CMD ["/bin/bash"]
