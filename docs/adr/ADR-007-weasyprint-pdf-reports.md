# ADR-007 — WeasyPrint for PDF Backtest Report Generation

**Date:** 2025-03-01  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The backtest engine produces a detailed HTML performance report (equity curve, drawdown chart,
trade log table, and summary metrics). Users requested the ability to download this report as a
PDF for offline review, sharing, and record-keeping. The primary requirement is pixel-accurate
rendering of the existing HTML + CSS report template without maintaining a separate PDF layout
or duplicating report logic.

Two Python PDF generation libraries were evaluated: ReportLab and WeasyPrint. ReportLab is
a programmatic PDF toolkit that draws text, shapes, and tables using a canvas API. It has no
HTML renderer; the existing HTML report template cannot be reused, and a parallel ReportLab
layout implementation would need to be maintained in sync with the HTML template — a
significant ongoing maintenance cost. A third option, using a headless browser (Playwright or
Puppeteer) to print the HTML to PDF, was discounted due to the heavy runtime dependency
(Chromium) and slow startup time per request.

## Decision

Use **WeasyPrint** to convert the HTML backtest report to PDF.

WeasyPrint renders HTML and CSS to PDF using the Pango (text layout) and Cairo (2D graphics)
system libraries. The `generate_pdf_report()` function in
`backtesting/reporting/pdf_report.py` calls `weasyprint.HTML(string=html).write_pdf()`,
reusing the same Jinja2 template that generates the browser-viewable HTML report. No separate
PDF layout is required. The PDF output is streamed directly from the
`GET /api/v1/backtest/{run_id}/report/pdf` endpoint as an `application/pdf` response.

## Consequences

### Positive
- The existing HTML + CSS Jinja2 report template is reused exactly; no duplicate layout code
- CSS Flexbox, Grid, and print media queries are respected by WeasyPrint's CSS engine
- PDF generation is synchronous and happens in-process (no headless browser startup latency)
- WeasyPrint's output is deterministic and suitable for archiving

### Negative
- WeasyPrint requires system-level dependencies (`libpango`, `libcairo`, `libgdk-pixbuf`) that
  must be installed in the Docker image, increasing image size by approximately 80 MB
- WeasyPrint does not support JavaScript; any chart rendered via JavaScript (e.g., a canvas
  chart) will not appear in the PDF — chart images must be embedded as static SVG or PNG in
  the HTML template
- WeasyPrint's CSS support is not 100% identical to browser rendering; complex animations and
  some modern CSS properties are ignored

### Neutral
- The `GET /backtest/{run_id}/report/pdf` endpoint requires a prior `POST /backtest/run` call
  to populate the in-process result cache; the `run_id` is returned in the run response
- WeasyPrint version is pinned in `pyproject.toml`; minor version bumps have occasionally
  changed rendering output and should be tested before upgrading
