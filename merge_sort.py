def merge_sort(arr):
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])

    return merge(left, right)


def merge(left, right):
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result


def test_merge_sort():
    sample = [38, 27, 43, 3, 9, 82, 10]
    expected = sorted(sample)
    sorted_arr = merge_sort(sample)
    assert sorted_arr == expected, f"Expected {expected}, got {sorted_arr}"
    print("Test passed! Sorted array:", sorted_arr)


if __name__ == "__main__":
    test_merge_sort()
