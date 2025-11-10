#pdf_export.py
import os
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter, QPageSize, QPageLayout
from PySide6.QtCore import QMarginsF

def export_scene_to_pdf(scene, save_path: str):
    """
    Ekrandaki QGraphicsScene'i PDF'e çevirir.
    Görselde ne varsa birebir aynı şekilde PDF'e kaydeder.
    """
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(save_path)

       
        printer.setPageMargins(QMarginsF(10, 10, 10, 10))
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Landscape)  

       
        painter = QPainter(printer)
        scene.render(painter)
        painter.end()

    except Exception as e:
        raise RuntimeError(f"PDF oluşturulamadı: {e}")

