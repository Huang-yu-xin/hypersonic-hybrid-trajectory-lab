class ConstantKControl:
    def __init__(self, value: float):
        if value <= 0.0:
            raise ValueError("K must be positive.")

        self.value = float(value)

    def __call__(self, t, state):
        return self.value