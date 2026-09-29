"""Configuration for the LLM-as-Judge evaluation framework."""

from pathlib import Path

# Directory containing the Evaluation case folders
ROOT_EVALUATION_DIRECTORY: Path = Path(
    "/Users/aayushiagrawal/Documents/NewUI-VariantAnnotator-ForStudy/study_jobs/Evaluation"
)

# Directory where evaluation results will be saved
OUTPUT_DIRECTORY: Path = Path(
    "/Users/aayushiagrawal/Documents/NewUI-VariantAnnotator-ForStudy/automated_eval/results"
)

# AWS Bedrock model configuration
MODEL_ID: str = "global.anthropic.claude-sonnet-4-6"
AWS_REGION: str = "us-east-1"

# LLM parameters
MAX_RETRIES: int = 3
TEMPERATURE: float = 0.0
MAX_TOKENS: int = 4096
