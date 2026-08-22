# Calculator Module User Manual

## Overview
The `Calculator` class provides robust standard mathematical operations including addition, subtraction, multiplication, division, exponentiation, and modulo operations with built-in error handling for invalid operations like division or modulo by zero.

## API Reference

### `Calculator.add(a, b)`
- **Description**: Returns the sum of `a` and `b` (`a + b`).
- **Parameters**: `a` (int/float), `b` (int/float)
- **Returns**: int/float

### `Calculator.subtract(a, b)`
- **Description**: Returns the difference of `a` and `b` (`a - b`).
- **Parameters**: `a` (int/float), `b` (int/float)
- **Returns**: int/float

### `Calculator.multiply(a, b)`
- **Description**: Returns the product of `a` and `b` (`a * b`).
- **Parameters**: `a` (int/float), `b` (int/float)
- **Returns**: int/float

### `Calculator.divide(a, b)`
- **Description**: Returns the division of `a` by `b` (`a / b`).
- **Parameters**: `a` (int/float), `b` (int/float)
- **Returns**: float
- **Raises**: `ValueError` if `b == 0`

### `Calculator.power(a, b)`
- **Description**: Returns `a` raised to the power of `b` (`a ** b`).
- **Parameters**: `a` (int/float), `b` (int/float)
- **Returns**: int/float

### `Calculator.modulo(a, b)`
- **Description**: Returns the remainder of `a` divided by `b` (`a % b`).
- **Parameters**: `a` (int/float), `b` (int/float)
- **Returns**: int/float
- **Raises**: `ValueError` if `b == 0`

## Running Tests
To verify functionality, run unittest:
```bash
python -m unittest test_calculator.py
```
