# shunting

An expression evaluation kernel written with the Python standard library only.

`shunting/core.py` is a three step pipeline: `tokenize()` turns source text into
tokens, `to_postfix()` runs the shunting yard over them and `evaluate()` runs the
resulting reverse polish program against an `Environment` of variables.

    evaluate("2 + 3 * 4")                 -> 14
    evaluate("(2 + 3) * 4")               -> 20
    evaluate("-2 ^ 2")                    -> -4
    evaluate("10 - 7 % 4")                -> 7
    evaluate("x * 2 + 1", {"x": 3})       -> 7
    evaluate("max(pow(2, 3), 10) / 4")    -> 2.5

The operators are `+ - * / % ^` plus a unary `+ -`, the functions are `abs`,
`min`, `max`, `sqrt`, `floor`, `ceil` and `pow`, and numbers may be written as
`12`, `12.5`, `.5` or `1.5e-2`.  Malformed source raises `ParseError`, a failure
at run time raises `EvaluationError`, and both derive from `ExpressionError`.

## Running the tests

From the project root:

    python3 -m unittest discover -s tests -v
