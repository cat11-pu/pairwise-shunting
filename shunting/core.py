r"""An expression evaluation kernel built on the shunting yard algorithm.

    tokenize(source)          the source text as a list of Token objects
    to_postfix(source)        the same expression in reverse polish order
    evaluate(source, ...)     the value of the expression

`to_postfix` is the shunting yard: operands go straight to the output while
operators wait on a stack until the operators above them are bound no tighter.
One frame per open parenthesis rides on that stack, so a closing parenthesis
ends either a plain group or a function call.  The operators, loose to tight,
are `+ -`, `* / %`, the unary `+ -` and `^`, which make `10 - 3 - 2` five,
`2 ^ 3 ^ 2` five hundred and twelve and `-2 ^ 2` minus four.  Values are
integers or floats: two integer operands of `+ - * %` give an integer again
while `/` and `sqrt` always give a float, and a number is written `12`,
`12.5`, `.5` or `1.5e-2`.  The functions are `abs`, `min`, `max`, `sqrt`,
`floor`, `ceil` and `pow`, and they receive their arguments left to right.

Malformed source raises ParseError, a failure at run time (a zero divisor, an
unknown name, the wrong number of arguments) raises EvaluationError; both
derive from ExpressionError.
"""

import math

DIGITS = "0123456789"
OPERATOR_CHARS = "+-*/%^"
PUNCTUATION = {"(": "left", ")": "right", ",": "comma"}
NAME_START = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
NAME_CHARS = NAME_START + DIGITS
VALUE_KINDS = ("number", "name", "right")

OPERATOR_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 1, "^": 4}
OPERATOR_ASSOCIATIVITY = {"+": "left", "-": "left", "*": "left", "/": "left",
                          "%": "left", "^": "right"}
UNARY_PRECEDENCE = 5
UNARY_OPERATORS = ("+", "-")


class ExpressionError(Exception):
    """Base class of every error this module reports."""

class ParseError(ExpressionError):
    """The source text is not a well formed expression."""

class EvaluationError(ExpressionError):
    """The expression is well formed but cannot be evaluated."""


class Token:
    """A number, a name, an operator, a bracket, a comma or, in postfix
    order, a call."""

    __slots__ = ("kind", "text", "value", "position")

    def __init__(self, kind, text, value=None, position=0):
        self.kind = kind
        self.text = text
        self.value = value
        self.position = position


def tokenize(source):
    """Split a source string into a list of Token objects."""
    if not isinstance(source, str):
        raise TypeError("an expression must be a string")
    tokens = []
    position = 0
    length = len(source)
    while position < length:
        ch = source[position]
        if ch.isspace():
            position += 1
        elif ch in DIGITS or (ch == "." and position + 1 < length and source[position + 1] in DIGITS):
            start = position
            value, position = _scan_number(source, position)
            tokens.append(Token("number", source[start:position], value, start))
        elif ch in NAME_START:
            start = position
            while position < length and source[position] in NAME_CHARS:
                position += 1
            tokens.append(Token("name", source[start:position], None, start))
        elif ch in OPERATOR_CHARS or ch in PUNCTUATION:
            tokens.append(Token(PUNCTUATION.get(ch, "operator"), ch, None, position))
            position += 1
        else:
            raise ParseError("the character %r at position %d is not part of an expression" % (ch, position))
    return tokens

def _scan_number(source, position):
    """Read one number and return it with the position just behind it."""
    start = position
    length = len(source)
    while position < length and source[position] in DIGITS:
        position += 1
    floating = False
    if position < length and source[position] == ".":
        floating = True
        position += 1
        while position < length and source[position] in DIGITS:
            position += 1
    if position < length and source[position] in "eE":
        floating = True
        position += 1
        if position < length and source[position] in "+-":
            position += 1
        digits = position
        while position < length and source[position] in DIGITS:
            position += 1
        if position == digits:
            raise ParseError("the exponent at position %d needs digits" % (digits,))
    text = source[start:position]
    return (float(text), position) if floating else (int(text), position)


