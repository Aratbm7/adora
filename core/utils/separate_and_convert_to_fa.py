from persian_tools import separator, digits


def separate_digits_and_convert_to_fa(digit: int) -> str:
    return separator.add(digits.convert_to_fa(int(digit)))
