"""Acceptance tests for the shunting expression kernel.

Run them from the project root with:

    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shunting import (
    Environment,
    EvaluationError,
    ExpressionError,
    ParseError,
    evaluate,
    tokenize,
    to_postfix,
)


def value_of(source, variables=None):
    """The value of the expression; an unexpected failure is a test failure."""
    try:
        return evaluate(source, variables)
    except Exception as error:
        raise AssertionError("%r raised %s: %s" % (source, type(error).__name__, error))


def error_of(source, kind, variables=None):
    """Report the error the expression must raise, as a test failure otherwise."""
    try:
        result = evaluate(source, variables)
    except kind as error:
        return error
    except Exception as error:
        raise AssertionError("%r raised %s instead of %s: %s"
                             % (source, type(error).__name__, kind.__name__, error))
    raise AssertionError("%r was accepted and gave %r instead of raising %s"
                         % (source, result, kind.__name__))


def texts(tokens):
    return [token.text for token in tokens]


def kinds(tokens):
    return [token.kind for token in tokens]


class ShuntingTest(unittest.TestCase):
    def test_tokens_and_postfix_order(self):
        self.assertEqual(texts(tokenize("12 + 3.5")), ["12", "+", "3.5"])
        self.assertEqual(kinds(tokenize("12 + 3.5")), ["number", "operator", "number"])
        self.assertEqual(kinds(tokenize("min(1, 2)")), ["name", "left", "number", "comma", "number", "right"])
        self.assertEqual(texts(to_postfix("1 + 2 * 3")), ["1", "2", "3", "*", "+"])
        self.assertEqual(texts(to_postfix("(1 + 2) * 3")), ["1", "2", "+", "3", "*"])
        self.assertEqual(texts(to_postfix("2 - 3 - 4")), ["2", "3", "-", "4", "-"])
        self.assertEqual(texts(to_postfix("10 - 7 % 4")), ["10", "7", "4", "%", "-"])
        self.assertEqual(texts(to_postfix("2 ^ 3 ^ 2")), ["2", "3", "2", "^", "^"])
        self.assertEqual(texts(to_postfix("-2 ^ 2")), ["2", "2", "^", "-"])
        self.assertEqual(texts(to_postfix("max(min(1, 2), 3)")), ["1", "2", "min", "3", "max"])
        calls = to_postfix("min(1, 2)")
        self.assertEqual(calls[-1].kind, "call")
        self.assertEqual(calls[-1].text, "min")
        self.assertEqual(calls[-1].value, 2)


class ArithmeticTest(unittest.TestCase):
    def test_precedence_and_left_associativity(self):
        self.assertEqual(value_of("2 + 3 * 4"), 14)
        self.assertEqual(value_of("(2 + 3) * 4"), 20)
        self.assertEqual(value_of("2 * (3 + 4)"), 14)
        self.assertEqual(value_of("((1 + 2) * (3 + 4))"), 21)
        self.assertEqual(value_of("10 - 3 - 2"), 5)
        self.assertEqual(value_of("1 - 2 - 3"), -4)
        self.assertEqual(value_of("100 / 5 / 2"), 10.0)
        self.assertEqual(value_of("6 / 3 * 2"), 4.0)
        self.assertEqual(value_of("18 - 4 * 3 + 6"), 12)
        self.assertEqual(value_of("2 + 3 * 4 - 6 / 3"), 12.0)
        self.assertEqual(value_of("1.5e2"), 150.0)
        self.assertEqual(value_of(".5 + .25"), 0.75)

    def test_percent_binds_like_multiplication_and_follows_the_divisor_sign(self):
        self.assertEqual(value_of("10 - 7 % 4"), 7)
        self.assertEqual(value_of("2 + 7 % 3"), 3)
        self.assertEqual(value_of("7 % 4 * 2"), 6)
        self.assertEqual(value_of("1 + 10 % 3 * 2"), 3)
        self.assertEqual(value_of("20 % 6"), 2)
        self.assertEqual(value_of("-7 % 4 + 1"), 2)
        self.assertEqual(value_of("-7 % 3"), 2)
        self.assertEqual(value_of("7 % -3"), -2)
        self.assertEqual(value_of("-7 % -3"), -1)
        self.assertEqual(value_of("-8 % 3"), 1)
        self.assertEqual(value_of("8 % 3"), 2)
        self.assertEqual(value_of("(-7) % 4"), 1)

    def test_a_zero_divisor_is_reported_as_an_evaluation_error(self):
        self.assertEqual(value_of("0 / 5"), 0.0)
        self.assertEqual(value_of("0 % 5"), 0)
        self.assertEqual(value_of("0.0 + 3"), 3.0)
        error_of("1 / 0", EvaluationError)
        error_of("1 / 0.0", EvaluationError)
        error_of("5 % 0", EvaluationError)
        error_of("2.5 % 0", EvaluationError)
        error_of("0 ^ -1", EvaluationError)

    def test_power_is_right_associative_and_looser_than_unary_minus(self):
        self.assertEqual(value_of("2 ^ 3 ^ 2"), 512)
        self.assertEqual(value_of("-2 ^ 2"), -4)
        self.assertEqual(value_of("-2 ^ 2 ^ 2"), -16)
        self.assertEqual(value_of("-2 ^ 3 ^ 2"), -512)
        self.assertEqual(value_of("2 ^ -2"), 0.25)
        self.assertEqual(value_of("-2 ^ -2"), -0.25)
        self.assertEqual(value_of("2 ^ 3 * 2"), 16)
        self.assertEqual(value_of("2 * 3 ^ 2"), 18)
        self.assertEqual(value_of("4 ^ 0.5"), 2.0)

    def test_integer_and_float_results_are_kept_apart(self):
        self.assertEqual(value_of("7 / 2"), 3.5)
        self.assertEqual(value_of("1 / 3"), 1 / 3)
        self.assertEqual(value_of("6 / 2"), 3.0)
        self.assertIsInstance(value_of("6 / 2"), float)
        self.assertEqual(value_of("4.0 / 2"), 2.0)
        self.assertEqual(value_of("7.5 / 2.5"), 3.0)
        self.assertIsInstance(value_of("2 + 3"), int)
        self.assertIsInstance(value_of("2 * 3"), int)
        self.assertEqual(value_of("7 % 4"), 3)
        self.assertIsInstance(value_of("7 % 4"), int)
        self.assertEqual(value_of("2.5 + 0.5"), 3.0)
        self.assertEqual(value_of("1.0 - 1"), 0.0)


class CallTest(unittest.TestCase):
    def test_call_arguments_are_passed_in_order(self):
        self.assertEqual(value_of("pow(2, 10)"), 1024)
        self.assertEqual(value_of("pow(10, 2)"), 100)
        self.assertEqual(value_of("max(1, 5, 3)"), 5)
        self.assertEqual(value_of("min(4, 2, 6)"), 2)
        self.assertEqual(value_of("abs(-4)"), 4)
        self.assertEqual(value_of("abs(3 - 8)"), 5)
        self.assertEqual(value_of("sqrt(9)"), 3.0)
        self.assertEqual(value_of("floor(2.7)"), 2)
        self.assertEqual(value_of("ceil(2.1)"), 3)
        self.assertEqual(value_of("max(min(3, 1), 2)"), 2)
        self.assertEqual(value_of("pow(pow(2, 2), 3)"), 64)

    def test_calls_check_the_number_of_arguments(self):
        error_of("sqrt(9, 2)", EvaluationError)
        error_of("abs(1, 2)", EvaluationError)
        error_of("pow(2, 3, 4)", EvaluationError)
        error_of("pow(2)", EvaluationError)
        error_of("sqrt()", ExpressionError)
        error_of("min()", ExpressionError)
        error_of("unknown(1)", EvaluationError)
        error_of("sqrt(-4)", EvaluationError)
        self.assertEqual(value_of("min(7)"), 7)
        self.assertEqual(value_of("max(3, 3)"), 3)


class ErrorTest(unittest.TestCase):
    def test_malformed_expressions_are_rejected(self):
        error_of("(1 + 2", ParseError)
        error_of("2 * (3 + 4", ParseError)
        error_of("((1 + 2)", ParseError)
        error_of("min(1, 2", ExpressionError)
        error_of("1 + 2)", ParseError)
        error_of("(1 + 2))", ParseError)
        error_of("1 2", ParseError)
        error_of("1 +", ParseError)
        error_of("", ParseError)
        error_of("   ", ParseError)
        error_of("* 3", ParseError)
        error_of("1 + * 2", ParseError)
        error_of("1 + @ 2", ParseError)
        error_of("1, 2", ParseError)
        error_of("min(1,)", ExpressionError)
        error_of("min(,1)", ExpressionError)
        with self.assertRaises(TypeError):
            tokenize(None)

    def test_variables_are_resolved_and_checked(self):
        self.assertEqual(value_of("x * 2 + 1", {"x": 3}), 7)
        self.assertEqual(value_of("a + b", {"a": 1.5, "b": 2}), 3.5)
        self.assertEqual(value_of("n ^ 2", {"n": 5}), 25)
        self.assertEqual(value_of("radius * pi * 2", {"radius": 2.0, "pi": 3.14}), 12.56)
        error_of("y + 1", EvaluationError)
        error_of("x + 1", EvaluationError, {"x": "twelve"})
        error_of("x + 1", EvaluationError, {"x": True})
        self.assertEqual(evaluate("2 * n", Environment().define("n", 4)), 8)
        self.assertEqual(evaluate("n + 1", Environment({"n": 1.5})), 2.5)


if __name__ == "__main__":
    unittest.main()
