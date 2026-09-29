"""Configuration for the criteria-based LLM evaluation framework."""

from pathlib import Path

# Source directories containing all 98 cases
CONCORDANT_NEW_DIR: Path = Path(
    "/Users/aayushiagrawal/Documents/NewUI-VariantAnnotator-ForStudy/study_jobs/concordant-new"
)
DISCORDANT_NEW_DIR: Path = Path(
    "/Users/aayushiagrawal/Documents/NewUI-VariantAnnotator-ForStudy/study_jobs/discordant-new"
)

# Output directory for results
OUTPUT_DIRECTORY: Path = Path(
    "/Users/aayushiagrawal/Documents/NewUI-VariantAnnotator-ForStudy/llm_automated_eval/results"
)

# AWS Bedrock model configuration
MODEL_ID: str = "global.anthropic.claude-sonnet-4-6"
AWS_REGION: str = "us-east-1"

# LLM parameters
MAX_RETRIES: int = 3
TEMPERATURE: float = 0.0
MAX_TOKENS: int = 4096

# Overall quality mapping
QUALITY_TO_SCORE: dict[str, int] = {
    "excellent": 5,
    "good": 4,
    "acceptable": 3,
    "poor": 2,
    "unsafe": 1,
}
