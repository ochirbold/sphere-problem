import pandas as pd
import numpy as np

def solve_quadratic_numpy():
    # Excel файлыг унших
    df = pd.read_excel('quadratic.xlsx')
    
    # NumPy array-ууд руу хөрвүүлэх
    a = df['a'].values
    b = df['b'].values
    c = df['c'].values
    
    # Дискриминант тооцоолох (векторчилсан)
    d = b**2 - 4*a*c
    
    # Шийдүүдийг тооцоолох
    # Эхлээд бүх утгуудын хувьд тооцоолох
    sqrt_d = np.sqrt(np.where(d >= 0, d, np.nan))
    
    # x1, x2 тооцоолох
    x1 = np.where(d >= 0, (-b + sqrt_d) / (2*a), np.nan)
    x2 = np.where(d >= 0, (-b - sqrt_d) / (2*a), np.nan)
    
    # d < 0 үед None утга оруулах
    x1 = np.where(d < 0, None, x1)
    x2 = np.where(d < 0, None, x2)
    
    # Үр дүнгийн DataFrame үүсгэх
    result_df = pd.DataFrame({
        'a': a,
        'b': b,
        'c': c,
        'd': d,
        'x1': x1,
        'x2': x2
    })
    
    # Excel файлд хадгалах
    result_df.to_excel('result_numpy.xlsx', index=False)
    print("Үр дүн result_numpy.xlsx файлд хадгалагдлаа.")
    
    return result_df

if __name__ == "__main__":
    result = solve_quadratic_numpy()
    print("Эхний 5 мөр:")
    print(result.head())