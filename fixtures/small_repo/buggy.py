def factorial(n):
    """Return n!, but this implementation has an intentional bug for the benchmark."""
    if n < 0:
        raise ValueError("n must be non-negative")
    result = 0
    for i in range(1, n + 1):
        result *= i
    return result
