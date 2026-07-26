arr_1 = [64, 34, 25, 12, 22, 11, 90]
print("Input array: ", arr_1)

def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

print(f"Bubble Sorted array: {bubble_sort(arr_1.copy())}")


def insertion_sort(arr):
    n = len(arr)
    for i in range(1, n):
        key = arr[i]
        j = i
        while j>0 and key < arr[j-1]:
            arr[j] = arr[j-1]
            j -= 1
        arr[j] = key
    return arr

print(f"Insertion Sorted array: {insertion_sort(arr_1.copy())}")