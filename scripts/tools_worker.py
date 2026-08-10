#!/usr/bin/env python3
"""
tools_worker.py — anaconda-side worker for MSO Studio's Tools module.

Runs the operations that need something only the shared anaconda
environment has: PySR symbolic regression (needs Julia), Gemini calls
(google-genai package), and PDF text/table extraction (pdfplumber). The
light PySide6 GUI venv never imports any of these directly -- it shells out
here via mso_studio.core.tools, exactly like every other core adapter's
subprocess bridge (mso_studio.core.backends.run_backend).

Reuses notebook_gemini.gemini_client.GeminiClient as-is (it's already
framework-agnostic, zero Tkinter imports) rather than re-implementing the
Gemini wrapper.

Usage:
    python3.9 tools_worker.py <mode> <request.json> <response.json>

Modes
-----
pysr_fit             {X, Y, n_iter}
gemini_chat          {prompt, context}
gemini_chat_pdf      {pdf_path, question}
gemini_chat_image    {image_path, mime, question}
gemini_summarise_pdf {pdf_path}
gemini_clean_table   {csv_text}
pdf_extract_text     {pdf_path}
pdf_extract_tables   {pdf_path}
pdf_page_count       {pdf_path}
pdf_render_page      {pdf_path, page_no, out_png_path, resolution}
rdkit_validate_smiles {rows: [{name, smiles}, ...]}
rdkit_render_png     {smiles, out_png_path, size}

(Polynomial fit is NOT here -- pure numpy, done in-process in the GUI venv;
see mso_studio.core.tools.poly_fit.)

Writes {"ok": true, "result": {...}} or {"ok": false, "error": "..."} to
response.json and exits 0/1 accordingly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _pysr_fit(req: dict) -> dict:
    import numpy as np
    from pysr import PySRRegressor

    X = np.array(req["X"], dtype=float).reshape(-1, 1)
    Y = np.array(req["Y"], dtype=float)
    model = PySRRegressor(
        niterations=int(req.get("n_iter", 40)),
        binary_operators=["+", "-", "*", "/", "^"],
        unary_operators=["exp", "log", "sqrt", "abs"],
        populations=10,
        # (Round-2 audit fix) population_size was 15, exactly equal to
        # PySRRegressor's own default `tournament_selection_n=15` -- the
        # Julia backend requires tournament_selection_n STRICTLY less than
        # population_size and raises `AssertionError:
        # tournament_selection_n must be less than population_size` at
        # Options construction, before any fitting happens. This was a
        # 100%-reproducible crash on every single PySR fit this tool ever
        # attempted, for any input (confirmed against real Arrhenius k(T)
        # data from MECHANISM/FFCM1 -- WORKBENCH_AUDIT_2026-08-10.md,
        # Round 2). 20 leaves headroom above the default
        # tournament_selection_n instead of exactly matching it.
        population_size=20,
        maxsize=20,
        verbosity=1,  # streamed to the GUI log via run_backend's on_line
        progress=False,
    )
    model.fit(X, Y)
    eqs = model.equations_
    best = model.get_best()
    x_fine = np.linspace(X.min(), X.max(), 300).reshape(-1, 1)
    y_fine = model.predict(x_fine)
    return {
        "equations": [
            {
                "complexity": int(row.get("complexity", 0)),
                "loss": float(row.get("loss", 0.0)),
                "equation": str(row.get("equation", "")),
            }
            for _, row in eqs.iterrows()
        ],
        "best_equation": str(best.get("equation", "")),
        "x_fine": x_fine.ravel().tolist(),
        "y_fine": np.asarray(y_fine).ravel().tolist(),
    }


def _gemini_chat(req: dict) -> dict:
    from notebook_gemini.gemini_client import GeminiClient

    client = GeminiClient()
    return {"reply": client.chat(req["prompt"], context=req.get("context", ""))}


def _gemini_chat_pdf(req: dict) -> dict:
    from notebook_gemini.gemini_client import GeminiClient

    client = GeminiClient()
    pdf_bytes = Path(req["pdf_path"]).read_bytes()
    return {"reply": client.chat_with_pdf_bytes(pdf_bytes, req["question"])}


def _gemini_chat_image(req: dict) -> dict:
    from notebook_gemini.gemini_client import GeminiClient

    client = GeminiClient()
    image_bytes = Path(req["image_path"]).read_bytes()
    return {"reply": client.chat_with_image_bytes(image_bytes, req.get("mime", "image/png"), req["question"])}


def _gemini_summarise_pdf(req: dict) -> dict:
    from notebook_gemini.gemini_client import GeminiClient

    client = GeminiClient()
    pdf_bytes = Path(req["pdf_path"]).read_bytes()
    return {"reply": client.summarise_pdf_bytes(pdf_bytes)}


def _gemini_clean_table(req: dict) -> dict:
    from notebook_gemini.gemini_client import GeminiClient

    client = GeminiClient()
    reply = client.chat(
        "Below is a table extracted from a PDF (possibly OCR-noisy). "
        "Fix any obvious OCR errors, merge split cells, and return the "
        "corrected table in CSV format (no extra commentary):\n\n" + req["csv_text"]
    )
    return {"reply": reply}


def _pdf_extract_text(req: dict) -> dict:
    import pdfplumber

    with pdfplumber.open(req["pdf_path"]) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    return {"n_pages": len(pages), "text": "\n".join(pages)}


def _pdf_page_count(req: dict) -> dict:
    import pdfplumber

    with pdfplumber.open(req["pdf_path"]) as pdf:
        return {"n_pages": len(pdf.pages)}


def _pdf_render_page(req: dict) -> dict:
    """Rasterize one PDF page to a PNG file -- used by the digitizer's 'Open
    PDF page' action. Routed through pdfplumber/anaconda rather than Qt's
    QtPdf module, which fails to import on this machine (a system
    libgssapi_krb5 version conflict unrelated to this project)."""
    import pdfplumber

    page_no = int(req["page_no"])  # 1-indexed
    with pdfplumber.open(req["pdf_path"]) as pdf:
        if not (1 <= page_no <= len(pdf.pages)):
            raise ValueError(f"page {page_no} out of range (PDF has {len(pdf.pages)} pages)")
        image = pdf.pages[page_no - 1].to_image(resolution=int(req.get("resolution", 150)))
        image.save(req["out_png_path"])
    return {"out_png_path": req["out_png_path"]}


def _pdf_extract_tables(req: dict) -> dict:
    import pdfplumber

    tables, page_nums = [], []
    with pdfplumber.open(req["pdf_path"]) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for tbl in page.extract_tables():
                clean = [[cell if cell is not None else "" for cell in row] for row in tbl]
                tables.append(clean)
                page_nums.append(page_no)
    return {"tables": tables, "page_nums": page_nums}


def _rdkit_validate_smiles(req: dict) -> dict:
    """{rows: [{name, smiles}, ...]} -> per-row validity + canonical SMILES
    + formula + MW, via RDKit (not in the GUI venv -- see this worker's
    module docstring). One bad SMILES never aborts the batch."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors

    out = []
    for row in req["rows"]:
        name, smiles = row.get("name", ""), row.get("smiles", "")
        mol = Chem.MolFromSmiles(smiles) if smiles else None
        if mol is None:
            out.append({"name": name, "smiles": smiles, "valid": False,
                        "canonical_smiles": None, "formula": None, "mw": None,
                        "error": "RDKit could not parse this SMILES"})
            continue
        out.append({
            "name": name, "smiles": smiles, "valid": True,
            "canonical_smiles": Chem.MolToSmiles(mol),
            "formula": rdMolDescriptors.CalcMolFormula(mol),
            "mw": round(Descriptors.MolWt(mol), 3),
            "error": None,
        })
    return {"rows": out}


