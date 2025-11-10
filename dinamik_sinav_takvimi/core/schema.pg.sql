-- PostgreSQL sürümü (Türkçe ASCII isimlerle)

CREATE TABLE IF NOT EXISTS bolumler(
  id SERIAL PRIMARY KEY,
  ad TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS kullanicilar(
  id SERIAL PRIMARY KEY,
  eposta TEXT UNIQUE NOT NULL,
  sifre_hash TEXT NOT NULL,
  rol TEXT NOT NULL CHECK (rol IN ('admin','koordinator')),
  bolum_id INT REFERENCES bolumler(id)
);

CREATE TABLE IF NOT EXISTS derslikler(
  id SERIAL PRIMARY KEY,
  bolum_id INT NOT NULL REFERENCES bolumler(id),
  kod TEXT NOT NULL,
  ad TEXT NOT NULL,
  kapasite INT NOT NULL CHECK (kapasite>0),
  satir INT NOT NULL CHECK (satir>0),
  sutun INT NOT NULL CHECK (sutun>0),
  sira_grup INT NOT NULL CHECK (sira_grup IN (2,3))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_derslikler_kod_bolum ON derslikler(bolum_id, kod);

CREATE TABLE IF NOT EXISTS dersler(
  id SERIAL PRIMARY KEY,
  bolum_id INT NOT NULL REFERENCES bolumler(id),
  kod TEXT NOT NULL,
  ad TEXT NOT NULL,
  sinif_yili INT NOT NULL CHECK (sinif_yili BETWEEN 1 AND 5),
  secmeli BOOLEAN NOT NULL,
  ogretim_uyesi TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dersler_kod_bolum ON dersler(bolum_id, kod);

CREATE TABLE IF NOT EXISTS ogrenciler(
  id SERIAL PRIMARY KEY,
  bolum_id INT NOT NULL REFERENCES bolumler(id),
  numara TEXT NOT NULL,
  ad TEXT NOT NULL,
  sinif_yili INT NOT NULL CHECK (sinif_yili BETWEEN 1 AND 5)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ogrenciler_numara_bolum ON ogrenciler(bolum_id, numara);

CREATE TABLE IF NOT EXISTS kayitlar(
  ogrenci_id INT NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
  ders_id INT NOT NULL REFERENCES dersler(id) ON DELETE CASCADE,
  PRIMARY KEY(ogrenci_id, ders_id)
);

CREATE TABLE IF NOT EXISTS sinav_zamanlari(
  id SERIAL PRIMARY KEY,
  sinav_turu TEXT NOT NULL CHECK (sinav_turu IN ('vize','final','but')),
  gun DATE NOT NULL,
  baslama_saat TIME NOT NULL,
  sure_dk INT NOT NULL CHECK (sure_dk>0)
);

CREATE TABLE IF NOT EXISTS sinavlar(
  id SERIAL PRIMARY KEY,
  ders_id INT NOT NULL REFERENCES dersler(id),
  zaman_id INT NOT NULL REFERENCES sinav_zamanlari(id)
);

CREATE TABLE IF NOT EXISTS sinav_derslikleri(
  id SERIAL PRIMARY KEY,
  sinav_id INT NOT NULL REFERENCES sinavlar(id) ON DELETE CASCADE,
  derslik_id INT NOT NULL REFERENCES derslikler(id),
  kota INT NOT NULL CHECK (kota>0)
);

CREATE TABLE IF NOT EXISTS oturma_koltuklari(
  id SERIAL PRIMARY KEY,
  sinav_derslik_id INT NOT NULL REFERENCES sinav_derslikleri(id) ON DELETE CASCADE,
  r INT NOT NULL,
  c INT NOT NULL,
  ogrenci_id INT REFERENCES ogrenciler(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_oturma_coord
  ON oturma_koltuklari (sinav_derslik_id, r, c);

CREATE TABLE IF NOT EXISTS kisitlar(
  id SMALLINT PRIMARY KEY DEFAULT 1,
  min_bekleme_dk INT NOT NULL DEFAULT 15,
  varsayilan_sure_dk INT NOT NULL DEFAULT 75,
  paralel_yok BOOLEAN NOT NULL DEFAULT FALSE,
  haric_gunler TEXT[] DEFAULT ARRAY[]::TEXT[]
);