class _Frame:
    """One open parenthesis: a plain group, or a call with a function name."""

    __slots__ = ("kind", "name", "arguments", "values", "position")

    def __init__(self, name, position):
        self.kind = "frame"
        self.name = name
        self.arguments = 0
        self.values = 0
        self.position = position

def _outranks(top_precedence, current_precedence, current_associativity):
    """True when the stacked operator has to leave before the current one: a
    tighter one leaves first, and at equal precedence only a left associative
    current operator takes its left neighbour with it."""
    if top_precedence > current_precedence:
        return True
    if top_precedence < current_precedence:
        return False
    return True

def to_postfix(source):
    """The expression of source as a list of tokens in reverse polish order."""
    return _shunt(tokenize(source))

def _shunt(tokens):
    output = []
    stack = []
    frames = []
    previous = None

    def emit(token):
        output.append(token)
        if frames:
            frames[-1].values += 1

    def drain():
        while stack and stack[-1].kind in ("operator", "unary"):
            output.append(stack.pop())

    for token in tokens:
        kind = token.kind
        if kind == "number" or kind == "name":
            if previous is not None and previous.kind in VALUE_KINDS:
                raise ParseError("an operator before %r at position %d is missing" % (token.text, token.position))
            emit(token)
        elif kind == "operator":
            if previous is None or previous.kind not in VALUE_KINDS:
                if token.text not in UNARY_OPERATORS:
                    raise ParseError("the operator %r at position %d has no left operand" % (token.text, token.position))
                stack.append(Token("unary", token.text, None, token.position))
            else:
                precedence = OPERATOR_PRECEDENCE[token.text]
                associativity = OPERATOR_ASSOCIATIVITY[token.text]
                while stack and stack[-1].kind in ("operator", "unary"):
                    top = stack[-1]
                    if top.kind == "unary":
                        top_precedence = UNARY_PRECEDENCE
                    else:
                        top_precedence = OPERATOR_PRECEDENCE[top.text]
                    if not _outranks(top_precedence, precedence, associativity):
                        break
                    output.append(stack.pop())
                stack.append(Token("operator", token.text, None, token.position))
        elif kind == "left":
            name = None
            if previous is not None and previous.kind == "name":
                name = output.pop().text
                if frames:
                    frames[-1].values -= 1
            elif previous is not None and previous.kind in ("number", "right"):
                raise ParseError("an operator before ( at position %d is missing" % (token.position,))
            frame = _Frame(name, token.position)
            stack.append(frame)
            frames.append(frame)
        elif kind == "comma":
            if not frames or frames[-1].name is None:
                raise ParseError("the comma at position %d is outside a call" % (token.position,))
            if previous is None or previous.kind not in VALUE_KINDS:
                raise ParseError("the comma at position %d has no argument before it" % (token.position,))
            drain()
            frames[-1].arguments += 1
            frames[-1].values = 0
        elif kind == "right":
            if not frames:
                raise ParseError("the ) at position %d closes nothing" % (token.position,))
            if previous is None or previous.kind not in VALUE_KINDS:
                raise ParseError("the ) at position %d has no value before it" % (token.position,))
            drain()
            frame = stack.pop()
            frames.pop()
            if frame.name is None:
                if frames:
                    frames[-1].values += 1
            else:
                arguments = frame.arguments + (1 if frame.values else 0)
                emit(Token("call", frame.name, arguments, frame.position))
        else:
            raise ExpressionError("cannot shunt the token %r" % (kind,))
        previous = token
    drain()
    if previous is not None and previous.kind not in VALUE_KINDS:
        raise ParseError("the expression ends with %r" % (previous.text,))
    if not output:
        raise ParseError("the expression is empty")
    return output


def evaluate(source, variables=None):
    """Tokenize, shunt and run one expression and return its value."""
    environment = variables if isinstance(variables, Environment) else Environment(variables)
    return _run(to_postfix(source), environment)

