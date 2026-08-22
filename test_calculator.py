import unittest
from calculator import Calculator

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(Calculator.add(2, 3), 5)
        self.assertEqual(Calculator.add(-1, 1), 0)
        self.assertAlmostEqual(Calculator.add(0.1, 0.2), 0.3, places=7)

    def test_subtract(self):
        self.assertEqual(Calculator.subtract(5, 3), 2)
        self.assertEqual(Calculator.subtract(1, 5), -4)

    def test_multiply(self):
        self.assertEqual(Calculator.multiply(3, 4), 12)
        self.assertEqual(Calculator.multiply(-2, 3), -6)
        self.assertEqual(Calculator.multiply(0, 5), 0)

    def test_divide(self):
        self.assertEqual(Calculator.divide(10, 2), 5)
        self.assertEqual(Calculator.divide(5, 2), 2.5)
        with self.assertRaises(ValueError):
            Calculator.divide(5, 0)

    def test_power(self):
        self.assertEqual(Calculator.power(2, 3), 8)
        self.assertEqual(Calculator.power(5, 0), 1)

    def test_modulo(self):
        self.assertEqual(Calculator.modulo(10, 3), 1)
        with self.assertRaises(ValueError):
            Calculator.modulo(10, 0)

if __name__ == '__main__':
    unittest.main()
