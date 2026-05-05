from __future__ import annotations


def normalize_numbers(values: list[int]) -> list[int]:
    result: list[int] = []
    for value in values:
        if value % 2 == 0:
            result.append(value // 2)
        else:
            result.append(value * 3 + 1)
    return result


def summarize(values: list[int]) -> dict[str, int]:
    total = 0
    maximum = values[0]
    for value in values:
        total += value
        if value > maximum:
            maximum = value
    return {"total": total, "maximum": maximum}


def main() -> None:
    raw_values = [3, 8, 5, 12]
    normalized = normalize_numbers(raw_values)
    summary = summarize(normalized)
    print(f"normalized={normalized}")
    print(f"summary={summary}")


if __name__ == "__main__":
    main()
