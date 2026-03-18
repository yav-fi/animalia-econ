# AWS Bedrock Setup

This project can refine priors with Amazon Bedrock models (for example Anthropic Claude on Bedrock).

## 1) Configure AWS credentials
Use any standard mechanism:
- `aws configure`
- AWS SSO profile
- environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`)

## 2) Set region and model
```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

You can switch to another Bedrock model ID (for example Amazon Nova) by changing `BEDROCK_MODEL_ID`.

## 3) Enable model access in Bedrock
In AWS Console -> Bedrock -> Model access, request/enable the model in your region.

## 4) Run with AI refinement
```bash
make pipeline-ai
```

If credentials or model access are missing, the script falls back to deterministic priors.
