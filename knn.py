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
# NORMALISASI DATA
# OPTIONAL
# ==========================================
def normalize_data(data):

    data = np.array(data, dtype=float)

    min_val = np.min(data, axis=0)
    max_val = np.max(data, axis=0)

    return (
        (data - min_val) /
        (max_val - min_val + 0.0001)
    )

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
            'confidence': 0
        }

    # ======================================
    # VALIDASI NILAI K
    # ======================================
    if k > len(data_latih):

        k = len(data_latih)

    distances = []

    # ======================================
    # HITUNG JARAK
    # ======================================
    for i in range(len(data_latih)):

        distance = euclidean_distance(
            data_latih[i],
            data_uji
        )

        distances.append({

            'distance': round(distance, 4),
            'label': label_latih[i],
            'fitur': data_latih[i]

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
    confidence = round(

        (
            voting.most_common(1)[0][1]
            / k
        ) * 100,

        2
    )

    # ======================================
    # RETURN HASIL
    # ======================================
    return {

        'hasil': hasil,

        'confidence': confidence,

        'neighbors': neighbors

    }