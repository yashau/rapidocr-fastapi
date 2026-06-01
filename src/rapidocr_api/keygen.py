import argparse
import secrets
import sys
import tomllib
from pathlib import Path

DEFAULT_FILE = Path("api-keys.toml")
DEFAULT_BYTES = 32


def generate_key(num_bytes: int = DEFAULT_BYTES) -> str:
    return secrets.token_urlsafe(num_bytes)


def _format_entry(key: str, comment: str | None) -> list[str]:
    lines = []
    if comment:
        lines.append(f"  # {comment}\n")
    lines.append(f'  "{key}",\n')
    return lines


def _find_multiline_api_keys_array(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("api_keys") and "=" in stripped and "[" in stripped:
            return index
    return None


def _find_array_end(lines: list[str], start_index: int) -> int | None:
    for index in range(start_index + 1, len(lines)):
        if lines[index].strip().startswith("]"):
            return index
    return None


def append_key(path: Path, key: str, comment: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        lines = ["api_keys = [\n", *_format_entry(key, comment), "]\n"]
        path.write_text("".join(lines), encoding="utf-8", newline="\n")
        return

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start_index = _find_multiline_api_keys_array(lines)
    if start_index is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.extend(["\n", "api_keys = [\n", *_format_entry(key, comment), "]\n"])
        path.write_text("".join(lines), encoding="utf-8", newline="\n")
        return

    end_index = _find_array_end(lines, start_index)
    if end_index is None:
        raise ValueError(f"Could not find closing bracket for api_keys array in {path}")

    lines[end_index:end_index] = _format_entry(key, comment)
    path.write_text("".join(lines), encoding="utf-8", newline="\n")


def validate_toml(path: Path) -> None:
    with path.open("rb") as file:
        tomllib.load(file)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and append an API key.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
        help="TOML file to update. Defaults to api-keys.toml.",
    )
    parser.add_argument(
        "--bytes",
        type=int,
        default=DEFAULT_BYTES,
        help="Number of random bytes before URL-safe encoding. Defaults to 32.",
    )
    parser.add_argument(
        "--comment",
        help="TOML comment to add above the key. If omitted, you will be prompted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.bytes <= 0:
        raise SystemExit("--bytes must be positive")

    comment = args.comment
    if comment is None:
        comment = input("Comment for this API key: ").strip()

    key = generate_key(args.bytes)
    append_key(args.file, key, comment)
    validate_toml(args.file)
    print(key)


if __name__ == "__main__":
    main()
