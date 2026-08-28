from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from support_ai.config import Settings
from support_ai.data import Dataset
from support_ai.eval import run_evaluation, write_report
from support_ai.retrieval import KnowledgeBase

settings = Settings.from_env()
report = run_evaluation(Dataset.load(settings.data_dir), KnowledgeBase(settings.kb_dir))
write_report(report, settings.root / "eval_report.json")
print(report["summary"])
