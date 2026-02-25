import pandas as pd
import math

def solve_quadratic_for_loop():
    # Excel файлыг унших
    df = pd.read_excel('quadratic.xlsx')
    
    # Үр дүн хадгалах DataFrame үүсгэх
    results = []
    
    # Мөр бүрээр давтах
    for index, row in df.iterrows():
        a = row['a']
        b = row['b']
        c = row['c']
        
        # Дискриминант тооцоолох
        d = b**2 - 4*a*c
        
        if d > 0:
            # 2 шийдтэй
            x1 = (-b + math.sqrt(d)) / (2*a)
            x2 = (-b - math.sqrt(d)) / (2*a)
        elif d == 0:
            # 1 шийдтэй
            x1 = x2 = -b / (2*a)
        else:
            # Бодит шийдгүй
            x1 = x2 = None
        
        # Үр дүнг хадгалах
        results.append({
            'a': a,
            'b': b,
            'c': c,
            'd': d,
            'x1': x1,
            'x2': x2
        })
    
    # DataFrame үүсгэх
    result_df = pd.DataFrame(results)
    
    # Excel файлд хадгалах
    result_df.to_excel('esult_for_loop.xlsx', index=False)
    print("Үр дүн result_for_loop.xlsx файлд хадгалагдлаа.")
    
    return result_df

if __name__ == "__main__":
    result = solve_quadratic_for_loop()
    print("Эхний 5 мөр:")
    print(result.head())