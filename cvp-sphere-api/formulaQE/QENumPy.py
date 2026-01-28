import pandas as pd
import numpy as np

df = pd.read_excel("quadratic.xlsx")

a = df["a"].values
b = df["b"].values
c = df["c"].values

# Дискриминант
d = b**2 - 4*a*c

# Язгуур (анх NaN)
x1 = np.full_like(d, np.nan, dtype=float)
x2 = np.full_like(d, np.nan, dtype=float)

mask = (d >= 0) & (a != 0)

sqrt_d = np.sqrt(d[mask])
x1[mask] = (-b[mask] + sqrt_d) / (2 * a[mask])
x2[mask] = (-b[mask] - sqrt_d) / (2 * a[mask])

df["d"] = d
df["x1"] = x1
df["x2"] = x2

df.to_excel("result_numpy.xlsx", index=False)
