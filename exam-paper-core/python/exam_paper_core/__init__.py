"""试卷解析与生成 Skill 的共享核心。"""

from .checkpoint import PipelineState, create_stage_receipt, validate_stage_receipt
from .cli import ChineseArgumentParser
from .contract import (
    CONTRACT_VERSION,
    FINGERPRINT_VERSION,
    ContractError,
    build_document,
    calculate_source_hash,
    read_json,
    validate_question_fragment,
    validate_document,
    write_json_atomic,
)
from .fingerprint import question_fingerprint
from .preflight import scan_tree
from .production import QuestionTransaction, validate_committed_transaction
from .assembly import ESAT_COMBINATIONS, analyze_assembly, build_assembled_exam
from .project_export import build_project_diagnostic_paper, validate_project_diagnostic_paper

__all__ = [
    "CONTRACT_VERSION",
    "FINGERPRINT_VERSION",
    "ContractError",
    "ChineseArgumentParser",
    "PipelineState",
    "QuestionTransaction",
    "ESAT_COMBINATIONS",
    "analyze_assembly",
    "build_document",
    "build_assembled_exam",
    "build_project_diagnostic_paper",
    "calculate_source_hash",
    "create_stage_receipt",
    "question_fingerprint",
    "read_json",
    "scan_tree",
    "validate_committed_transaction",
    "validate_document",
    "validate_question_fragment",
    "validate_project_diagnostic_paper",
    "validate_stage_receipt",
    "write_json_atomic",
]
