# Oracle provenance

The dependency-free reference model in
`tests/reference/codec_8b10b_oracle.py` was adapted from these primary upstream
implementations and cross-checked against their known-answer tests:

- LiteX [`litex/soc/cores/code_8b10b.py`](https://github.com/enjoy-digital/litex/blob/86f29574801fe861ee598e8f179a78dfa381c70a/litex/soc/cores/code_8b10b.py)
  and [`test/cores/test_code_8b10b.py`](https://github.com/enjoy-digital/litex/blob/86f29574801fe861ee598e8f179a78dfa381c70a/test/cores/test_code_8b10b.py), commit
  `86f29574801fe861ee598e8f179a78dfa381c70a`, BSD-2-Clause.
- LiteEth [`liteeth/phy/pcs_1000basex.py`](https://github.com/enjoy-digital/liteeth/blob/8c9150ff121cb3148d8ea26ce3b1c5200479848d/liteeth/phy/pcs_1000basex.py)
  and [`test/test_pcs_1000basex.py`](https://github.com/enjoy-digital/liteeth/blob/8c9150ff121cb3148d8ea26ce3b1c5200479848d/test/test_pcs_1000basex.py), commit
  `8c9150ff121cb3148d8ea26ce3b1c5200479848d`, BSD-2-Clause.

LiteX copyright: 2016–2017 Sebastien Bourdeauducq and 2019–2020 Florent
Kermarrec for the referenced codec file.  LiteEth PCS copyright: 2018–2020
Sebastien Bourdeauducq and 2024 Florent Kermarrec.  The full BSD-2-Clause text
is reproduced below.

```text
Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
