import numpy as np
from scipy.optimize import linprog

# ---------------------------
# 1. Parameters (from paper example)
# ---------------------------
p = np.array([700.0, 1120.0, 4480.0])
c = np.array([280.0, 420.0, 2240.0])
F = 14000.0

xmin = np.array([6.66, 4.0, 1.25])
xmax = np.array([26.66, 16.0, 5.0])

d = p - c
norm_d = np.linalg.norm(d)

# ---------------------------
# 2. Objective: max r -> min (-r)
# ---------------------------
c_obj = np.array([0, 0, 0, -1])  # [x1, x2, x3, r]

# ---------------------------
# 3. Inequality constraints A_ub x <= b_ub
# ---------------------------
A = []
b = []

# Profit constraint:
# d·x - norm(d)*r >= F  ->  -d·x + norm(d)*r <= -F
A.append(np.hstack([-d, norm_d]))
b.append(-F)

# xj - r >= xmin_j  ->  -xj + r <= -xmin_j
for j in range(3):
    row = np.zeros(4)
    row[j] = -1
    row[3] = 1
    A.append(row)
    b.append(-xmin[j])

# xj + r <= xmax_j
for j in range(3):
    row = np.zeros(4)
    row[j] = 1
    row[3] = 1
    A.append(row)
    b.append(xmax[j])

A = np.array(A)
b = np.array(b)

# ---------------------------
# 4. Variable bounds
# ---------------------------
bounds = [
    (None, None),  # x1
    (None, None),  # x2
    (None, None),  # x3
    (0, None)      # r >= 0
]

# ---------------------------
# 5. Solve LP
# ---------------------------
result = linprog(
    c=c_obj,
    A_ub=A,
    b_ub=b,
    bounds=bounds,
    method="highs"
)

# ---------------------------
# 6. Output
# ---------------------------
if result.success:
    x1, x2, x3, r = result.x
    print("Optimal solution:")
    print(f"x1 = {x1:.3f}")
    print(f"x2 = {x2:.3f}")
    print(f"x3 = {x3:.3f}")
    print(f"r  = {r:.3f}")

    print("\nProfitability interval:")
    print(f"{x1-r:.2f} <= x1 <= {x1+r:.2f}")
    print(f"{x2-r:.2f} <= x2 <= {x2+r:.2f}")
    print(f"{x3-r:.2f} <= x3 <= {x3+r:.2f}")
else:
    print("Optimization failed:", result.message)
