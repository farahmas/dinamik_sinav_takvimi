

/*schema.sqlite.sql*/

PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bolumler(
  id   INTEGER PRIMARY KEY,
  ad   TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS kullanicilar(
  id           INTEGER PRIMARY KEY,
  eposta       TEXT UNIQUE NOT NULL,
  sifre_hash   TEXT NOT NULL,
  rol          TEXT NOT NULL CHECK (rol IN ('admin','koordinator')),
  bolum_id     INTEGER,                              
  FOREIGN KEY (bolum_id) REFERENCES bolumler(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS derslikler(
  id         INTEGER PRIMARY KEY,
  bolum_id   INTEGER NOT NULL,
  kod        TEXT NOT NULL,                          
  ad         TEXT NOT NULL,                          
  kapasite   INTEGER NOT NULL CHECK (kapasite > 0),
  satir      INTEGER NOT NULL CHECK (satir    > 0),  
  sutun      INTEGER NOT NULL CHECK (sutun    > 0),  
  sira_grup  INTEGER NOT NULL CHECK (sira_grup IN (2,3,4)),
  UNIQUE (bolum_id, kod),
  FOREIGN KEY (bolum_id) REFERENCES bolumler(id) ON DELETE CASCADE
);



CREATE TABLE IF NOT EXISTS dersler(
  id          INTEGER PRIMARY KEY,
  bolum_id    INTEGER NOT NULL,
  kod         TEXT NOT NULL,                         
  ad          TEXT NOT NULL,
  sinif_yili  INTEGER NOT NULL CHECK (sinif_yili BETWEEN 1 AND 5),
  secmeli     INTEGER NOT NULL CHECK (secmeli IN (0,1)),  -- 0: Zorunlu, 1: Seçmeli
  ogretim_uyesi TEXT NOT NULL,
  UNIQUE (bolum_id, kod),
  FOREIGN KEY (bolum_id) REFERENCES bolumler(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ogrenciler(
  id          INTEGER PRIMARY KEY,
  bolum_id    INTEGER NOT NULL,
  kod         TEXT NOT NULL,                         
  ad          TEXT NOT NULL,
  sinif_yili  INTEGER NOT NULL CHECK (sinif_yili BETWEEN 1 AND 5),
  UNIQUE (kod),
  FOREIGN KEY (bolum_id) REFERENCES bolumler(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS kayitlar(
  ogrenci_id  INTEGER NOT NULL,
  ders_id     INTEGER NOT NULL,
  PRIMARY KEY (ogrenci_id, ders_id),
  FOREIGN KEY (ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE,
  FOREIGN KEY (ders_id)    REFERENCES dersler(id)    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sinav_zamanlari(
  id            INTEGER PRIMARY KEY,
  sinav_turu    TEXT NOT NULL CHECK (sinav_turu IN ('vize','final','but')),
  gun           TEXT NOT NULL,            
  baslama_saat  TEXT NOT NULL,            
  sure_dk       INTEGER NOT NULL CHECK (sure_dk > 0)
);


CREATE TABLE IF NOT EXISTS sinavlar(
  id         INTEGER PRIMARY KEY,
  ders_id    INTEGER NOT NULL,
  zaman_id   INTEGER NOT NULL,
  UNIQUE (ders_id, zaman_id),
  FOREIGN KEY (ders_id)  REFERENCES dersler(id)         ON DELETE CASCADE,
  FOREIGN KEY (zaman_id) REFERENCES sinav_zamanlari(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sinav_derslikleri(
  id          INTEGER PRIMARY KEY,
  sinav_id    INTEGER NOT NULL,
  derslik_id  INTEGER NOT NULL,
  kota        INTEGER NOT NULL CHECK (kota > 0),
  UNIQUE (sinav_id, derslik_id),
  FOREIGN KEY (sinav_id)   REFERENCES sinavlar(id)    ON DELETE CASCADE,
  FOREIGN KEY (derslik_id) REFERENCES derslikler(id)  ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS oturma_koltuklari(
  id                INTEGER PRIMARY KEY,
  sinav_derslik_id  INTEGER NOT NULL,
  r                 INTEGER NOT NULL,   
  c                 INTEGER NOT NULL,   
  ogrenci_id        INTEGER,            
  UNIQUE (sinav_derslik_id, r, c),
  FOREIGN KEY (sinav_derslik_id) REFERENCES sinav_derslikleri(id) ON DELETE CASCADE,
  FOREIGN KEY (ogrenci_id)       REFERENCES ogrenciler(id)        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_ok_ogrenci_once
ON oturma_koltuklari (sinav_derslik_id, ogrenci_id)
WHERE ogrenci_id IS NOT NULL;


CREATE TABLE IF NOT EXISTS kisitlar(
  id               INTEGER PRIMARY KEY,    
  min_bekleme_dk   INTEGER NOT NULL DEFAULT 15,
  varsayilan_sure_dk INTEGER NOT NULL DEFAULT 75,
  paralel_yok      INTEGER NOT NULL DEFAULT 0 CHECK (paralel_yok IN (0,1)),
  haric_gunler     TEXT                   
);


CREATE INDEX IF NOT EXISTS ix_dersler_bolum ON dersler(bolum_id);
CREATE INDEX IF NOT EXISTS ix_derslikler_bolum ON derslikler(bolum_id);
CREATE INDEX IF NOT EXISTS ix_ogrenciler_bolum ON ogrenciler(bolum_id);
CREATE INDEX IF NOT EXISTS ix_kayitlar_ogrenci ON kayitlar(ogrenci_id);
CREATE INDEX IF NOT EXISTS ix_kayitlar_ders ON kayitlar(ders_id);









