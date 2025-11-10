# core/export_excel.py 
import xlsxwriter
import os
import re
from pathlib import Path

def sanitize_filename(name: str) -> str:
    """Dosya adı için geçersiz karakterleri temizler."""
    return re.sub(r'[\\/*?:"<>| ]+', "_", name.strip())

def export_exam_excel_each_class(plans, exam_type="Vize"):
    """
    📘 Her bölüm ve her sınıf için ayrı Excel dosyası oluşturur.

    plans = {
        "Bilgisayar Mühendisliği": {
            1: [ {...}, {...} ],
            2: [ {...} ],
            3: [ {...} ],
            4: [ {...} ],
        },
        "Elektrik Mühendisliği": {
            1: [ {...} ],
            2: [ {...} ],
        },
    }
    """
    try:
       
        ROOT = Path(__file__).resolve().parents[1]
        output_dir = ROOT / "data"
        output_dir.mkdir(parents=True, exist_ok=True)

        created_files = []

        for dept_name, sinif_dict in plans.items():
          
            for sinif in sorted([k for k in sinif_dict.keys() if k and k in (1, 2, 3, 4)]):
                dersler = sinif_dict[sinif]
                if not dersler:
                    continue

                #
                sinif_label = f"{sinif}_Sinif"
                sinif_title = f"{sinif}. Sınıf"

             
                safe_dept = sanitize_filename(dept_name)
                safe_exam = sanitize_filename(exam_type.capitalize())
                file_name = f"program_{safe_dept}_{sinif_label}_{safe_exam}.xlsx"
                filepath = output_dir / file_name

                
                workbook = xlsxwriter.Workbook(str(filepath))
                ws = workbook.add_worksheet("Sınav Programı")

                
                title_fmt = workbook.add_format({
                    "bold": True, "align": "center", "valign": "vcenter",
                    "font_color": "white", "bg_color": "#C0504D",
                    "border": 1, "font_size": 14
                })
                header_fmt = workbook.add_format({
                    "bold": True, "align": "center", "valign": "vcenter",
                    "font_color": "white", "bg_color": "#F37C20",
                    "border": 1, "font_size": 12
                })
                cell_fmt = workbook.add_format({
                    "align": "center", "valign": "vcenter", "border": 1
                })
                left_fmt = workbook.add_format({
                    "align": "left", "valign": "vcenter", "border": 1
                })

                
                ws.set_column("A:A", 15)
                ws.set_column("B:B", 12)
                ws.set_column("C:C", 45)
                ws.set_column("D:D", 30)
                ws.set_column("E:E", 25)

               
                title_text = f"{dept_name.upper()} BÖLÜMÜ {exam_type.upper()} SINAV PROGRAMI – {sinif_title}"
                ws.merge_range("A1:E1", title_text, title_fmt)

                
                headers = ["Tarih", "Sınav Saati", "Ders Adı", "Öğretim Elemanı", "Derslik"]
                for col, h in enumerate(headers):
                    ws.write(2, col, h, header_fmt)

            
                row = 3
                for rec in dersler:
                    ws.write(row, 0, str(rec.get("Tarih", "")), cell_fmt)
                    ws.write(row, 1, str(rec.get("Saat", "")), cell_fmt)
                    ws.write(row, 2, str(rec.get("Ders Adı", "")), left_fmt)
                    ws.write(row, 3, str(rec.get("Öğretim Elemanı", "")), left_fmt)
                    ws.write(row, 4, str(rec.get("Derslik", "")), cell_fmt)
                    row += 1

                workbook.close()
                created_files.append(str(filepath))

        return created_files

    except Exception as e:
        print(f"❌ Excel oluşturulamadı: {e}")
        return []
    

    




