# Sourced by the signoff scripts. Paths of the tool image and the two PDK deck trees.
SO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$SO/../../../.." && pwd)
RUN=${SIGNOFF_RUN:-$ROOT/scratch/integration/signoff-run}
# Project KLayout 0.30.9 image (aarch64); its /foss/pdks/gf180mcuD is the project PDK (open_pdks f6eeac7).
KL_IMAGE=${KL_IMAGE:-sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305}
# Shuttle PDK (open_pdks 792ef67): a directory with drc/ (KLayout deck) and scripts/ (fill). Default: the copy made by the
# sign-off gap check; precheck/NOTES.md says where a complete tree lives once it has been fetched.
PDK_LIVE=${PDK_LIVE:-$ROOT/scratch/integration/signoff-gap/precheck/pdk_792ef67}
PDK_PROJ=${PDK_PROJ:-$ROOT/scratch/integration/signoff-gap/precheck/pdk_f6eeac7}
mkdir -p "$RUN"
