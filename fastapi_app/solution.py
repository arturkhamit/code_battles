import sys


def is_balanced(s):
    stack = []

    for char in s:
        if char == "(":
            # Открывающую скобку кладем в стек
            stack.append(char)
        elif char == ")":
            # Если пришла закрывающая, а стек пуст — баланс нарушен
            if not stack:
                return False
            stack.pop()
        else:
            # Если встретился ЛЮБОЙ другой символ (например, '*'), строка невалидна
            return False

    # Если в конце стек пуст, значит все открытые скобки закрылись
    return len(stack) == 0


def main():
    # Считываем данные построчно, чтобы корректно обработать все символы
    input_data = sys.stdin.read().split()

    if not input_data:
        return

    # Первое число — количество тестовых случаев
    t = int(input_data[0])

    # Обрабатываем каждый тест
    for i in range(1, t + 1):
        if i < len(input_data):
            s = input_data[i]
            if is_balanced(s):
                print("YES")
            else:
                print("NO")


if __name__ == "__main__":
    main()
