#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["reportlab"]
# ///
"""1:1 drilling template for the option B board, tiled on US Letter pages.

    cad_b/board_template.py [OUT.pdf]      (default /tmp/option-b-board-template.pdf)

Hole positions come from render_b/w_b.scad (part="v3_holes"), i.e. the same
numbers the CAD and the assembly video use. Print at 100 % ("actual size"),
check the 100 mm scale bar on every page, tape the pages edge to edge using
the overlap crosses, lay the sheet on the board with its edges flush, and
centre-punch every hole. Drill Ø2.5 mm pilots, about 10 mm deep, and the one Ø35 hopper hole all the way through.
"""
import re, subprocess, sys, math
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/option-b-board-template.pdf")
r = subprocess.run(["openscad", "-D", 'part="v3_holes"', "-o", "/tmp/_holes.echo", str(HERE / "render_b" / "w_b.scad")],
                   capture_output=True, text=True)
txt = Path("/tmp/_holes.echo").read_text() if Path("/tmp/_holes.echo").exists() else r.stderr
holes = [(m[1], float(m[2]), float(m[3])) for m in re.finditer(r'HOLE = \["([^"]+)", ([-\d.e]+), ([-\d.e]+)\]', txt)]
stations = [(m[1], float(m[2]), float(m[3])) for m in re.finditer(r'STATION = \["([^"]+)", ([-\d.e]+), ([-\d.e]+)\]', txt)]
b = re.search(r'BOARD = \[([-\d.]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)\]', txt)
if not holes or not b: sys.exit("no hole data from w_b.scad:\n" + txt[-2000:])
bx0, by0, bw, bh = map(float, b.groups())

PW, PH = letter                                   # points
margin, overlap = 12 * mm, 15 * mm
uw, uh = PW - 2 * margin, PH - 2 * margin          # usable area per page (points)
step_x, step_y = uw - overlap, uh - overlap
cols = math.ceil((bw * mm - overlap) / step_x); rows = math.ceil((bh * mm - overlap) / step_y)
c = canvas.Canvas(str(out), pagesize=letter)
c.setTitle("Riftbound sorter option B: board drilling template (1:1)")

def page(ci, ri):
    # board X runs left->right, board Y runs bottom->top (the bins' side at the top)
    ox = margin - ci * step_x - 0; oy = margin - ri * step_y
    def P(x, y): return ox + (x - bx0) * mm, oy + (y - by0) * mm
    c.saveState(); p = c.beginPath(); p.rect(margin, margin, uw, uh); c.clipPath(p, stroke=0)
    c.setLineWidth(0.6); c.setStrokeGray(0.4); c.rect(*P(bx0, by0), bw * mm, bh * mm)      # board edge
    c.setStrokeGray(0.75); c.setLineWidth(0.3)
    for k in range(-4, 5):                                                                    # light 100 mm grid
        x0, y0 = P(k * 100, by0); x1, y1 = P(k * 100, by0 + bh); c.line(x0, y0, x1, y1)
        x0, y0 = P(bx0, k * 100); x1, y1 = P(bx0 + bw, k * 100); c.line(x0, y0, x1, y1)
    c.setStrokeGray(0); c.setLineWidth(0.5)
    ax, ay = P(0, 0); c.line(ax - 12 * mm, ay, ax + 12 * mm, ay); c.line(ax, ay - 12 * mm, ax, ay + 12 * mm)
    c.circle(ax, ay, 80 * mm, stroke=1, fill=0); c.setFont("Helvetica", 7); c.drawString(ax + 2 * mm, ay + 2 * mm, "yaw axis (pedestal centre)")
    for n, x, y in stations:
        sx, sy = P(x, y); c.setStrokeGray(0.55); c.circle(sx, sy, 3 * mm); c.setFont("Helvetica", 6); c.drawCentredString(sx, sy - 6 * mm, n + " (cup centre)")
    c.setStrokeGray(0)
    for n, x, y in holes:
        hx, hy = P(x, y)
        c.setLineWidth(0.3); c.line(hx - 5 * mm, hy, hx + 5 * mm, hy); c.line(hx, hy - 5 * mm, hx, hy + 5 * mm)
        big = "Ø35" in n
        c.setLineWidth(0.5); c.circle(hx, hy, (17.5 if big else 1.25) * mm); c.setFont("Helvetica", 5.5); c.drawString(hx + (19 if big else 1.8) * mm, hy + 1.5 * mm, n)
    c.restoreState()
    c.setFont("Helvetica-Bold", 9); c.drawString(margin, PH - margin + 3 * mm, f"Option B board template  page {ri * cols + ci + 1}/{cols * rows}  (column {ci + 1} of {cols} from the left, row {ri + 1} of {rows} from the bottom)")
    c.setFont("Helvetica", 7); c.drawString(margin, margin - 8 * mm, "Print at 100 % / actual size. Overlap the pages on the grid lines and hole crosses. Holes: Ø2.5 mm pilots. Bins side = top.")
    c.setLineWidth(1); c.line(PW - margin - 100 * mm, margin - 5 * mm, PW - margin, margin - 5 * mm)
    for t in (0, 50, 100): x = PW - margin - 100 * mm + t * mm; c.line(x, margin - 6.5 * mm, x, margin - 3.5 * mm)
    c.drawRightString(PW - margin, margin - 9.5 * mm, "this bar must measure exactly 100 mm")
    c.showPage()

for ri in range(rows):
    for ci in range(cols):
        page(ci, ri)
c.save()
print(f"{out}: {cols * rows} pages, {len(holes)} holes")
