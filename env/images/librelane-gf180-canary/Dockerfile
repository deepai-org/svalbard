# syntax=docker.io/docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3 AS pdk

FROM ghcr.io/librelane/librelane@sha256:d8f3de6a4b0563d8632ce317a84fdc5a88f3cad1d4409cdef5c8e983f1505012

LABEL org.opencontainers.image.title="SVALBARD LibreLane GF180 core canary"
LABEL org.opencontainers.image.description="Public GF180 snapshot plus a narrow LibreLane 3 compatibility overlay; not a fabrication-qualified PDK"
LABEL org.opencontainers.image.source="https://github.com/deepai-org/svalbard"
LABEL org.svalbard.scope="generic-core-canary-only"
LABEL org.svalbard.pdk.ciel-revision="f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7"

COPY --from=pdk /foss/pdks/ciel/gf180mcu/versions/f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7/gf180mcuD /pdk/gf180mcuD
COPY overlay_pdk.py /tmp/overlay_pdk.py
RUN python3 /tmp/overlay_pdk.py && rm /tmp/overlay_pdk.py

ENV PDK_ROOT=/pdk
