"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import argparse
import os
import shutil
import sys

from . import (
    __version__,
    BuildRunner,
    BuildRunnerConfigurationError,
)
from buildrunner import config, loggers
from buildrunner.config import BuildRunnerConfig
from buildrunner.utils import epoch_time


def parse_args(argv):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog=argv[0], description="buildrunner runs builds defined in buildrunner.yaml"
    )

    parser.add_argument(
        "-c",
        "--global-config",
        default=None,
        dest="global_config_file",
        help='global configuration file (defaults to "~/.buildrunner.yaml")',
    )

    parser.add_argument(
        "-d",
        "--directory",
        default=os.getcwd(),
        dest="directory",
        help="build directory (defaults to current working directory)",
    )
    parser.add_argument(
        "-b",
        "--build-results-directory",
        dest="build_results_dir",
        help="build results directory (defaults to <build-directory>/buildrunner.results)",
    )

    parser.add_argument(
        "-f",
        "--file",
        default=None,
        dest="config_file",
        help='build configuration file (defaults to "buildrunner.yaml", then "gauntlet.yaml")',
    )

    parser.add_argument(
        "-x",
        "--debug",
        dest="debug",
        action="store_true",
        help="enables debug logging",
    )

    parser.add_argument(
        "-n",
        "--build-number",
        default=None,
        dest="build_number",
        help="build number (defaults to unix/epoch time)",
    )

    parser.add_argument(
        "-t",
        "--docker-timeout",
        default=600,
        type=int,
        dest="docker_timeout",
        help="docker timeout in seconds, defaults to 600",
    )

    parser.add_argument(
        "--push",
        default=False,
        action="store_true",
        dest="push",
        help="push images to remote registries (without this flag buildrunner simply tags images)",
    )

    parser.add_argument(
        "--keep-images",
        default=False,
        action="store_true",
        dest="keep_images",
        help="DEPRECATED: The keep-images argument is deprecated. "
        "Keep images is the default behavior. Please use --cleanup-images instead to cleanup images.",
    )

    parser.add_argument(
        "--cleanup-images",
        default=False,
        action="store_true",
        dest="cleanup_images",
        help="Cleanup generated images at the end of the build",
    )

    parser.add_argument(
        "--local-images",
        default=False,
        action="store_true",
        dest="local_images",
        help="Prefer local images rather than fetching remote images. "
        "This can be used for testing images prior to pushing them and is the equivalent "
        "of setting pull to false for every image/build.",
    )

    parser.add_argument(
        "--platform",
        default=None,
        dest="platform",
        type=str,
        help="The platform architecture to pass to the docker daemon when pulling, building, and running images."
        'For example, "linux/amd64" or "linux/arm64/v8".',
    )

    parser.add_argument(
        "--keep-step-artifacts",
        default=False,
        action="store_true",
        dest="keep_step_artifacts",
        help="keep artifacts generated for each step of the build (step artifacts are by default deleted to "
        "prevent clutter on build machines)",
    )

    parser.add_argument(
        "--clean-cache",
        default=False,
        action="store_true",
        dest="clean_cache",
        help='Clean local caches as defined in buildrunner config ("caches-root"), which defaults to '
        "~/.buildrunner/caches",
    )

    parser.add_argument(
        "-s",
        "--steps",
        default=[],
        dest="steps",
        action="append",
        help="only run the listed steps (use the argument multiple times or specify as comma-delimited)",
    )

    parser.add_argument(
        "--publish-ports",
        default=False,
        action="store_true",
        dest="publish_ports",
        help="publish ports defined on a run step, this should never be used on a build server",
    )

    parser.add_argument(
        "--disable-timestamps",
        default=False,
        action="store_true",
        dest="disable_timestamps",
        help="disables printing of timestamps in the logging output",
    )

    parser.add_argument(
        "--version",
        default=False,
        action="store_true",
        dest="print_version",
        help="print the current buildrunner version and exit",
    )

    parser.add_argument(
        "--no-color",
        default=False,
        action="store_true",
        dest="no_log_color",
        help="disable colors when logging",
    )

    parser.add_argument(
        "--print-generated-files",
        default=False,
        action="store_true",
        dest="print_generated_files",
        help="logs the Jinja generated file contents and stops",
    )

    parser.add_argument(
        "--log-generated-files",
        default=False,
        action="store_true",
        dest="log_generated_files",
        help="logs the Jinja generated file contents",
    )

    parser.add_argument(
        "--disable-multi-platform",
        default=None,
        choices=["true", "false"],
        dest="disable_multi_platform",
        help="overrides the 'platforms' configuration and global config; to disable multi-platform builds",
    )

    args = parser.parse_args(argv[1:])

    # Set build results dir if not set
    if not args.build_results_dir:
        args.build_results_dir = os.path.join(args.directory, config.RESULTS_DIR)

    # Only absolute directories can do a mount bind
    args.directory = os.path.realpath(args.directory)

    _steps = []
    for _step in args.steps:
        _steps.extend(_step.split(","))
    args.steps = _steps

    return args


def clean_cache(argv):
    """Cache cleanup"""
    args = parse_args(argv)
    BuildRunnerConfig.initialize_instance(
        push=False,
        build_number=1,
        build_id="",
        vcs=None,
        steps_to_run=[],
        build_dir=args.directory,
        global_config_file=args.global_config_file,
        run_config_file=args.config_file,
        build_time=epoch_time(),
        log_generated_files=(
            bool(args.log_generated_files or args.print_generated_files)
        ),
        # Do not attempt to load run configuration, just global configuration
        load_run_config=False,
    )
    BuildRunner.clean_cache()


def _create_results_dir(cleanup_step_artifacts: bool, build_results_dir: str) -> None:
    try:
        # cleanup existing results dir (if needed)
        if cleanup_step_artifacts and os.path.exists(build_results_dir):
            shutil.rmtree(build_results_dir)
        # (re)create the build results dir
        os.makedirs(build_results_dir, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"ERROR: {str(exc)}\n")
        sys.exit(os.EX_UNAVAILABLE)


def initialize_br(args: argparse.Namespace) -> BuildRunner:
    _create_results_dir(not args.keep_step_artifacts, args.build_results_dir)
    loggers.initialize_root_logger(
        args.debug,
        args.no_log_color,
        args.disable_timestamps,
        args.build_results_dir,
    )

    # set build time
    build_time = epoch_time()

    # set build number
    build_number = args.build_number
    if not build_number:
        build_number = build_time

    return BuildRunner(
        build_dir=args.directory,
        build_results_dir=args.build_results_dir,
        global_config_file=args.global_config_file,
        run_config_file=args.config_file,
        build_time=build_time,
        build_number=build_number,
        push=args.push,
        cleanup_images=args.cleanup_images,
        cleanup_cache=args.clean_cache,
        steps_to_run=args.steps,
        publish_ports=args.publish_ports,
        log_generated_files=(
            bool(args.log_generated_files or args.print_generated_files)
        ),
        docker_timeout=args.docker_timeout,
        local_images=args.local_images,
        platform=args.platform,
        disable_multi_platform=None
        if args.disable_multi_platform is None
        else args.disable_multi_platform == "true",
    )


def main(argv):
    """Main program execution."""
    args = parse_args(argv)

    # are we just printing the version?
    if args.print_version:
        print(__version__)
        return os.EX_OK

    try:
        build_runner = initialize_br(args)
        if not args.print_generated_files:
            build_runner.run()
            if build_runner.exit_code:
                return build_runner.exit_code
    except BuildRunnerConfigurationError as brce:
        print((str(brce)))
        return os.EX_CONFIG
    return os.EX_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
