"""Typed local geofeed analysis."""

from .analyzer import MAX_DATA_ROWS, analyze_file
from .corrections import export_corrected_csv, propose_corrections, record_approval
from .errors import AnalysisError, CorrectionError, DataRowLimitError, SourceDecodeError
from .models import Analysis, CorrectionApproval, CorrectionPlan
from .runtime import require_supported_python

require_supported_python()

__all__ = [
    "MAX_DATA_ROWS",
    "Analysis",
    "AnalysisError",
    "CorrectionApproval",
    "CorrectionError",
    "CorrectionPlan",
    "DataRowLimitError",
    "SourceDecodeError",
    "analyze_file",
    "export_corrected_csv",
    "propose_corrections",
    "record_approval",
    "require_supported_python",
]
