from werkzeug.security import generate_password_hash

# ==========================================
# INPUT PASSWORD
# ==========================================
password = input("Masukkan password: ")

# ==========================================
# GENERATE HASH
# ==========================================
hash_password = generate_password_hash(password)

# ==========================================
# OUTPUT HASH
# ==========================================
print("\n==============================")
print("HASH PASSWORD:")
print("==============================\n")

print(hash_password)

print("\n==============================")
print("Selesai")
print("==============================")