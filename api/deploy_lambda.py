from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


DEFAULT_FUNCTION_NAME = "AnimaliaEconApi"
DEFAULT_REGION = "us-east-1"
DEFAULT_S3_PREFIX = "deployments/animaliaeconapi"
DEFAULT_DEPENDENCIES = [
    # Use pydantic v1 for portable pure-python packaging from non-Linux hosts.
    "fastapi==0.95.2",
    "pydantic==1.10.24",
    "mangum==0.17.0",
]


def run(cmd: list[str], cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() if proc.stderr else ""
        stdout = proc.stdout.strip() if proc.stdout else ""
        detail = stderr or stdout or f"exit code {proc.returncode}"
        raise SystemExit(f"Command failed: {' '.join(cmd)}\n{detail}")
    return proc


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise SystemExit(f"Missing required path: {src}")
    shutil.copytree(src, dst)


def zip_dir(source_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir():
                continue
            arcname = path.relative_to(source_dir)
            zf.write(path, arcname=str(arcname))


def resolve_account_id(region: str) -> str:
    proc = run(
        ["aws", "sts", "get-caller-identity", "--region", region, "--output", "json"],
        capture=True,
    )
    payload = json.loads(proc.stdout)
    account = str(payload.get("Account", "")).strip()
    if not account:
        raise SystemExit("Unable to resolve AWS account id via sts get-caller-identity.")
    return account


def default_bucket(region: str) -> str:
    account = resolve_account_id(region=region)
    return f"cdk-hnb659fds-assets-{account}-{region}"


def package_lambda(
    repo_root: Path,
    build_dir: Path,
    zip_path: Path,
    dependencies: list[str],
) -> None:
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if zip_path.exists():
        zip_path.unlink()
    build_dir.mkdir(parents=True, exist_ok=True)

    print("Installing deployment dependencies...")
    run([sys.executable, "-m", "pip", "install", "--quiet", "--target", str(build_dir), *dependencies])

    print("Copying code and dataset artifacts...")
    copy_tree(repo_root / "api", build_dir / "api")
    copy_tree(repo_root / "sim", build_dir / "sim")

    (build_dir / "data").mkdir(parents=True, exist_ok=True)
    (build_dir / "releases").mkdir(parents=True, exist_ok=True)
    (build_dir / "schema" / "api").mkdir(parents=True, exist_ok=True)

    copy_tree(repo_root / "data" / "processed", build_dir / "data" / "processed")
    copy_tree(repo_root / "releases" / "datasets", build_dir / "releases" / "datasets")
    copy_tree(repo_root / "schema" / "api" / "v1", build_dir / "schema" / "api" / "v1")

    print("Creating zip package...")
    zip_dir(source_dir=build_dir, zip_path=zip_path)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Package: {zip_path} ({size_mb:.2f} MiB)")


def deploy_lambda(
    function_name: str,
    region: str,
    zip_path: Path,
    s3_bucket: str,
    s3_prefix: str,
    wait: bool,
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    s3_key = f"{s3_prefix.rstrip('/')}/animalia_lambda_{ts}.zip"

    print(f"Uploading to s3://{s3_bucket}/{s3_key} ...")
    upload_err: SystemExit | None = None
    for attempt in range(1, 4):
        try:
            # Use put-object to avoid multipart upload fragility for this small artifact.
            run(
                [
                    "aws",
                    "s3api",
                    "put-object",
                    "--region",
                    region,
                    "--bucket",
                    s3_bucket,
                    "--key",
                    s3_key,
                    "--body",
                    str(zip_path),
                ]
            )
            upload_err = None
            break
        except SystemExit as exc:
            upload_err = exc
            if attempt == 3:
                break
            wait_s = attempt * 3
            print(f"Upload attempt {attempt}/3 failed; retrying in {wait_s}s...")
            time.sleep(wait_s)

    if upload_err is not None:
        raise upload_err

    print(f"Updating Lambda function {function_name} ...")
    update = run(
        [
            "aws",
            "lambda",
            "update-function-code",
            "--region",
            region,
            "--function-name",
            function_name,
            "--s3-bucket",
            s3_bucket,
            "--s3-key",
            s3_key,
            "--output",
            "json",
        ],
        capture=True,
    )
    payload = json.loads(update.stdout)
    print(
        "Update accepted: "
        f"function={payload.get('FunctionName')} "
        f"last_modified={payload.get('LastModified')} "
        f"code_size={payload.get('CodeSize')}"
    )

    if wait:
        print("Waiting for function update to complete...")
        run(["aws", "lambda", "wait", "function-updated", "--region", region, "--function-name", function_name])

    try:
        url_proc = run(
            [
                "aws",
                "lambda",
                "get-function-url-config",
                "--region",
                region,
                "--function-name",
                function_name,
                "--output",
                "json",
            ],
            capture=True,
        )
        url_payload = json.loads(url_proc.stdout)
        function_url = str(url_payload.get("FunctionUrl", "")).strip()
    except SystemExit:
        function_url = ""

    print("Deploy complete.")
    print(f"s3_key={s3_key}")
    if function_url:
        print(f"function_url={function_url}")
        print(f"verify: curl {function_url}v1/meta")


def main() -> None:
    parser = argparse.ArgumentParser(description="Package and deploy AnimaliaEcon API to AWS Lambda.")
    parser.add_argument("--function-name", default=DEFAULT_FUNCTION_NAME, help="Lambda function name.")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region.")
    parser.add_argument("--s3-bucket", default="", help="S3 bucket used as deployment staging.")
    parser.add_argument("--s3-prefix", default=DEFAULT_S3_PREFIX, help="S3 key prefix for deployment zip.")
    parser.add_argument(
        "--dependency",
        action="append",
        default=[],
        help="Override/add pip dependency for deploy package. Repeatable.",
    )
    parser.add_argument("--build-dir", default="/tmp/animalia_lambda_pkg", help="Temporary build directory.")
    parser.add_argument("--zip-path", default="/tmp/animalia_lambda.zip", help="Output zip path.")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for Lambda update completion.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    build_dir = Path(args.build_dir).resolve()
    zip_path = Path(args.zip_path).resolve()
    dependencies = args.dependency if args.dependency else list(DEFAULT_DEPENDENCIES)
    bucket = args.s3_bucket.strip() or default_bucket(region=args.region)

    print(f"repo_root={repo_root}")
    print(f"region={args.region}")
    print(f"function_name={args.function_name}")
    print(f"s3_bucket={bucket}")
    print(f"dependencies={','.join(dependencies)}")

    package_lambda(
        repo_root=repo_root,
        build_dir=build_dir,
        zip_path=zip_path,
        dependencies=dependencies,
    )
    deploy_lambda(
        function_name=args.function_name,
        region=args.region,
        zip_path=zip_path,
        s3_bucket=bucket,
        s3_prefix=args.s3_prefix,
        wait=not args.no_wait,
    )


if __name__ == "__main__":
    main()
