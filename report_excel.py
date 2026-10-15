import openpyxl

from strings import raw, t


def generate_daily_excel(date_str, stats, top_sales, top_arrivals):
    sheets = raw("excel_sheets")
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = sheets[0]
    ws.append([t("daily_header", date=date_str).replace("<b>", "").replace("</b>", "")])
    ws.append([])
    ws.append(["Metric", "Count", "Qty"])
    ws.append(["Sales", stats["sales"][0], stats["sales"][1]])
    ws.append(["Arrivals", stats["arrivals"][0], stats["arrivals"][1]])
    ws.append(["Price changes", stats["price_changes"], ""])
    ws.append(["Status changes", stats["status_changes"], ""])

    ws_a = wb.create_sheet(title=sheets[2])
    ws_a.append(["#", "Title", "Publisher", "Qty"])
    for i, it in enumerate(top_arrivals or [], 1):
        ws_a.append([i, it["title"], it["publisher"], it["qty"]])

    ws_s = wb.create_sheet(title=sheets[3])
    ws_s.append(["#", "Title", "Publisher", "Qty"])
    for i, it in enumerate(top_sales or [], 1):
        ws_s.append([i, it["title"], it["publisher"], it["qty"]])

    filename = f"report_{date_str}.xlsx"
    wb.save(filename)
    return filename
