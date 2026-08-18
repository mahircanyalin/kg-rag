from bs4 import BeautifulSoup
import re
import json
import os


def html_to_text(html_path: str) -> str:
    """HTML dosyasını düz metne çevirir, etiketleri atar."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # Script ve style bloklarını tamamen at (içlerinde metin yok)
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Sadece görünür metni al
    text = soup.get_text(separator=" ")

    # Fazla boşlukları temizle (HTML'den gelen bol whitespace)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150):
    """
    Metni parçalara böler.
    - chunk_size: her parçanın yaklaşık karakter sayısı
    - overlap: parçalar arası örtüşme (bağlam kopmasın diye)
    """
    chunks = []
    start = 0
    chunk_id = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        chunks.append({
            "chunk_id": f"chunk_{chunk_id:04d}",
            "text": chunk.strip(),
            "start_char": start,
            "end_char": end,
        })

        chunk_id += 1
        # Bir sonraki parça, overlap kadar geriden başlar
        start = end - overlap

    return chunks


if __name__ == "__main__":
    # 1. HTML'i düz metne çevir
    text = html_to_text("data/apple_10k.html")
    print(f"Temizlenmiş metin: {len(text):,} karakter")

    # 2. Parçalara böl
    chunks = chunk_text(text)
    print(f"Toplam parça (chunk): {len(chunks)}")

    # 3. Sonucu JSON olarak kaydet (sonraki adımlarda kullanacağız)
    os.makedirs("data", exist_ok=True)
    with open("data/apple_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print("Kaydedildi: data/apple_chunks.json")

    # İlk parçaya göz at (kontrol için)
    print("\n--- İlk parça örneği ---")
    print(chunks[0]["text"][:300])