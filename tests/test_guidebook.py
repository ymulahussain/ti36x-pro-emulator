"""Expected behaviors and numerical examples from TI-36XPro_Guidebook_EN.pdf.

Page numbers below are the guidebook's printed page numbers.
"""

import math
import unittest

import sympy as sp

from ti36x.engine import Calculator
from ti36x.evaluator import EvalError
from ti36x.features import calculate, serialize


class GuidebookTests(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator()

    def keys(self, keys, expected):
        self.calc.press_sequence(keys)
        self.assertIsNone(self.calc.state.error)
        self.assertEqual(self.calc.state.result, expected)

    def feature(self, operation, parameters):
        return calculate(self.calc, operation, parameters)

    def test_p4_off_retains_history_modes_memory_and_ans(self):
        self.calc.set_expression("15")
        self.calc.press_sequence(["sto", "var", "enter"])
        self.calc.set_modes(angle="RAD", decimal_places=2)
        self.calc.press_sequence(["2nd", "on"])
        self.assertFalse(self.calc.state.powered_on)
        self.calc.press("9")
        self.assertEqual(self.calc.state.entry, "")
        self.calc.press("on")
        self.assertEqual(self.calc.state.angle, "RAD")
        self.assertEqual(self.calc.state.memory["x"], "15")
        self.assertTrue(self.calc.state.history)
        self.assertEqual(self.calc._ans_value, 15)

    def test_p6_mode_menu_does_not_cycle_angle_implicitly(self):
        self.calc.press("mode")
        self.assertEqual(self.calc.state.angle, "DEG")
        self.calc.press_sequence(["right", "enter", "clear"])
        self.assertEqual(self.calc.state.angle, "RAD")
        self.calc.press_sequence(["mode", "down", "right", "right", "enter", "clear"])
        self.assertEqual(self.calc.state.notation, "ENG")

    def test_p9_multitap_functions(self):
        for key, choices in [
            ("sin", ["sin(", "asin(", "sinh(", "asinh("]),
            ("lnlog", ["ln(", "log("]),
            ("pi", ["π", "e", "i"]),
        ]:
            self.calc.reset()
            for expected in choices:
                self.calc.press(key)
                self.assertEqual(self.calc.state.entry, expected)
        self.calc.reset()
        self.calc.press_sequence(["var", "right", "var"])
        self.assertEqual(self.calc.state.entry, "xx")

    def test_p10_history_enter_pastes_before_re_evaluation(self):
        self.calc.set_expression("7*4")
        self.calc.set_expression("3*1")
        self.calc.press_sequence(["up", "up", "enter"])
        self.assertEqual(self.calc.state.entry, "7*4")
        self.assertEqual(len(self.calc.state.history), 2)
        self.calc.press("enter")
        self.assertEqual(self.calc.state.result, "28")

    def test_p11_answer_toggle_and_chaining(self):
        self.keys(["2nd", "sq", "8", "enter"], "2*sqrt(2)")
        self.calc.press("fd")
        self.assertEqual(self.calc.state.result, "2.828427125")
        self.calc.reset()
        self.keys(["3", "mul", "3", "enter", "mul", "3", "enter"], "27")

    def test_p12_classic_and_mathprint_power_order(self):
        self.calc.set_modes(entry_format="CLASSIC")
        self.assertEqual(self.calc.set_expression("2^3^2").result, "64")
        self.assertEqual(self.calc.set_expression("2^(3^2)").result, "512")
        self.calc.set_expression("2^9^5")
        self.assertEqual(self.calc._ans_value, 2**45)
        self.calc.set_modes(entry_format="MATHPRINT")
        self.assertEqual(self.calc.set_expression("2^3^2").result, "512")
        for entry in ["CLASSIC", "MATHPRINT"]:
            self.calc.set_modes(entry_format=entry)
            self.assertEqual(self.calc.set_expression("3²²").result, "81")
            self.assertEqual(self.calc.set_expression("3²⁻¹").result, "1/9")

    def test_p13_enter_closes_open_parentheses(self):
        self.keys(["2nd", "sq", "9", "add", "1", "6", "enter"], "5")
        self.assertEqual(self.calc.set_expression("4(2+3").result, "20")

    def test_p13_delete_overwrites_and_insert_preserves_character(self):
        self.calc.press_sequence(["1", "2", "left", "3"])
        self.assertEqual(self.calc.state.entry, "13")
        self.calc.reset()
        self.calc.press_sequence(["1", "2", "left", "2nd", "delete", "3"])
        self.assertEqual(self.calc.state.entry, "132")
        self.calc.press("delete")
        self.assertEqual(self.calc.state.entry, "13")

    def test_p16_mathprint_fraction_with_expressions(self):
        self.keys(
            ["frac", "1", "dot", "2", "add", "1", "dot", "3", "down", "4", "enter"],
            "5/8",
        )
        self.calc.reset()
        self.keys(["3", "frac", "4", "right", "add", "1", "enter"], "7/4")

    def test_p16_mixed_fraction_key(self):
        self.keys(["1", "2nd", "7", "7", "down", "1", "2", "enter"], "19/12")

    def test_p17_ore_percentage_problem_and_ans(self):
        self.calc.set_expression("3%*5000+2.3%*7300")
        self.assertIsNone(self.calc.state.error)
        self.assertEqual(self.calc.state.result, "317.9")
        self.keys(["mul", "2", "8", "0", "enter"], "89012")
        self.calc.reset()
        self.keys(["2", "2nd", "div", "mul", "1", "5", "0", "enter"], "3")

    def test_p18_roots_and_reciprocal_key_shortcuts(self):
        self.keys(["2nd", "sq", "4", "9", "enter"], "7")
        self.calc.reset()
        self.keys(["6", "2nd", "power", "6", "4", "enter"], "2")
        self.calc.reset()
        self.keys(["2", "2nd", "frac", "enter"], "1/2")
        self.calc.reset()
        self.keys(["2", "reciprocal", "enter"], "1/2")

    def test_p19_circle_area(self):
        self.keys(["pi", "mul", "1", "2", "sq", "enter"], "144*pi")
        self.calc.set_modes(decimal_places=1)
        self.assertEqual(self.calc.state.result, "452.4")

    def test_p20_math_menu_lcm_gcd_and_prime_factors(self):
        self.keys(["math", "2", "6", "comma", "9", "rparen", "enter"], "18")
        self.assertEqual(self.calc.set_expression("gcd(18,33)").result, "3")
        self.assertEqual(
            self.feature("factor", {"value": 253}), {"factors": {"11": 1, "23": 1}}
        )
        self.assertEqual(
            self.feature("summation", {"expression": "2x", "start": 1, "end": 4}), 20
        )
        self.assertEqual(
            self.feature("product", {"expression": "1/x", "start": 1, "end": 5}),
            sp.Rational(1, 120),
        )

    def test_p21_number_functions(self):
        for expression, expected in [
            ("round(1.245,1)", "1.2"),
            ("iPart(4.9)", "4"),
            ("fPart(4.9)", "0.9"),
            ("int(-5.6)", "-6"),
            ("min(4,-5)", "-5"),
            ("max(.6,.7)", "0.7"),
            ("mod(17,12)", "5"),
        ]:
            with self.subTest(expression=expression):
                self.assertEqual(self.calc.set_expression(expression).result, expected)

    def test_p22_angle_modifiers_and_dms(self):
        self.calc.set_modes(angle="RAD")
        self.assertEqual(self.calc.set_expression("sin(deg(30))").result, "1/2")
        self.calc.set_modes(angle="DEG")
        self.assertEqual(self.calc.set_expression("rad(2π)").result, "360")
        result = self.feature("dms", {"value": "12+31/60+45/3600+26+54/60+38/3600"})
        self.assertEqual(result["degrees"], 39)
        self.assertEqual(result["minutes"], 26)
        self.assertAlmostEqual(float(result["seconds"]), 23)

    def test_p25_rectangular_polar_coordinates(self):
        self.calc.set_modes(decimal_places=1)
        for expression, expected in [
            ("rx(5,30)", "4.3"),
            ("ry(5,30)", "2.5"),
            ("pr(3,4)", "5.0"),
            ("pt(3,4)", "53.1"),
        ]:
            self.assertEqual(self.calc.set_expression(expression).result, expected)

    def test_p26_trigonometric_and_inverse_multitap(self):
        self.keys(["tan", "4", "5", "rparen", "enter"], "1")
        self.calc.reset()
        self.keys(["tan", "tan", "1", "rparen", "enter"], "45")
        self.calc.reset()
        self.keys(["5", "mul", "cos", "6", "0", "rparen", "enter"], "5/2")
        self.calc.set_modes(angle="RAD")
        self.assertEqual(self.calc.set_expression("tan(π/4)").result, "1")

    def test_p27_hyperbolics_ignore_angle_unit(self):
        answers = []
        for angle in ["DEG", "RAD", "GRAD"]:
            self.calc.reset()
            self.calc.set_modes(angle=angle)
            self.keys(
                ["sin", "sin", "sin", "5", "rparen", "add", "2", "enter"], "76.20321058"
            )
            answers.append(self.calc._ans_value)
        self.assertTrue(all(x == answers[0] for x in answers))

    def test_p28_logarithm_and_exponential_multitap(self):
        self.keys(["lnlog", "lnlog", "1", "rparen", "enter"], "0")
        self.calc.reset()
        self.keys(["exp10", "exp10", "lnlog", "lnlog", "2", "rparen", "enter"], "2")

    def test_p29_symmetric_numeric_derivative(self):
        self.assertAlmostEqual(
            float(self.feature("derivative", {"expression": "x^2+5x", "point": -1})), 3
        )
        # The manual specifies a symmetric difference, not an exact derivative.
        self.assertAlmostEqual(
            float(
                self.feature(
                    "derivative", {"expression": "x^3", "point": 2, "epsilon": "0.001"}
                )
            ),
            12.000001,
            places=6,
        )

    def test_p30_numeric_integral(self):
        for lower, upper in [(-2, 0), (0, 2)]:
            self.assertAlmostEqual(
                float(
                    self.feature(
                        "integral",
                        {"expression": "-x^2+4", "lower": lower, "upper": upper},
                    )
                ),
                16 / 3,
                places=10,
            )
        self.calc.set_modes(angle="RAD")
        self.assertAlmostEqual(
            float(
                self.feature(
                    "integral", {"expression": "x*sin(x)", "lower": 0, "upper": "π"}
                )
            ),
            math.pi,
            places=10,
        )

    def test_p31_stored_operation(self):
        self.feature("storedop", {"operation": "*2+3"})
        self.keys(["4", "2nd", "rparen"], "11")
        self.keys(["2nd", "rparen"], "25")

    def test_p33_eight_variables_and_store_enter(self):
        self.calc.press_sequence(["1", "5", "sto", "var"])
        self.assertEqual(self.calc.state.memory["x"], "0")
        self.calc.press("enter")
        self.assertEqual(self.calc.state.memory["x"], "15")
        self.calc.press_sequence(["sto", "var", "var", "enter"])
        self.assertEqual(self.calc.state.memory["y"], "15")
        self.assertEqual(set(self.calc.state.memory), set("xyztabcd"))
        self.calc.press_sequence(["2nd", "var", "1"])
        self.assertTrue(all(x == "0" for x in self.calc.state.memory.values()))

    def test_p42_one_variable_statistics(self):
        result = self.feature("stats:1-Var Stats", {"x": [45, 55, 55, 55]})
        self.assertEqual(result["mean_x"], sp.Rational(105, 2))
        self.assertEqual(result["n"], 4)

    def test_p44_weighted_statistics(self):
        result = self.feature(
            "stats:1-Var Stats", {"x": [12, 13, 10, 11], "frequency": [1, 0.5, 1, 0.5]}
        )
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["sum_x"], 34)
        self.assertEqual(result["mean_x"], sp.Rational(34, 3))
        self.assertEqual(result["Sx"], "Error")
        result = self.feature(
            "stats:1-Var Stats", {"x": [12, 13, 10, 15], "frequency": [1, 0.5, 1, 0.5]}
        )
        self.assertEqual(result["mean_x"], 12)

    def test_p46_braking_linear_regression(self):
        result = self.feature(
            "stats:2-Var Stats",
            {"x": [33, 49, 65, 79], "y": [5.3, 14.45, 20.21, 38.45], "predict_x": 55},
        )
        self.assertAlmostEqual(float(result["a"]), 0.67732519, places=7)
        self.assertAlmostEqual(float(result["predicted_y"]), 18.58651224, places=7)

    def test_p47_linear_and_exponential_regression(self):
        result = self.feature(
            "stats:LinReg", {"x": [1, 2, 3, 4, 5], "y": [5, 8, 11, 14, 17]}
        )
        self.assertAlmostEqual(float(result["a"]), 3)
        self.assertAlmostEqual(float(result["b"]), 2)
        result = self.feature(
            "stats:ExpReg", {"x": [0, 1, 2, 3, 4], "y": [10, 14, 23, 35, 48]}
        )
        self.assertTrue(9 < float(result["a"]) < 11)
        self.assertTrue(1.4 < float(result["b"]) < 1.6)

    def test_p49_binomial_distribution_list(self):
        result = self.feature(
            "distribution:binompdf", {"n": 20, "p": 0.6, "x": [3, 6, 9]}
        )
        for x, p in zip([3, 6, 9], result):
            self.assertAlmostEqual(
                p, math.comb(20, x) * 0.6**x * 0.4 ** (20 - x), places=12
            )

    def test_p50_probability_multitap(self):
        self.keys(["4", "prb", "enter"], "24")
        self.calc.reset()
        self.keys(["5", "2", "prb", "prb", "5", "enter"], "2598960")
        self.calc.reset()
        self.keys(["8", "prb", "prb", "prb", "3", "enter"], "336")
        self.calc.reset()
        self.keys(["2", "5", "prb", "prb", "3", "enter"], "2300")

    def test_p52_table_vertex(self):
        result = self.feature(
            "table", {"expression": "x(36-x)", "start": 15, "step": 3, "count": 4}
        )
        self.assertEqual(result[1], {"x": 18, "f(x)": 324})
        self.assertEqual(result[0]["f(x)"], result[2]["f(x)"])

    def test_p53_table_function_call(self):
        self.feature(
            "table", {"expression": "3600-450x", "start": 0, "step": 1, "count": 9}
        )
        self.assertEqual(self.calc.set_expression("f(8)").result, "0")

    def test_p55_matrix_operations(self):
        self.feature("matrix", {"name": "A", "values": [[1, 2], [3, 4]]})
        for expression, expected in [
            ("det([A])", -2),
            ("transpose([A])", sp.Matrix([[1, 3], [2, 4]])),
            ("[A]⁻¹", sp.Matrix([[-2, 1], [sp.Rational(3, 2), sp.Rational(-1, 2)]])),
            ("rref([A])", sp.eye(2)),
        ]:
            self.calc.set_expression(expression)
            self.assertIsNone(self.calc.state.error)
            self.assertEqual(self.calc._ans_value, expected)

    def test_p58_vector_operations(self):
        self.feature("vector", {"name": "u", "values": [0.5, 8]})
        self.feature("vector", {"name": "v", "values": [2, 3]})
        self.assertEqual(self.calc.set_expression("DotP([u],[v])").result, "25")
        self.assertEqual(self.calc.set_expression("norm([v])").result, "sqrt(13)")
        self.calc.set_expression("[u]+[v]")
        self.assertEqual(self.calc._ans_value, sp.Matrix([sp.Rational(5, 2), 11]))

    def test_p59_numeric_solver(self):
        result = self.feature(
            "solver", {"expression": "x^2=2", "variable": "x", "guess": 1}
        )
        self.assertAlmostEqual(float(result["solution"]), math.sqrt(2), places=10)
        self.assertAlmostEqual(float(result["left_minus_right"]), 0, places=10)

    def test_p60_polynomial_solver(self):
        result = self.feature("polynomial", {"coefficients": [1, -2, 2]})
        self.assertEqual(set(result["roots"]), {1 - sp.I, 1 + sp.I})
        self.assertEqual(result["vertex"], [1, 1])

    def test_p61_system_solver_and_saved_variables(self):
        result = self.feature(
            "system", {"coefficients": [[1, 1], [1, -2]], "rhs": [1, 3]}
        )
        self.assertEqual(result, {"x": sp.Rational(5, 3), "y": sp.Rational(-2, 3)})
        result = self.feature(
            "system",
            {"coefficients": [[5, -2, 3], [4, 3, 5], [2, 4, -2]], "rhs": [-9, 4, 14]},
        )
        self.assertEqual(result, {"x": 0, "y": 3, "z": -1})
        self.assertEqual(self.calc.state.memory["z"], "-1")

    def test_p63_infinite_and_inconsistent_systems(self):
        for rhs, error in [
            ([4, 8, 12], "Infinite Solutions"),
            ([4, 9, 12], "No Solution Found"),
        ]:
            with self.assertRaisesRegex(EvalError, error):
                self.feature(
                    "system",
                    {"coefficients": [[1, 2, 3], [2, 4, 6], [3, 6, 9]], "rhs": rhs},
                )

    def test_p64_base_conversion_and_logic(self):
        self.assertEqual(
            self.feature("base", {"value": 127, "from": "DEC", "to": "HEX"})["value"],
            "7F",
        )
        self.assertEqual(
            self.feature("base", {"value": "10000000", "from": "BIN", "to": "OCT"})[
                "value"
            ],
            "200",
        )
        self.calc.set_modes(base="BIN")
        self.assertEqual(self.calc.set_expression("1111+1").result, "10000")
        self.assertEqual(
            self.feature("logic", {"left": "1111", "right": "1010", "operator": "and"})[
                "value"
            ],
            "1010",
        )

    def test_p66_expression_parameters(self):
        self.assertEqual(
            self.feature(
                "expression", {"expression": "2x+z", "values": {"x": 2, "z": 5}}
            ),
            9,
        )
        self.assertEqual(
            self.feature(
                "expression", {"expression": "2x+z", "values": {"x": 4, "z": 6}}
            ),
            14,
        )

    def test_p67_constants_and_conversions(self):
        self.assertEqual(self.feature("constant", {"name": "c"}), 299792458)
        self.assertEqual(
            self.feature("constant", {"name": "h"}), sp.Rational("6.62607015e-34")
        )
        self.assertEqual(
            self.feature("convert", {"value": -22, "from": "F", "to": "C"}), -30
        )
        self.assertEqual(
            self.feature("convert", {"value": 60, "from": "km/h", "to": "m/s"}),
            sp.Rational(50, 3),
        )

    def test_p72_complex_calculations(self):
        self.calc.set_modes(angle="RAD", complex_format="a+bi")
        for expression, expected in [
            ("abs(3+4i)", "5"),
            ("conj(5-6i)", "5 + 6i"),
            ("real(5-6i)", "5"),
            ("imag(5-6i)", "-6"),
        ]:
            self.assertEqual(self.calc.set_expression(expression).result, expected)

    def test_p4_auto_power_down_retains_pending_expression(self):
        self.calc.press_sequence(["2", "add", "3"])
        self.calc._last_activity -= 301
        self.assertTrue(self.calc.expire_if_idle())
        self.assertFalse(self.calc.state.powered_on)
        self.calc.press("on")
        self.keys(["enter"], "5")

    def test_p36_list_formula_updates_after_edit(self):
        result = self.feature(
            "data", {"lists": {"L1": [8, -1, 4]}, "formulas": {"L2": "9/5*L1+32"}}
        )
        self.assertEqual(result["L2"], ["232/5", "151/5", "196/5"])
        result = self.feature("data", {"lists": {"L1": [21]}})
        self.assertEqual(result["L2"], ["349/5"])
        with self.assertRaisesRegex(EvalError, "FORMULA"):
            self.feature("data", {"formulas": {"L1": "L1+1"}})

    def test_p39_normal_and_poisson_distributions(self):
        self.assertAlmostEqual(
            self.feature("distribution:normalcdf", {"lower": -1, "upper": 1}),
            0.682689492137,
            places=10,
        )
        self.assertAlmostEqual(
            self.feature("distribution:invNorm", {"area": 0.95}),
            1.64485362695,
            places=10,
        )
        self.assertAlmostEqual(
            self.feature("distribution:poissonpdf", {"mu": 3, "x": 2}),
            math.exp(-3) * 9 / 2,
            places=12,
        )

    def test_normal_cdf_tails_remain_positive_and_symmetric(self):
        positive = self.feature("distribution:normalcdf", {"lower": 9, "upper": 10})
        negative = self.feature("distribution:normalcdf", {"lower": -10, "upper": -9})
        self.assertGreater(positive, 0)
        self.assertGreater(negative, 0)
        self.assertAlmostEqual(positive / negative, 1, places=12)

    def test_p50_random_seed_is_repeatable(self):
        for _ in range(2):
            self.calc.press_sequence(["5", "sto", "2nd", "prb", "1", "enter"])
            self.calc.press_sequence(["2nd", "prb", "1", "enter"])
            if _ == 0:
                first = self.calc._ans_value
            else:
                self.assertEqual(self.calc._ans_value, first)

    def test_p60_polynomial_repeated_roots(self):
        self.assertEqual(
            self.feature("polynomial", {"coefficients": [1, -3, 3, -1]})["roots"],
            [1, 1, 1],
        )

    def test_p66_decimal_bitwise_complement(self):
        self.assertEqual(
            self.feature("logic", {"left": 192, "right": 48, "operator": "nand"})[
                "decimal"
            ],
            -1,
        )

    def test_p76_documented_domain_errors(self):
        for expression in [
            "sqrt(-1)",
            "log(0)",
            "ln(-1)",
            "asin(2)",
            "root(2,-1)",
            "0^0",
            "(-2)^0.5",
            "70!",
        ]:
            self.assertTrue(self.calc.set_expression(expression).error, expression)
        self.assertIn("OVERFLOW", self.calc.set_expression("10^100").error)


if __name__ == "__main__":
    unittest.main()
