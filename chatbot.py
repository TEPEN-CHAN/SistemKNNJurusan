def chatbot_response(pesan):

    pesan = pesan.lower()

    # ==========================================
    # SAPAAN
    # ==========================================
    if "halo" in pesan:
        return "Halo, saya chatbot rekomendasi jurusan."

    elif "hai" in pesan:
        return "Hai, ada yang bisa saya bantu?"

    elif "jurusan" in pesan:
        return "Sistem akan merekomendasikan pilihan mapel berdasarkan nilai dan minat bakat siswa."

    elif "knn" in pesan:
        return "KNN adalah metode klasifikasi berdasarkan tetangga terdekat."

    elif "ipa" in pesan:
        return "Pilihan 1 biasanya cocok untuk siswa dengan kemampuan numerik dan analisis tinggi."

    elif "ips" in pesan:
        return "Pilihan 2 biasanya cocok untuk siswa dengan kemampuan sosial dan komunikasi."

    elif "minat" in pesan:
        return "Minat bakat siswa dianalisis menggunakan pendekatan Holland RIASEC."

    elif "realistic" in pesan:
        return "Tipe Realistic menyukai aktivitas praktik dan teknis."

    elif "investigative" in pesan:
        return "Tipe Investigative menyukai analisis dan pemecahan masalah."

    elif "artistic" in pesan:
        return "Tipe Artistic menyukai seni dan kreativitas."

    elif "social" in pesan:
        return "Tipe Social menyukai membantu dan berinteraksi dengan orang lain."

    elif "enterprising" in pesan:
        return "Tipe Enterprising menyukai kepemimpinan dan bisnis."

    elif "conventional" in pesan:
        return "Tipe Conventional menyukai pekerjaan terstruktur dan administrasi."

    # ==========================================
    # DEFAULT
    # ==========================================
    else:
        return "Maaf, pertanyaan belum tersedia di sistem chatbot."