def _rdkit_render_png(req: dict) -> dict:
    """{smiles, out_png_path, size} -> a 2D structure depiction, for the
    Tools RDKit tab's preview pane."""
    from rdkit import Chem
    from rdkit.Chem import Draw

    mol = Chem.MolFromSmiles(req["smiles"])
    if mol is None:
        raise ValueError(f"RDKit could not parse SMILES: {req['smiles']!r}")
    size = int(req.get("size", 300))
    Draw.MolToFile(mol, req["out_png_path"], size=(size, size))
    return {"out_png_path": req["out_png_path"]}


_HANDLERS = {
    "pysr_fit": _pysr_fit,
    "gemini_chat": _gemini_chat,
    "gemini_chat_pdf": _gemini_chat_pdf,
    "gemini_chat_image": _gemini_chat_image,
    "gemini_summarise_pdf": _gemini_summarise_pdf,
    "gemini_clean_table": _gemini_clean_table,
    "pdf_extract_text": _pdf_extract_text,
    "pdf_extract_tables": _pdf_extract_tables,
    "pdf_page_count": _pdf_page_count,
    "pdf_render_page": _pdf_render_page,
    "rdkit_validate_smiles": _rdkit_validate_smiles,
    "rdkit_render_png": _rdkit_render_png,
}


def main() -> int:
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <mode> <request.json> <response.json>", file=sys.stderr)
        return 2
    mode, req_path, resp_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])

    handler = _HANDLERS.get(mode)
    if handler is None:
        resp_path.write_text(json.dumps({
            "ok": False,
            "error": f"Unknown mode '{mode}'. Available: {', '.join(sorted(_HANDLERS))}",
        }))
        return 1

    try:
        request = json.loads(req_path.read_text())
        result = handler(request)
        resp_path.write_text(json.dumps({"ok": True, "result": result}))
        return 0
    except Exception as exc:  # noqa: BLE001 - the GUI reads response.json either way
        resp_path.write_text(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
