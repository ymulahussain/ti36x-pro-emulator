import unittest

from ti36x.engine import Calculator
from ti36x.evaluator import MAX_EXPRESSION_LENGTH


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator()

    def expression(self, expression, expected):
        state = self.calc.set_expression(expression)
        self.assertIsNone(state.error, (expression, state.error))
        self.assertEqual(state.result, expected)

    def test_arithmetic_and_exact_results(self):
        for expression, expected in [
            ("2+3*4", "14"),
            ("(2+3)*4", "20"),
            ("0.1+0.2", "0.3"),
            ("3÷4", "3/4"),
            ("√(2)", "sqrt(2)"),
            ("2^3^2", "512"),
            ("-2^2", "-4"),
            ("2^-3", "1/8"),
        ]:
            with self.subTest(expression=expression):
                self.expression(expression, expected)

    def test_implicit_multiplication(self):
        for expression, expected in [
            ("2π", "2*pi"),
            ("2(3+4)", "14"),
            ("(2+1)(4+1)", "15"),
            ("2sin(30)", "1"),
            ("ππ", "pi**2"),
            ("2e", "5.436563657"),
        ]:
            with self.subTest(expression=expression):
                self.expression(expression, expected)

    def test_trigonometry_in_all_angle_units(self):
        for angle, expression, expected in [
            ("DEG", "sin(30)", "1/2"),
            ("DEG", "asin(1/2)", "30"),
            ("RAD", "sin(π/2)", "1"),
            ("RAD", "acos(0)", "pi/2"),
            ("GRAD", "sin(100)", "1"),
            ("GRAD", "asin(1)", "100"),
            ("DEG", "sin(asin(1/2))", "1/2"),
        ]:
            with self.subTest(angle=angle, expression=expression):
                self.calc.state.angle = angle
                self.expression(expression, expected)

    def test_roots_logs_scientific_entry_and_probability(self):
        for expression, expected in [
            ("root(3,-8)", "-2"),
            ("root(2,9)", "3"),
            ("log(100)", "2"),
            ("ln(e)", "1"),
            ("3ᴇ⁻2", "3/100"),
            ("5!", "120"),
            ("(2+3)!", "120"),
            ("abs(-3)!", "6"),
            ("ncr(5,2)", "10"),
            ("npr(5,2)", "20"),
        ]:
            with self.subTest(expression=expression):
                self.expression(expression, expected)

    def test_math_errors_are_reported_and_retry_clears_error(self):
        for expression in [
            "1/0",
            "0/0",
            "ln(0)",
            "tan(90)",
            "(-1)!",
            "ncr(2,3)",
            "root(0,2)",
        ]:
            with self.subTest(expression=expression):
                state = self.calc.set_expression(expression)
                self.assertEqual(state.result, "Error")
                self.assertTrue(state.error)
                self.expression("2+2", "4")

    def test_only_calculator_expressions_are_accepted(self):
        for expression in [
            "unknown",
            "sin.__class__",
            '__import__("os")',
            "[1,2]",
            "lambda: 2",
            "sin(x=3)",
            "2 2",
            "(1).real",
            "9^9999",
            "factorial(1001)",
            "1e999",
            "2" * 101,
            "1" * (MAX_EXPRESSION_LENGTH + 1),
        ]:
            with self.subTest(expression=expression):
                self.assertTrue(self.calc.set_expression(expression).error)

    def test_chaining_uses_exact_previous_result(self):
        self.expression("1/3", "1/3")
        self.calc.press_sequence(["mul", "3", "enter"])
        self.assertEqual(self.calc.state.result, "1")
        self.calc.press_sequence(["square", "enter", "inv", "enter"])
        self.assertEqual(self.calc.state.result, "1")
        self.expression("√(2)", "sqrt(2)")
        self.expression("ans^2", "2")

    def test_new_digits_start_new_calculation(self):
        self.expression("2+2", "4")
        self.calc.press_sequence(["5", "enter"])
        self.assertEqual(self.calc.state.result, "5")

    def test_shift_aliases_and_fraction_entry(self):
        self.calc.press_sequence(["lnlog", "lnlog", "1", "0", "0", "rparen", "enter"])
        self.assertEqual(self.calc.state.result, "2")
        self.calc.reset()
        self.calc.press_sequence(["3", "frac", "4", "enter"])
        self.assertEqual(self.calc.state.result, "3/4")
        self.calc.press("fd")
        self.assertEqual(self.calc.state.result, "0.75")
        self.calc.press("fd")
        self.assertEqual(self.calc.state.result, "3/4")
        self.calc.press_sequence(["2nd", "fd"])
        self.assertEqual(self.calc.state.result, "0.75")

    def test_memory_store_recall_and_clear(self):
        self.expression("√(2)", "sqrt(2)")
        self.calc.press_sequence(["sto", "var", "var", "enter"])
        self.assertEqual(self.calc.state.memory["y"], "sqrt(2)")
        self.expression("y^2", "2")
        self.calc.press_sequence(["2nd", "sto", "2", "square", "enter"])
        self.assertEqual(self.calc.state.result, "2")
        self.calc.press_sequence(["2nd", "var", "1"])
        self.assertTrue(all(value == "0" for value in self.calc.state.memory.values()))

    def test_memory_store_from_entry_and_x(self):
        self.calc.press_sequence(["7", "sto", "var", "enter"])
        self.assertEqual(self.calc.state.memory["x"], "7")
        self.assertIsNone(self.calc.state.memory_action)
        self.expression("2x", "14")

    def test_history_navigation_and_cursor_editing(self):
        self.expression("1+1", "2")
        self.expression("2+2", "4")
        self.calc.press("up")
        self.assertEqual(self.calc.state.entry, "2+2")
        self.calc.press("up")
        self.assertEqual(self.calc.state.entry, "1+1")
        self.calc.press("down")
        self.assertEqual(self.calc.state.entry, "2+2")
        self.calc.press("down")
        self.assertEqual(self.calc.state.entry, "")
        self.calc.press_sequence(["1", "2", "left", "delete", "3", "enter"])
        self.assertEqual(self.calc.state.result, "13")

    def test_menu_quit_and_reset(self):
        self.calc.press("math")
        self.assertEqual(self.calc.state.menu, "math")
        self.calc.press_sequence(["2nd", "mode"])
        self.assertIsNone(self.calc.state.menu)
        self.assertEqual(self.calc.state.angle, "DEG")
        self.calc.press_sequence(["sto", "clear"])
        self.assertIsNone(self.calc.state.memory_action)
        self.calc.press_sequence(["mode", "right", "right", "enter", "clear"])
        self.assertEqual(self.calc.state.angle, "GRAD")
        self.calc.press_sequence(["2nd", "0", "2"])
        self.assertEqual(self.calc.state.angle, "DEG")
        self.assertEqual(self.calc.state.history, [])

    def test_format_modes_use_numeric_results(self):
        for notation, expected in [
            ("NORM", "0.3333"),
            ("SCI", "3.3333ᴇ-1"),
            ("ENG", "333.3333ᴇ-3"),
        ]:
            with self.subTest(notation=notation):
                self.calc.set_modes(notation=notation, decimal_places=4)
                self.expression("1/3", expected)

    def test_entry_and_history_are_bounded(self):
        self.calc.press_sequence(["1"] * (MAX_EXPRESSION_LENGTH + 1))
        self.assertEqual(len(self.calc.state.entry), MAX_EXPRESSION_LENGTH)
        self.assertTrue(self.calc.state.error)
        for _ in range(101):
            self.calc.set_expression("1")
        self.assertEqual(len(self.calc.state.history), 100)
        self.assertEqual(len(self.calc.state.to_dict()["history"]), 10)


if __name__ == "__main__":
    unittest.main()
