import unittest
from screen_gpio_liberty import groups, interpolate

class LibertyScreenTests(unittest.TestCase):
    def test_nested_group_and_quoted_braces(self):
        s='cell ("a") { note : "}"; pin ("P") { capacitance : 1; } }'
        name,body=list(groups(s,'cell'))[0]
        self.assertEqual(name,'a')
        self.assertEqual(list(groups(body,'pin'))[0][0],'P')

    def test_bilinear_table_and_endpoints(self):
        table='index_1("0, 1"); index_2("2, 4"); values("2, 4", "4, 6");'
        self.assertEqual(interpolate(table,0.5,3),4)
        self.assertEqual(interpolate(table,1,4),6)
        with self.assertRaisesRegex(ValueError,'extrapolation'): interpolate(table,0.5,5)

    def test_malformed_table_rejected(self):
        with self.assertRaisesRegex(ValueError,'dimensions'):
            interpolate('index_1("0, 1"); index_2("2, 4"); values("2, 4");',0.5,3)

if __name__ == '__main__': unittest.main()
