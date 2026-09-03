FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates make python3 iverilog verilator ngspice \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/input_files
COPY input_files/ /app/input_files/
RUN chmod -R a-w /app/input_files

CMD ["bash"]
