"""
PDF report generator for backtesting results.

Converts the existing HTML report to PDF via WeasyPrint.
Reuses ``generate_html_report()`` — no metric duplication.

Justification for WeasyPrint:
  The HTML report template already produces a complete, styled self-contained
  document.  WeasyPrint converts it to PDF directly with no layout duplication.
  Pure-Python alternatives (ReportLab) would require re-implementing all layout,
  SVG chart rendering, and table styling from scratch.

Usage::

    from backtesting.reporting.pdf_report import generate_pdf_report

    pdf_bytes = generate_pdf_report(result)
    with open("report.pdf", "wb") as f:
        f.write(pdf_bytes)
"""

from __future__ import annotations

from backtesting.engine.base import BacktestResult
from backtesting.reporting.html_report import generate_html_report

try:
    from backtesting.optimization.monte_carlo import MonteCarloResult
except ImportError:
    MonteCarloResult = None  # type: ignore[misc,assignment]


def generate_pdf_report(
    result: BacktestResult,
    mc_result: "MonteCarloResult | None" = None,
) -> bytes:
    """
    Render a BacktestResult as a PDF document.

    Converts the self-contained HTML report produced by ``generate_html_report``
    to PDF using WeasyPrint.

    Parameters
    ----------
    result : BacktestResult
        Completed backtest result (metrics pre-computed or will be computed here).
    mc_result : MonteCarloResult | None
        Optional Monte Carlo simulation results to include in the PDF.

    Returns
    -------
    bytes
        Raw PDF binary content.

    Raises
    ------
    ImportError
        If WeasyPrint is not installed.
    """
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "WeasyPrint is required for PDF generation. "
            "Install it with: pip install weasyprint"
        ) from exc

    html_content = generate_html_report(result, mc_result=mc_result)

    # WeasyPrint renders the HTML to PDF in-memory
    pdf_bytes: bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
