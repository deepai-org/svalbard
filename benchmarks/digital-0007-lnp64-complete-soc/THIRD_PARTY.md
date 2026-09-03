# Third-party material

The frozen LNP64 ISA is copied from commit `f4fb5856d` under
Community-Spec-1.0. The emulator, conformance report, assembly corpus, and test
images are copied or built from that commit under Apache-2.0. Full texts are in
`LICENSES/`.

Every required LNP64 artifact is included in this bundle and hash-locked. The
source commit records provenance; no external LNP64 checkout is required.

No LNP64 RTL is included.

The sealed verifier uses the public GPL-3.0-or-later `wyvernSemi/pcievhost`
revision `b82b2ff3a047f742354c9607dea34b9b97bf108c` and its public GPL-3.0-only
`wyvernSemi/vproc` dependency revision under the same license
`ae80e5b5cb43d4e9f82f9d45aa3b614e053f9df4`. They are fetched from
`https://github.com/wyvernSemi/pcievhost.git` and
`https://github.com/wyvernSemi/vproc.git` while building the verifier image;
neither is required by the submitted design.
