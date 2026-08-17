# syntax=docker.io/docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM docker.io/library/rust@sha256:ed6e6a4aa37e6f71bf7329736fd2b3cf29c8b82b23072f8255708b54f9c87944 AS build
ARG SOURCE_DATE_EPOCH=1718807854
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH} \
    CARGO_TARGET_DIR=/opt/cargo-target
ADD --checksum=sha256:a50ba101318b96250a8f08faf4243eaf35ceecf9a8eaf2363f72c36c951c4d8a \
    https://static.crates.io/crates/quaigh/quaigh-0.0.6.crate /tmp/quaigh-0.0.6.crate
RUN mkdir /opt/quaigh-source \
    && tar -xzf /tmp/quaigh-0.0.6.crate --strip-components=1 -C /opt/quaigh-source \
    && cargo install --path /opt/quaigh-source --locked --root /opt/quaigh \
    && strip /opt/quaigh/bin/quaigh \
    && test "$(/opt/quaigh/bin/quaigh --version)" = "quaigh 0.0.6"

FROM docker.io/library/debian@sha256:273c4267223752a058c730533a8b9a5e1c44b213674f258b76fd1135fc87fdd2
LABEL org.opencontainers.image.title="SVALBARD Quaigh ATPG"
LABEL org.opencontainers.image.source="https://github.com/Coloquinte/quaigh"
LABEL org.opencontainers.image.version="0.0.6"
LABEL org.opencontainers.image.revision="192bfb9edb330fb726dca4b9746fb3fb96524aba"
LABEL org.opencontainers.image.licenses="MIT OR Apache-2.0"
COPY --from=build /opt/quaigh/bin/quaigh /usr/local/bin/quaigh
USER 65532:65532
ENTRYPOINT ["/usr/local/bin/quaigh"]
