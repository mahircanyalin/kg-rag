import requests
import os

# SEC, kim olduğunu belirten bir User-Agent ister (zorunlu).
# Kendi adını ve e-postanı yaz — SEC bunu istiyor, spam değil.
HEADERS = {"User-Agent": "mahir.yalin@outlook.com"}

def get_latest_10k_url(cik: str):
    """Şirketin CIK'inden en son 10-K dosyasının URL'ini bulur."""
    # CIK 10 haneye tamamlanır (başına sıfır eklenir)
    cik_padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    # Son başvurular "recent" altında, sütun sütun (paralel diziler) tutulur
    recent = data["filings"]["recent"]
    forms = recent["form"]                    # ["10-K", "8-K", ...]
    accession_numbers = recent["accessionNumber"]
    primary_docs = recent["primaryDocument"]

    # İlk 10-K'yı bul (en yeni en başta)
    for i, form in enumerate(forms):
        if form == "10-K":
            accession = accession_numbers[i].replace("-", "")
            doc = primary_docs[i]
            # Dosyanın tam URL'i
            file_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{accession}/{doc}"
            )
            return file_url

    raise ValueError("Bu şirket için 10-K bulunamadı")


def download_filing(url: str, save_path: str):
    """Dosyayı indirip diske kaydeder."""
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(resp.text)

    print(f"İndirildi: {save_path} ({len(resp.text):,} karakter)")
    return save_path


if __name__ == "__main__":
    # Apple: CIK 320193
    apple_cik = "320193"

    url = get_latest_10k_url(apple_cik)
    print("Bulunan 10-K URL:", url)

    download_filing(url, "data/apple_10k.html")