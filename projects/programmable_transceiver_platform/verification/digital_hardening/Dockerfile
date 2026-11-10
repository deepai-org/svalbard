FROM hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
USER root
COPY prepare_toolchain.py /opt/svalbard/prepare_toolchain.py
RUN python3 /opt/svalbard/prepare_toolchain.py
