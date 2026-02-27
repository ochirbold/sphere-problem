import time
import subprocess
import sys

def run_all_comparisons():
    print("КВАДРАТ ТЭГШИТГЭЛИЙН ШИЙДЭЛ ХАРЬЦУУЛАЛТ")
    print("="*50)
    
    # 1. For loop програм ажиллуулах
    print("\n1. For loop програм ажиллаж байна...")
    start_time = time.time()
    
    try:
        exec(open('ComparisonAlgo/quadratic_for_loop.py').read())
        for_loop_time = time.time() - start_time
        print(f"For loop програм {for_loop_time:.4f} секундэд дууслаа.")
    except Exception as e:
        print(f"Алдаа гарлаа: {e}")
        for_loop_time = None
    
    # 2. NumPy програм ажиллуулах
    print("\n2. NumPy програм ажиллаж байна...")
    start_time = time.time()
    
    try:
        exec(open('ComparisonAlgo/quadratic_numpy.py').read())
        numpy_time = time.time() - start_time
        print(f"NumPy програм {numpy_time:.4f} секундэд дууслаа.")
    except Exception as e:
        print(f"Алдаа гарлаа: {e}")
        numpy_time = None
    
    # 3. Харьцуулалт хийх
    print("\n3. Үр дүнг харьцуулж байна...")
    try:
        exec(open('ComparisonAlgo/compare_results.py').read())
    except Exception as e:
        print(f"Алдаа гарлаа: {e}")
    
    # Гүйцэтгэлийн харьцуулалт
    if for_loop_time and numpy_time:
        print("\n" + "="*50)
        print("ГҮЙЦЭТГЭЛИЙН ХУГАЦААНЫ ХАРЬЦУУЛАЛТ:")
        print("="*50)
        print(f"For loop програм: {for_loop_time:.4f} секунд")
        print(f"NumPy програм: {numpy_time:.4f} секунд")
        
        if for_loop_time > 0:
            speedup = for_loop_time / numpy_time
            print(f"\nNumPy програм {speedup:.2f} дахин хурдан ажилласан!")
    
    print("\n" + "="*50)
    print("БҮХ ПРОГРАМ АМЖИЛТТАЙ ДУУСЛАА!")
    print("="*50)

if __name__ == "__main__":
    run_all_comparisons()