def _run(tokens, environment):
    stack = []
    for token in tokens:
        kind = token.kind
        if kind == "number":
            stack.append(token.value)
        elif kind == "name":
            stack.append(environment.lookup(token.text))
        elif kind == "unary":
            if not stack:
                raise EvaluationError("the unary %r at position %d has no operand" % (token.text, token.position))
            stack.append(_apply_unary(token.text, stack.pop()))
        elif kind == "operator":
            if len(stack) < 2:
                raise EvaluationError("the operator %r at position %d needs two operands" % (token.text, token.position))
            right = stack.pop()
            left = stack.pop()
            stack.append(_apply_binary(token.text, left, right))
        elif kind == "call":
            if len(stack) < token.value:
                raise EvaluationError("the call to %r at position %d has too few arguments" % (token.text, token.position))
            arguments = [stack.pop() for _ in range(token.value)]
            stack.append(_call(token.text, arguments))
        else:
            raise ExpressionError("cannot run the token %r" % (kind,))
    if len(stack) != 1:
        raise EvaluationError("the expression left %d values behind" % (len(stack),))
    return stack[0]

def _apply_unary(operator, value):
    """The unary plus is the identity and the unary minus negates."""
    return -value if operator == "-" else +value

def _apply_binary(operator, left, right):
    if operator in ("/", "%") and left == 0:
        reason = "division by zero" if operator == "/" else "modulo by zero"
        raise EvaluationError(reason)
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        if isinstance(left, int) and isinstance(right, int):
            return left // right
        return left / right
    if operator == "%":
        return _modulo(left, right)
    if operator == "^":
        return _power(left, right)
    raise ExpressionError("unknown operator %r" % (operator,))

def _modulo(left, right):
    return math.fmod(left, right)

def _sqrt(value):
    if value < 0:
        raise EvaluationError("sqrt needs a value that is not negative")
    return math.sqrt(value)

def _power(base, exponent):
    if not isinstance(exponent, int):
        if base < 0:
            raise EvaluationError("a negative base needs an integer exponent")
    elif exponent < 0 and base == 0:
        raise EvaluationError("zero raised to a negative power")
    return base ** exponent


FUNCTIONS = {
    "abs": (1, 1, lambda arguments: abs(arguments[0])),
    "min": (1, None, lambda arguments: min(arguments)),
    "max": (1, None, lambda arguments: max(arguments)),
    "sqrt": (1, 1, lambda arguments: _sqrt(arguments[0])),
    "floor": (1, 1, lambda arguments: math.floor(arguments[0])),
    "ceil": (1, 1, lambda arguments: math.ceil(arguments[0])),
    "pow": (2, 2, lambda arguments: _power(arguments[0], arguments[1])),
}

def _call(name, arguments):
    """Run the function called name over its arguments."""
    entry = FUNCTIONS.get(name)
    if entry is None:
        raise EvaluationError("there is no function named %r" % (name,))
    minimum, maximum, function = entry
    count = len(arguments)
    if count < minimum:
        raise EvaluationError("%s takes %s, not %d" % (name, _arity_text(minimum, maximum), count))
    return function(arguments)

def _arity_text(minimum, maximum):
    """How many arguments a function takes, in words."""
    word = "argument" if minimum == 1 else "arguments"
    return "%s %d %s" % ("at least" if maximum is None else "exactly", minimum, word)


class Environment:
    """The variable bindings an expression is evaluated against."""

    def __init__(self, variables=None):
        self.variables = dict(variables) if variables else {}

    def define(self, name, value):
        """Bind name to value and return the environment."""
        self.variables[name] = value
        return self

    def lookup(self, name):
        """The value of name, or an EvaluationError when it is not usable."""
        if name not in self.variables:
            raise EvaluationError("the name %r is not defined" % (name,))
        value = self.variables[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvaluationError("the name %r is not a number" % (name,))
        return value
