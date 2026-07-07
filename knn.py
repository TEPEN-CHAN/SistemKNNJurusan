# import numpy as np
# from collections import Counter


# # ==========================================
# # HITUNG EUCLIDEAN DISTANCE
# # ==========================================
# def euclidean_distance(data1, data2):

#     data1 = np.array(data1)
#     data2 = np.array(data2)

#     return np.sqrt(
#         np.sum((data1 - data2) ** 2)
#     )


# # ==========================================
# # PROSES KNN
# # ==========================================
# def knn_predict(data_latih, label_latih, data_uji, k=3):

#     distances = []

#     # ==========================================
#     # HITUNG JARAK SEMUA DATA LATIH
#     # ==========================================
#     for i in range(len(data_latih)):

#         distance = euclidean_distance(
#             data_latih[i],
#             data_uji
#         )

#         distances.append(
#             (distance, label_latih[i])
#         )

#     # ==========================================
#     # URUTKAN DARI JARAK TERKECIL
#     # ==========================================
#     distances.sort(key=lambda x: x[0])

#     # ==========================================
#     # AMBIL K TETANGGA TERDEKAT
#     # ==========================================
#     neighbors = distances[:k]

#     # ==========================================
#     # AMBIL LABEL TETANGGA
#     # ==========================================
#     labels = [label for _, label in neighbors]

#     # ==========================================
#     # VOTING MAYORITAS
#     # ==========================================
#     result = Counter(labels).most_common(1)[0][0]

#     return result

import numpy as np
from collections import Counter

# ==========================================
# HITUNG EUCLIDEAN DISTANCE
# ==========================================
def euclidean_distance(data1, data2):

    data1 = np.array(data1, dtype=float)
    data2 = np.array(data2, dtype=float)

    return np.sqrt(
        np.sum((data1 - data2) ** 2)
    )

# ==========================================
# NORMALISASI MIN-MAX
# ==========================================
def normalize_data(data):

    data = np.array(data, dtype=float)

    min_val = np.min(data, axis=0)
    max_val = np.max(data, axis=0)
    range_val = max_val - min_val
    safe_range = np.where(range_val == 0, 1, range_val)

    return (data - min_val) / safe_range


def normalize_train_test(data_latih, data_uji):

    data_latih = np.array(data_latih, dtype=float)
    data_uji = np.array(data_uji, dtype=float)

    if data_latih.ndim == 1:

        data_latih = data_latih.reshape(1, -1)

    min_val = np.min(data_latih, axis=0)
    max_val = np.max(data_latih, axis=0)
    range_val = max_val - min_val
    safe_range = np.where(range_val == 0, 1, range_val)

    data_latih_normal = (data_latih - min_val) / safe_range
    data_uji_normal = (data_uji - min_val) / safe_range

    return (
        data_latih_normal,
        data_uji_normal,
        min_val,
        max_val,
        range_val
    )


def rounded_list(values):

    return [
        round(float(value), 4)
        for value in values
    ]

# ==========================================
# PROSES KNN
# ==========================================
def knn_predict(
    data_latih,
    label_latih,
    data_uji,
    k=3
):

    # ======================================
    # VALIDASI DATA
    # ======================================
    if len(data_latih) == 0:

        return {
            'hasil': 'Data latih kosong',
            'neighbors': [],
            'confidence': 0,
            'all_distances': [],
            'data_uji_normalisasi': [],
            'min_values': [],
            'max_values': [],
            'range_values': []
        }

    # ======================================
    # VALIDASI NILAI K
    # ======================================
    if k > len(data_latih):

        k = len(data_latih)

    if k < 1:

        k = 1

    (
        data_latih_normal,
        data_uji_normal,
        min_values,
        max_values,
        range_values
    ) = normalize_train_test(
        data_latih,
        data_uji
    )

    distances = []

    # ======================================
    # HITUNG JARAK SETELAH NORMALISASI
    # ======================================
    for i in range(len(data_latih)):

        distance = euclidean_distance(
            data_latih_normal[i],
            data_uji_normal
        )

        distances.append({

            'index': i,
            'distance': round(distance, 4),
            'label': label_latih[i],
            'fitur': data_latih[i],
            'fitur_normalisasi': rounded_list(data_latih_normal[i])

        })

    # ======================================
    # SORTING JARAK
    # ======================================
    distances = sorted(
        distances,
        key=lambda x: x['distance']
    )

    # ======================================
    # AMBIL TETANGGA TERDEKAT
    # ======================================
    neighbors = distances[:k]

    # ======================================
    # AMBIL LABEL
    # ======================================
    labels = [
        n['label']
        for n in neighbors
    ]

    # ======================================
    # VOTING MAYORITAS
    # ======================================
    voting = Counter(labels)

    hasil = voting.most_common(1)[0][0]

    # ======================================
    # HITUNG CONFIDENCE
    # ======================================
    jumlah_vote_terbanyak = voting.most_common(1)[0][1]
    jumlah_kelas = max(2, len(set(label_latih)))
    alpha = 0.1

    # Smoothing mencegah confidence menjadi 100% mutlak saat semua tetangga
    # terdekat memiliki label yang sama, terutama ketika nilai K kecil.
    confidence = round(

        (
            (jumlah_vote_terbanyak + alpha)
            / (k + (alpha * jumlah_kelas))
        ) * 100,

        2
    )

    # ======================================
    # RETURN HASIL
    # ======================================
    return {

        'hasil': hasil,

        'confidence': confidence,

        'neighbors': neighbors,

        'all_distances': distances,

        'data_uji_normalisasi': rounded_list(data_uji_normal),

        'min_values': rounded_list(min_values),

        'max_values': rounded_list(max_values),

        'range_values': rounded_list(range_values)

    }
