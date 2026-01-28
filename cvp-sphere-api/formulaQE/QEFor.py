import pandas as pd
import math

# Excel унших
df = pd.read_excel("quadratic.xlsx")

# Шинэ баганууд
df["d"] = None
df["x1"] = None
df["x2"] = None

for i in range(len(df)):
    a = df.loc[i, "a"]
    b = df.loc[i, "b"]
    c = df.loc[i, "c"]

    d = b**2 - 4*a*c
    df.loc[i, "d"] = d

    if d >= 0 and a != 0:
        sqrt_d = math.sqrt(d)
        df.loc[i, "x1"] = (-b + sqrt_d) / (2*a)
        df.loc[i, "x2"] = (-b - sqrt_d) / (2*a)
    else:
        df.loc[i, "x1"] = None
        df.loc[i, "x2"] = None

# Excel-д хадгалах
df.to_excel("result_for_loop.xlsx", index=False)
