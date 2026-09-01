# Schemas

Machine-readable interface and contract schemas live here. Schemas define
structure; project-owned specifications and values remain with their projects.

Current schema:

- [`pcie_gen1_endpoint_spec.schema.json`](pcie_gen1_endpoint_spec.schema.json)
  validates the PCIe endpoint specification shape.

Run `python3 scripts/validate.py structure` after changing a schema or a file it
validates.
