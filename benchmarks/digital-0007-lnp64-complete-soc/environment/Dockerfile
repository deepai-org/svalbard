FROM docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3

USER root
ENTRYPOINT []

RUN groupadd --gid 1000 agent \
 && useradd --uid 1000 --gid agent --create-home --shell /bin/bash agent

RUN python3 -m venv /opt/rewardkit \
 && /opt/rewardkit/bin/pip install --no-cache-dir "harbor-rewardkit==0.1.7"
ENV PATH="/opt/rewardkit/bin:${PATH}"
ENV LITELLM_LOCAL_MODEL_COST_MAP=True

# Public, source-available PCIe root-complex verifier. Both revisions are
# immutable and rechecked by the adapter before use.
RUN git clone https://github.com/wyvernSemi/vproc.git /opt/vproc \
 && git -C /opt/vproc checkout --detach ae80e5b5cb43d4e9f82f9d45aa3b614e053f9df4 \
 && git clone https://github.com/wyvernSemi/pcievhost.git /opt/pcievhost \
 && git -C /opt/pcievhost checkout --detach b82b2ff3a047f742354c9607dea34b9b97bf108c \
 && sed -e "s/0x/32'h/" -e 's/#/`/' -e 's/DEFINES/AUTO GENERATED. DO NOT EDIT!/' \
      /opt/pcievhost/src/pcie_vhost_map.h \
      > /opt/pcievhost/verilog/headers/pcie_vhost_map.v \
 && printf '%s\n' ae80e5b5cb43d4e9f82f9d45aa3b614e053f9df4 > /opt/vproc/.benchmark-revision \
 && printf '%s\n' b82b2ff3a047f742354c9607dea34b9b97bf108c > /opt/pcievhost/.benchmark-revision \
 && make -C /opt/pcievhost/lib -f makefile.sysvlog ARCHFLAG= VPROC_TOP=/opt/vproc \
 && rm -rf /opt/vproc/.git /opt/pcievhost/.git

WORKDIR /app/input_files
COPY input_files/ /app/input_files/
RUN xz -dk /app/input_files/oracle/lnp64-emulator-aarch64.xz \
 && chmod +x /app/input_files/oracle/lnp64-emulator-aarch64 \
 && chown -R root:root /app/input_files \
 && chmod -R a-w /app/input_files \
 && mkdir -p /app/output \
 && chown -R agent:agent /app/output

WORKDIR /app

CMD ["/bin/bash"]
