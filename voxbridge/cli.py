"""VoxBridge CLI entry point.

Usage:
    voxbridge run --config bridge.yaml
    voxbridge providers
    voxbridge init [--output bridge.yaml]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger


def cmd_run(args: argparse.Namespace) -> None:
    """Run the VoxBridge bridge."""
    config_path = args.config

    if not Path(config_path).exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    from voxbridge.config import load_config

    config = load_config(config_path)

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=config.logging.level)

    logger.info(f"VoxBridge starting with config: {config_path}")
    logger.info(f"Provider: {config.provider.type}")
    logger.info(f"Listening on: {config.provider.listen_host}:{config.provider.listen_port}")
    logger.info(f"Bot URL: {config.bot.url}")

    # Try FastAPI server first, fall back to plain WebSocket server
    try:
        from voxbridge.server import run_server
        run_server(config)
    except ImportError:
        # FastAPI not available, use plain WebSocket server
        from voxbridge.bridge import VoxBridge
        bridge = VoxBridge(config)
        bridge.run()


def cmd_providers(args: argparse.Namespace) -> None:
    """List available telephony providers."""
    from voxbridge.serializers.registry import serializer_registry

    providers = serializer_registry.available
    print("\nAvailable VoxBridge Providers:")
    print("=" * 40)
    for name in providers:
        serializer = serializer_registry.create(name)
        print(f"  {name:<20} codec={serializer.audio_codec.value}, rate={serializer.sample_rate}")
    print(f"\nTotal: {len(providers)} providers")
    print()


def cmd_init(args: argparse.Namespace) -> None:
    """Generate a starter configuration file."""
    output = Path(args.output)

    if output.exists() and not args.force:
        logger.error(f"File already exists: {output}. Use --force to overwrite.")
        sys.exit(1)

    from voxbridge.config import DEFAULT_CONFIG_YAML

    output.write_text(DEFAULT_CONFIG_YAML)
    print(f"Configuration written to: {output}")
    print(f"\nEdit the file and run: voxbridge run --config {output}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="voxbridge",
        description="VoxBridge - Universal telephony adapter for voice bots",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # `voxbridge run`
    run_parser = subparsers.add_parser("run", help="Run the VoxBridge bridge")
    run_parser.add_argument(
        "--config", "-c",
        default="bridge.yaml",
        help="Path to the bridge YAML config file (default: bridge.yaml)",
    )

    # `voxbridge providers`
    subparsers.add_parser("providers", help="List available telephony providers")

    # `voxbridge init`
    init_parser = subparsers.add_parser("init", help="Generate a starter config file")
    init_parser.add_argument(
        "--output", "-o",
        default="bridge.yaml",
        help="Output file path (default: bridge.yaml)",
    )
    init_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing file",
    )

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "providers":
        cmd_providers(args)
    elif args.command == "init":
        cmd_init(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
