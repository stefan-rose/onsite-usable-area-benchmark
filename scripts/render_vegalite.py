"""Render a Vega-Lite spec to PDF (vector) or PNG with vl-convert.

Usage:
    python scripts/render_vegalite.py SPEC OUT [--inline-spec SPEC_OUT]

OUT ending in .pdf gives a vector PDF; anything else gives PNG at the scale in
the SCALE environment variable (default 2). If the spec has a data.url pointing
to a local CSV, the CSV is read (path relative to the spec), numeric fields are
converted to float, and the rows are inlined, because vl-convert does not
resolve local relative URLs. --inline-spec also writes that self-contained spec.

Tested with vl-convert-python 1.9.0, e.g.:
    uv run --with vl-convert-python python scripts/render_vegalite.py \
        figures/fig_bins.vl.json figures/fig_bins.pdf
"""
import csv
import json
import os
import sys

import vl_convert as vlc


def main() -> None:
    args = sys.argv[1:]
    inline_out = None
    if "--inline-spec" in args:
        i = args.index("--inline-spec")
        inline_out = args[i + 1]
        del args[i:i + 2]
    spec_path, out = args
    spec = json.load(open(spec_path))
    url = spec.get("data", {}).get("url")
    if url:
        p = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(spec_path)), url))
        rows = list(csv.DictReader(open(p)))
        for r in rows:
            for k, v in r.items():
                try:
                    r[k] = float(v)
                except ValueError:
                    pass
        spec["data"] = {"values": rows}
        print(f"inlined {len(rows)} rows from {p}")
    if inline_out:
        with open(inline_out, "w") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
            f.write("\n")
    if out.endswith(".pdf"):
        data = vlc.vegalite_to_pdf(json.dumps(spec))
    else:
        data = vlc.vegalite_to_png(json.dumps(spec), scale=int(os.environ.get("SCALE", 2)))
    with open(out, "wb") as f:
        f.write(data)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
