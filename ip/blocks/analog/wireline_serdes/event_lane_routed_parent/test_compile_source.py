#!/usr/bin/env python3
import sys
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compile_source as compiler  # noqa: E402


class RoutedParentSourceTest(unittest.TestCase):
    def test_source_is_namespace_safe_and_self_contained(self) -> None:
        source = compiler.compile_source()
        self.assertNotRegex(source.lower(), r"^\s*\.include\b")
        self.assertEqual(source.count(f".subckt {compiler.TOP} "), 1)
        self.assertEqual(source.count(f".subckt {compiler.EVENT_TOP} "), 1)
        self.assertEqual(source.count(f".subckt {compiler.FANOUT_TOP} "), 1)
        self.assertEqual(source.count(f".subckt {compiler.LANE_TOP} "), 1)
        self.assertEqual(source.count(".subckt reference_level_receiver "), 1)
        self.assertIn(".subckt event__cp_inv ", source)
        self.assertIn(".subckt fanout__cp_inv ", source)
        self.assertNotIn(".subckt cp_inv ", source)

    def test_parent_connects_selected_physical_boundaries(self) -> None:
        source = compiler.compile_source()
        self.assertIn("XEVENT CLKP_H CLKN_H SEL0 SEL1 SEL2", source)
        self.assertIn("XFANOUT E_CLK E_CLKB O_CLK O_CLKB", source)
        for instance in ("XLEVEL_SE", "XLEVEL_SO", "XLEVEL_E", "XLEVEL_O"):
            self.assertIn(instance + " ", source)
        self.assertIn("E_SENSE_UNUSED E_SENSE reference_level_receiver", source)
        self.assertIn("O_SENSE_UNUSED O_SENSE reference_level_receiver", source)
        self.assertIn(
            "E_CAPTURE_CLK_PRE LEVEL_REF LEVEL_BIAS VDD VSS",
            source,
        )
        self.assertIn(
            "O_CAPTURE_CLK_PRE LEVEL_REF LEVEL_BIAS VDD VSS",
            source,
        )
        self.assertIn(
            "E_SENSE E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK E_CAPTURE_CLKB E_SENSE_BOOST",
            source,
        )
        self.assertIn(
            "O_SENSE O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB O_SENSE_BOOST",
            source,
        )

    def test_every_x_instance_resolves_to_one_definition(self) -> None:
        source = compiler.compile_source()
        definitions = {
            match.group(1).lower() for match in re.finditer(
                r"^\s*\.subckt\s+(\S+)", source, re.IGNORECASE | re.MULTILINE)
        }
        statements = []
        current = ""
        for line in source.splitlines():
            if line.lstrip().startswith("+"):
                current += " " + line.lstrip()[1:]
            else:
                if current:
                    statements.append(current)
                current = line
        statements.append(current)
        instances = [statement for statement in statements
                     if statement.lstrip().lower().startswith("x")]
        self.assertGreater(len(instances), 40)
        external_pdk_primitives = {"pfet_03v3", "nfet_03v3", "ppolyf_u"}
        for statement in instances:
            tokens = statement.split()
            positional = [token for token in tokens
                          if "=" not in token and token.lower() != "params:"]
            target = positional[-1].lower()
            self.assertIn(target, definitions | external_pdk_primitives,
                          statement)


if __name__ == "__main__":
    unittest.main()
