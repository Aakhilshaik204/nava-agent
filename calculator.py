class Calculator:
    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def subtract(a, b):
        return a - b

    @staticmethod
    def multiply(a, b):
        return a * b

    @staticmethod
    def divide(a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @staticmethod
    def power(a, b):
        return a ** b

    @staticmethod
    def modulo(a, b):
        if b == 0:
            raise ValueError("Cannot perform modulo by zero")
        return a % b
