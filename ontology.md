# Ontoloji — SEC 10-K Knowledge Graph

## Karar: Yerel embedding (sentence-transformers, 384 boyut) kullanılıyor

## Varlık Tipleri (7)
- Company        : Şirketin kendisi ve diğer şirketler
- Person         : Yöneticiler, önemli kişiler
- Product        : Ürün ve hizmetler (iPhone, Services...)
- Location        : Coğrafi bölgeler, ülkeler (China, Europe...)
- RiskFactor     : Riskler (tedarik riski, güvenlik riski...)
- Regulator      : Düzenleyici kurumlar (EU Commission, SEC...)
- BusinessSegment: İş segmentleri (Americas, Greater China...)

## İlişki Tipleri (9)
- OPERATES_IN     : Company -> Location/Segment
- DEPENDS_ON      : Company -> Company/Location (tedarik bağımlılığı)
- MANUFACTURES_IN : Company -> Location
- PRODUCES        : Company -> Product
- FACES_RISK      : Company -> RiskFactor
- REGULATED_BY    : Company -> Regulator
- COMPETES_WITH   : Company -> Company
- HAS_EXECUTIVE   : Company -> Person
- ACQUIRED        : Company -> Company