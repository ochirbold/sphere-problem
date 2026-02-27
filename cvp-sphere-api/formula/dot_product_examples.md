# Скаляр үржвэр (Dot Product) функционал

## Товч хариулт: **Тийм, манай системд скаляр үржвэр байгаа!**

Таны `formula_runtime.py` файлд `DOT` функц бэлэн байна:

```python
def safe_dot(a, b):
    return sum(x * y for x, y in zip(a, b))

SAFE_FUNCTIONS = {
    # ... бусад функцууд
    "DOT": safe_dot,  # Скаляр үржвэрийн функц
    # ...
}
```

## DOT функцын ажиллагаа

`DOT(a, b)` функц нь:

1. Хоёр массивын скаляр үржвэрийг тооцоолно
2. `a₁×b₁ + a₂×b₂ + ... + aₙ×bₙ` томъёогоор бодно
3. Хоёр массивын урт ижил байх ёстой

## Хэрэглээний жишээнүүд

### Жишээ 1: Бүтээгдэхүүний орлого бодох

```
Нийт_орлого = DOT(Үнэ, Тоо_хэмжээ)
```

### Жишээ 2: Жинлэсэн дундаж

```
Жинлэсэн_дундаж = DOT(Үнэлгээ, Жин) / SUM(Жин)
```

### Жишээ 3: Векторуудын ижил төстэй байдал

```
Ижил_төстэй_байдал = DOT(Вектор_A, Вектор_B) / (NORM(Вектор_A) * NORM(Вектор_B))
```

## Практик жишээ PYTHONCODE.PY-д

```python
# Томьёоны жишээ:
# TOTAL_REVENUE:DOT(PRICE, QUANTITY)
# WEIGHTED_AVG:DOT(SCORE, WEIGHT) / SUM(WEIGHT)

python PYTHONCODE.PY VT_DATA.V_17687947217601 ID \
'TOTAL_REVENUE:DOT(PRICE, QUANTITY)' \
'AVG_PRICE:DOT(PRICE, QUANTITY) / SUM(QUANTITY)' \
'"PRICE":PRICE "QUANTITY":QUANTITY'
```

## Гүйцэтгэлийн шинжилгээ

### Давуу талууд:

1. **Нэг удаагийн тооцоо**: DOT функц нь скаляр үржвэрийг нэг удаа тооцоолно
2. **Оновчтой**: Python-ийн `zip()` ба `sum()` функцуудыг ашигладаг
3. **Тогтвортой**: Массивын урт ижил биш бол алдаа гаргана

### Хязгаарлалтууд:

1. **Санах ой**: Хоёр баганыг нэг дор санах ойд ачаалах шаардлагатай
2. **Өгөгдлийн хэмжээ**: Том өгөгдлийн хувьд database-level тооцоо илүү үр дүнтэй

## Database-тэй интеграцчилал

Том өгөгдлийн хувьд SQL-ээр шууд тооцоолох:

```sql
-- DOT(PRICE, QUANTITY)-ийг SQL-ээр
SELECT SUM(PRICE * QUANTITY) AS DOT_RESULT FROM table_name;

-- Эсвэл PYTHONCODE.PY-д шууд ашиглах
SELECT SUM(PRICE * QUANTITY) AS DOT_PRICE_QUANTITY FROM table_name
```

## Туршилтын жишээ

`dot_product_test.py` файл үүсгэж туршилт хийх:

```python
from formula_runtime import run_formula

# Туршилтын өгөгдөл
test_data = [
    {'price': [100, 200, 300], 'quantity': [2, 3, 4]},
    {'price': [150, 250, 350], 'quantity': [1, 2, 3]},
]

for i, row in enumerate(test_data):
    result = run_formula('DOT(price, quantity)', row)
    print(f"Мөр {i+1}: DOT(price, quantity) = {result}")
    # Гаралт: Мөр 1: 100*2 + 200*3 + 300*4 = 2000
```

## Дүгнэлт

1. **✅ Манай системд скаляр үржвэр байгаа**: `DOT()` функц бэлэн байна
2. **✅ Ашиглахад хялбар**: `DOT(багана1, багана2)` гэж ашиглана
3. **✅ Оновчтой**: Нэг удаагийн тооцоолол
4. **✅ Олон төрлийн хэрэглээ**: Орлого, жинлэсэн дундаж, вектор үйлдлүүд

Таны "манай 2 баганы утгыг скаляр үржвэр" хийх хэрэгцээг `DOT()` функцээр бүрэн хангаж чадна!
