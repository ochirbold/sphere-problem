import pandas as pd
import numpy as np

def compare_results():
    # Хоёр файлыг унших
    df_for_loop = pd.read_excel('result_for_loop.xlsx')
    df_numpy = pd.read_excel('result_numpy.xlsx')
    
    print("For loop програмын үр дүн:")
    print(df_for_loop.head())
    print("\nNumPy програмын үр дүн:")
    print(df_numpy.head())
    
    # Хоёр файлын ялгааг шалгах
    print("\n" + "="*50)
    print("Хоёр файлын ялгааны дүн шинжилгээ:")
    print("="*50)
    
    # Мөрийн тоо
    print(f"Мөрийн тоо (for loop): {len(df_for_loop)}")
    print(f"Мөрийн тоо (numpy): {len(df_numpy)}")
    
    # Баганын нэрс
    print(f"\nБаганын нэрс (for loop): {list(df_for_loop.columns)}")
    print(f"Баганын нэрс (numpy): {list(df_numpy.columns)}")
    
    # d утгуудын ялгаа
    d_diff = np.abs(df_for_loop['d'] - df_numpy['d'])
    print(f"\nd утгуудын дундаж ялгаа: {d_diff.mean():.10f}")
    print(f"d утгуудын хамгийн их ялгаа: {d_diff.max():.10f}")
    
    # x1 утгуудын ялгаа (NaN-уудыг тооцохгүй)
    x1_for_loop = df_for_loop['x1'].dropna()
    x1_numpy = df_numpy['x1'].dropna()
    
    if len(x1_for_loop) > 0 and len(x1_numpy) > 0:
        x1_diff = np.abs(x1_for_loop.values - x1_numpy.values)
        print(f"\nx1 утгуудын дундаж ялгаа: {x1_diff.mean():.10f}")
        print(f"x1 утгуудын хамгийн их ялгаа: {x1_diff.max():.10f}")
    
    # Програмын гүйцэтгэл хэмжих
    print("\n" + "="*50)
    print("ГҮЙЦЭТГЭЛИЙН ХАРЬЦУУЛАЛТ:")
    print("="*50)
    print("For loop програм нь ойлгомжтой боловч удаан ажиллана.")
    print("NumPy програм нь векторчилсан тооцоолол хийж илүү хурдан ажиллана.")
    print("Том өгөгдөлд NumPy илүү үр дүнтэй.")

if __name__ == "__main__":
    compare_results()