# core/errors.py

class ErrorCodes:
   
    DERS_YOK = "Ders bulunamadı"
    OGRENCI_YOK = "Kayıtlı öğrenci yok"
    DERSLIK_YOK = "Derslik bulunamadı"
    KAPASITE = "Kapasite yetersiz"
    CAKISMA = "Öğrenci sınav çakışması"
    TARIH_ARALIGI = "Geçersiz tarih aralığı"
    OTURMA = "Oturma planı hatası"
    KOLTUK = "Koltuk yerleşimi hatası"
    PDF = "PDF oluşturma hatası"
    GENEL = "Bilinmeyen hata"

def format_error(category, detail=None):
    """
    Returns a formatted, user-friendly message.
    Safe to show in QMessageBox across all UI layers.
    """
    detail = detail or ""
    templates = {
      
        ErrorCodes.DERS_YOK: f"❌ Ders bulunamadı! {detail}",
        ErrorCodes.OGRENCI_YOK: f"👩‍🎓 Kayıtlı öğrenci yok! {detail}",
        ErrorCodes.DERSLIK_YOK: f"🏫 Derslik bulunamadı! {detail}",
        ErrorCodes.KAPASITE: f"⚠️ Kapasite yetersiz — bazı öğrenciler yerleştirilemedi. {detail}",
        ErrorCodes.CAKISMA: f"⚠️ Öğrencinin dersleri çakışıyor! ({detail})",
        ErrorCodes.TARIH_ARALIGI: f"📅 Geçersiz tarih aralığı! ({detail})",

        ErrorCodes.OTURMA: f"💺 Oturma planı oluşturulamadı! ({detail})",
        ErrorCodes.KOLTUK: f"🪑 Koltuk yerleşimi yapılamadı! ({detail})",
        ErrorCodes.PDF: f"📄 PDF çıktısı oluşturulamadı! ({detail})",

      
        ErrorCodes.GENEL: f"⚠️ Beklenmeyen hata oluştu! {detail}",
    }
    if category in templates:
        return templates[category]
    elif isinstance(category, str):
        return f"⚠️ {category}: {detail}"
    else:
        return f"⚠️ Bilinmeyen hata: {detail}"


def success_message(msg):
    """Returns standardized success message for UI display."""
    return f"✅ {msg}"
