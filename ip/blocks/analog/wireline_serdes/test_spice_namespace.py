#!/usr/bin/env python3
import unittest
from pathlib import Path
import tempfile

from spice_namespace import NamespaceError, namespace_source, resolve_includes


SOURCE = """* cp_inv in a comment must remain unchanged
.subckt cp_inv A Y VDD VSS params: M=1
XDEV A Y primitive params: M={M}
.ends cp_inv
.subckt public_top A Y VDD VSS
X0 A N VDD VSS cp_inv
X1 N Y VDD VSS
+ cp_inv M=2
.ends public_top
"""


class SpiceNamespaceTest(unittest.TestCase):
    def test_internal_definition_and_calls_are_namespaced(self) -> None:
        result, mapping = namespace_source(SOURCE, "leaf_a", {"public_top"})
        self.assertEqual(mapping["cp_inv"], "leaf_a__cp_inv")
        self.assertEqual(mapping["public_top"], "public_top")
        self.assertIn(".subckt leaf_a__cp_inv", result)
        self.assertIn(".ends leaf_a__cp_inv", result)
        self.assertIn("X0 A N VDD VSS leaf_a__cp_inv", result)
        self.assertIn("+ leaf_a__cp_inv M=2", result)
        self.assertIn("* cp_inv in a comment", result)

    def test_terminal_named_like_subckt_is_not_rewritten(self) -> None:
        source = ".subckt inv A Y\n.ends inv\nX0 inv Y inv\n"
        result, _ = namespace_source(source, "p")
        self.assertIn("X0 inv Y p__inv", result)

    def test_rejects_unresolved_include(self) -> None:
        with self.assertRaisesRegex(NamespaceError, "resolve .include"):
            namespace_source(".include child.spice\n", "p")

    def test_rejects_duplicate_case_insensitive_definition(self) -> None:
        source = ".subckt INV A Y\n.ends INV\n.subckt inv A Y\n.ends inv\n"
        with self.assertRaisesRegex(NamespaceError, "duplicate"):
            namespace_source(source, "p")

    def test_requires_public_identity_to_exist(self) -> None:
        with self.assertRaisesRegex(NamespaceError, "public subcircuit"):
            namespace_source(SOURCE, "p", {"missing"})

    def test_resolves_relative_and_virtual_includes_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "leaf.spice").write_text(".subckt leaf A Y\n.ends leaf\n")
            (root / "middle.spice").write_text(
                ".include leaf.spice\n.include /src/leaf.spice\n")
            (root / "top.spice").write_text(".include middle.spice\n")
            result = resolve_includes(root / "top.spice", root)
        self.assertEqual(result.count(".subckt leaf"), 1)
        self.assertIn("duplicate include elided", result)

    def test_include_resolution_cannot_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "top.spice").write_text(".include ../outside.spice\n")
            with self.assertRaisesRegex(NamespaceError, "escapes source root"):
                resolve_includes(root / "top.spice", root)


if __name__ == "__main__":
    unittest.main()
